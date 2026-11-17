"""Existing-tool execution. Installation and login are deliberately user actions."""
from __future__ import annotations

import importlib.util
import importlib.metadata
import json
import os
import shutil
import subprocess
from pathlib import Path

from .image_http import ImageApiError, assert_safe


CLI_COMMANDS = {"minimax": "mmx", "jimeng": "dreamina", "dreamina": "dreamina", "wanxiang": "bl"}
OFFICIAL_GUIDES = {
    "minimax": "https://github.com/MiniMax-AI/cli",
    "jimeng": "https://jimeng.jianying.com/cli",
    "dreamina": "https://jimeng.jianying.com/cli",
    "wanxiang": "https://help.aliyun.com/zh/model-studio/cli/overview",
}
_BOOTSTRAPPERS = {"uv", "uvx", "npx", "npm", "pip", "pip3", "pipx", "winget", "choco", "curl", "wget", "powershell", "pwsh", "cmd", "bash", "sh"}
_CREDENTIAL_FLAGS = {"--api-key", "--token", "--authorization", "--secret-key", "--access-key", "--password"}


def existing_command(command):
    if not isinstance(command, list) or not command or any(not isinstance(item, str) or not item for item in command):
        raise ValueError("tool command must be a nonempty argv array")
    executable = Path(command[0]).stem.lower()
    if executable in _BOOTSTRAPPERS or any(item in {"install", "-m pip", "ensurepip"} for item in command[1:]):
        raise ValueError("generation requires an already installed executable; confirm installation separately")
    if any(item.lower().split("=", 1)[0] in _CREDENTIAL_FLAGS for item in command[1:]):
        raise ValueError("configure tool credentials through environment variables")
    resolved = shutil.which(command[0])
    if resolved is None:
        raise FileNotFoundError("configured tool executable is unavailable")
    return [resolved, *command[1:]]


def execution_config(provider, value=None):
    if value is not None and not isinstance(value, dict):
        raise ValueError("execution configuration must be a JSON object")
    config = dict(value or {"backend": "api"})
    assert_safe(config)
    backend = config.get("backend", "api")
    if backend not in {"api", "cli", "mcp"}:
        raise ValueError("backend must be api, cli, or mcp")
    config["backend"] = backend
    allowed = {"backend", "command", "transport", "url", "credential_env", "timeout_seconds"}
    if set(config) - allowed:
        raise ValueError("unsupported execution configuration")
    timeout = config.setdefault("timeout_seconds", 900 if provider == "minimax" and backend == "mcp" else 600)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 3600:
        raise ValueError("tool timeout_seconds must be 1–3600")
    if backend == "cli":
        config.setdefault("command", [CLI_COMMANDS[provider]])
    elif backend == "mcp":
        config.setdefault("transport", "stdio" if provider == "minimax" else "streamable-http")
        if config["transport"] not in {"stdio", "streamable-http", "sse"}:
            raise ValueError("unsupported MCP transport")
        if provider == "minimax" and config["transport"] == "stdio":
            config.setdefault("command", ["minimax-mcp"])
            config.setdefault("credential_env", "MINIMAX_API_KEY")
        if config["transport"] != "stdio":
            if provider == "wanxiang":
                config.setdefault("url", "https://dashscope.aliyuncs.com/api/v1/mcps/TextGenerateImage/mcp")
                config.setdefault("credential_env", "DASHSCOPE_API_KEY")
            from urllib.parse import urlsplit
            parsed = urlsplit(config.get("url", ""))
            if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("MCP requires a credential-free endpoint URL; use credential_env for authentication")
            if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("remote MCP requires HTTPS")
        variable = config.get("credential_env")
        if variable is not None:
            import re
            if not isinstance(variable, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", variable):
                raise ValueError("credential_env must name an environment variable")
    if "command" in config:
        command = config["command"]
        if not isinstance(command, list) or not command or any(not isinstance(item, str) or not item for item in command):
            raise ValueError("tool command must be a nonempty argv array")
        if Path(command[0]).stem.lower() in _BOOTSTRAPPERS:
            raise ValueError("use an installed tool executable; installation requires user confirmation")
        if any(item.lower().split("=", 1)[0] in _CREDENTIAL_FLAGS for item in command[1:]):
            raise ValueError("configure tool credentials through environment variables")
    return config


def tool_preflight(provider, config):
    backend = config["backend"]
    missing = []
    if backend == "cli" or config.get("transport") == "stdio":
        try:
            existing_command(config.get("command", []))
        except FileNotFoundError:
            missing.append("tool executable")
    if backend == "mcp":
        try:
            version = importlib.metadata.version("mcp")
            if version.split(".", 1)[0] != "2":
                missing.append("Python mcp>=2,<3 extra")
        except importlib.metadata.PackageNotFoundError:
            missing.append("Python mcp>=2,<3 extra")
    if importlib.util.find_spec("PIL") is None:
        missing.append("Python Pillow package")
    variable = config.get("credential_env")
    credential_missing = bool(variable and not os.environ.get(variable))
    reason = "configure " + variable if credential_missing else "prerequisites available; live authentication unverified"
    if missing:
        reason = "missing " + ", ".join(missing)
    return {
        "schema_version": 1, "provider": provider, "backend": backend,
        "available": not missing and not credential_missing,
        "authenticated": False, "authentication_verified": False,
        "missing": missing, "reason": reason,
        "requires_installation_confirmation": bool(missing),
        "official_guide": OFFICIAL_GUIDES[provider],
    }


def run_tool(config, arguments):
    argv = [*existing_command(config["command"]), *arguments]
    try:
        result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False, timeout=config["timeout_seconds"], check=False)
    except subprocess.TimeoutExpired:
        raise ImageApiError("tool_timeout") from None
    if result.returncode:
        # Vendor stderr can include credentials, signed URLs and prompt media.
        raise ImageApiError("tool_exit_" + str(result.returncode))
    try:
        value = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise ImageApiError("invalid_tool_json") from None
    if not isinstance(value, dict):
        raise ImageApiError("invalid_tool_result")
    return value


def require_help_flags(config, subcommand, arguments):
    """Dreamina publishes flags through the installed command's help."""
    result = subprocess.run([*existing_command(config["command"]), subcommand, "-h"], capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False, timeout=30, check=False)
    if result.returncode:
        raise ValueError("Dreamina command help is unavailable")
    flags = {item.split("=", 1)[0] for item in arguments if item.startswith("--")}
    if any(flag not in result.stdout for flag in flags):
        raise ValueError("installed Dreamina command does not advertise the required flags")
