"""Read-only environment evidence and setup suggestions; Python 3.8+ compatible."""

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path


PROFILES = {
    "core": (),
    "image": (("Pillow", "PIL.Image"),),
    "background": (("Pillow", "PIL.Image"), ("numpy", "numpy"), ("scipy", "scipy"), ("rembg", "rembg")),
}


def _probe(module):
    # Import only; never create model sessions, install packages, or print
    # third-party output. -B avoids creating bytecode during diagnostics.
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-c", "import importlib,sys; importlib.import_module(sys.argv[1])", module],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def inspect_environment(repo_root, profile="image", *, version=None, system=None, virtual_environment=None, probe=None, venv_dir=None):
    """Report the selected interpreter. Returned argv suggestions never execute."""
    if profile not in PROFILES:
        raise ValueError("unknown environment profile")
    root = Path(repo_root).resolve()
    version = tuple(version or sys.version_info[:3])
    system = system or platform.system()
    virtual_environment = (sys.prefix != sys.base_prefix) if virtual_environment is None else virtual_environment
    probe = probe or _probe
    supported = version[:2] >= (3, 11)
    target = Path(venv_dir).resolve() if venv_dir else root / ".venv"
    target_python = target / ("Scripts/python.exe" if system == "Windows" else "bin/python")
    report = {
        "schema_version": 1, "status": "ready", "system": system,
        "repo_root": str(root), "profile": profile,
        "python": {"executable": sys.executable, "version": ".".join(map(str, version)), "supported": supported, "virtual_environment": virtual_environment},
        "dependencies": [], "missing": [], "pip_available": None,
        "venv_available": None, "suggested_commands": [],
        "scope": "python-packages", "model_assets_verified": False,
        "guidance": "Use this exact interpreter for every launcher and pip command. Setup suggestions require user authorization; existing authorization remains valid.",
    }
    if not supported:
        report.update(status="needs_setup", missing=["Python >=3.11"], guidance="Select an existing Python 3.11+ interpreter, or obtain one from https://www.python.org/downloads/ for this system. Re-run this checker with that exact interpreter before starting the Forge runtime.")
        return report
    if not (root / "pyproject.toml").is_file() or not (root / "src/game_visual_forge").is_dir() or not (root / "skills").is_dir():
        report.update(status="needs_setup", missing=["Forge repository"], guidance="Choose the intact Forge repository with skills/, src/game_visual_forge/, and pyproject.toml using --repo-root. No setup commands were executed.")
        return report
    report["pip_available"] = bool(probe("pip"))
    report["venv_available"] = bool(probe("venv"))
    for name, module in PROFILES[profile]:
        available = bool(probe(module))
        report["dependencies"].append({"name": name, "module": module, "available": available})
        if not available:
            report["missing"].append(name)
    if not report["missing"]:
        return report
    report["status"] = "needs_setup"
    commands = report["suggested_commands"]
    if virtual_environment and (venv_dir is None or target == Path(sys.prefix).resolve()):
        python = sys.executable
        if not report["pip_available"]:
            commands.append({"action": "bootstrap-pip-in-selected-environment", "argv": [python, "-m", "ensurepip", "--upgrade"]})
    elif target.exists():
        if target_python.is_file():
            commands.append({"action": "recheck-existing-environment", "argv": [str(target_python), str(Path(__file__).resolve()), "--repo-root", str(root), "--profile", profile, "--venv-dir", str(target)]})
            report["guidance"] += " An environment already exists; inspect it with its own interpreter before choosing where to install."
        else:
            report["guidance"] += " The proposed environment directory already exists without the expected interpreter; preserve it and choose another destination using --venv-dir."
        return report
    else:
        if not report["venv_available"]:
            report["guidance"] += " The venv module is unavailable. Consult this system's Python installation/package manager before creating an isolated environment."
            return report
        commands.append({"action": "create-isolated-environment", "argv": [sys.executable, "-m", "venv", str(target)]})
        python = str(target_python)
    commands.append({"action": "install-selected-extra", "argv": [python, "-m", "pip", "install", "-e", str(root) + "[" + profile + "]"]})
    report["guidance"] += " No commands were executed. Authorize only the required packages and destination. Model files, cache directories, credentials, and paid requests are separate."
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--profile", choices=tuple(PROFILES), default="image")
    parser.add_argument("--venv-dir", type=Path)
    args = parser.parse_args(argv)
    report = inspect_environment(args.repo_root, args.profile, venv_dir=args.venv_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
