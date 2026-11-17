# Python environment checks and assisted setup

Use this guide before a Forge launcher or local processing command. Explain
results in the user's language. Native Agent image tools do not require this
Python runtime; local validation/processing and direct API adapters do.
The runtime requires Python 3.11+. Keep the full repository available.

## First discover the actual host and interpreter

Do not assume a `python` command, an activated environment, or Agent-specific
paths. Inspect the OS, available shell, existing project environment, Python
executables, and package managers before choosing commands.

On Windows PowerShell, discover paths without starting an installer:

```powershell
Get-Command python, python3, py, pymanager -All -ErrorAction SilentlyContinue |
  Select-Object Name, Source
```

If a launcher is present, list installed runtimes with `py -0p`; the newer
install manager also supports `py list`/`pymanager list`. A WindowsApps alias
does not prove Python is installed. Avoid blindly launching aliases or
`py exec` during discovery: the install manager can download a missing runtime.
Choose an existing interpreter's full path and verify its version and
`sys.executable`. Reuse an appropriate existing project environment when possible.

On macOS/Linux, inspect `uname -s` and `command -v python3` (or `type -a python3`).
On Linux also inspect `/etc/os-release` before choosing a package manager.
Check the resolved interpreter's version; do not assume `python` means Python 3.

## No Python, or an unsupported version

If no usable interpreter exists, say so before running `.py` commands. Report
the detected OS, command/path evidence, and the Python 3.11+ requirement. Offer
manual instructions or Agent-assisted setup; continue native image work only
if it is useful and clearly explain that final local processing is pending.

- Windows: use the official Python install manager/installer appropriate to the
  machine and its available installation tools. Prefer an existing runtime over
  downloading another one. Use absolute paths after setup; do not change global
  PATH or overwrite another Python installation.
- macOS: use an existing supported interpreter or the official Python installer;
  use Homebrew only when it is already available and that installation is authorized.
- Linux: match the distribution/package manager and privileges actually found.
  A separate `python3-venv` or pip package may be needed. Preserve the OS Python;
  do not use global pip, `sudo pip`, or `--break-system-packages`.

Select a supported version compatible with the dependencies needed by the
current task, rather than blindly installing the newest runtime. Show the
specific source, destination, and commands once those host facts are known.
If the Agent has no local command execution, provide the user's exact commands
and wait for their results; do not claim to have configured the environment.

## Run the standalone read-only checker

The checker uses the standard library and can run under Python 3.8+ before the
3.11+ Forge runtime is imported. Older runtimes should follow the upgrade path
above. An old interpreter produces `needs_setup` instead of importing Forge.

```powershell
& "<verified-python.exe>" "<forge-root>/install/check_environment.py" --profile image
```

POSIX equivalent:

```bash
"<verified-python>" "<forge-root>/install/check_environment.py" --profile image
```

Profiles are `core` (runtime commands), `image` (Pillow), and `background`
(Pillow, NumPy, SciPy, rembg). Choose only what this task requires. Valid native
Alpha and explicit opaque delivery do not require rembg. A known chroma source
can use the existing color-key processor when the user selects that treatment.
Background package checks do not prove model files are cached or usable.

The JSON identifies `python.executable`, version, virtual-environment state,
pip/venv availability, dependencies, missing items, and suggested setup argv.
`ready` means the checked Python/modules are available, not that API credentials,
background model assets, FFmpeg, audio runtimes, or engine tools were verified.
Imports run in child processes; the checker does not install or download models.
It never reads API keys or invokes a provider. Exit 0 means ready; exit 1 means
setup is needed. `--venv-dir` selects another proposed environment directory.

If the selected interpreter is wrong, re-run the checker with the existing
environment's interpreter. Do not install into the wrong environment just
because bare `python` or bare `pip` happens to work.

## Help configure only the authorized scope

If the user has already asked the Agent to configure the environment, act
within that authorization after inspection. Do not ask the same approval again.
Ask only for missing material choices such as an installation/cache destination.
Without setup authorization, present the missing prerequisites, exact commands,
and an option for manual setup or Agent help. Ordinary asset work does not
authorize arbitrary installation, credential changes, or paid generation.

Preserve existing environments. The checker suggests rechecking an existing
environment instead of overwriting it. For a new approved destination:

```powershell
& "<verified-base-python.exe>" -m venv "<chosen-environment>"
& "<chosen-environment>/Scripts/python.exe" -m pip install -e "<forge-root>[image]"
```

On POSIX use `<chosen-environment>/bin/python`. Use `[background]` only when
local background removal needs it. Always bind pip to the selected interpreter
with `-m pip`; render argv with quoting appropriate to the user's shell.
Activation and PowerShell execution-policy changes are unnecessary when using
the environment interpreter directly. Do not create over an existing directory.

If pip is missing inside the selected environment, use that interpreter's
`-m ensurepip --upgrade` where supported. If venv/ensurepip is missing or package
resolution fails, explain the actual error and adapt to the detected OS/version
instead of repeating the failed command or modifying system Python.

Python package installation and model preparation are separate. Before rembg
processing, inspect the selected model and cache location (`U2NET_HOME`, or the
runtime's default cache). Missing model assets require an explicit model/cache
setup decision; an isolated venv does not isolate model caches automatically.
Keep personal license acceptance and Stable Audio/ComfyUI/provider-specific
installation gates. This guide does not authorize weights, nodes, or paid calls.

## Verify the result

Re-run the checker and the selected Skill launcher's `--help` using the exact
chosen interpreter. Check the relevant modules and local processing path.
For a selected API, run its offline preflight separately. Report executed
commands, interpreter/environment paths, actual results, and unresolved items.
Distinguish instructions offered, setup performed, and setup verified.

Official references: [Python on Windows](https://docs.python.org/3/using/windows.html),
[venv](https://docs.python.org/3/library/venv.html), and the
[Python Packaging guide](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/).
