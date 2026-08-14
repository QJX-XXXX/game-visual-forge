# Stable Audio 3 local runtime

This is an optional setup for `forge-text-audio`. It installs the official
`Stability-AI/stable-audio-3` source, its isolated Python environment, model
cache, and temporary files below one directory chosen by you. It does not use
a hosted audio API, change user variables or `PATH`, or accept a license for you.

Chinese version: [README.zh-CN.md](README.zh-CN.md)

## 1. Choose a root

Run these commands in a fresh PowerShell process. The prompt accepts any
absolute path, including a path on the system drive. Do not replace it with a
repository-relative default.

```powershell
$AudioRoot = Read-Host "Stable Audio 3 installation directory"
$AudioRoot = [System.IO.Path]::GetFullPath($AudioRoot)
$AudioRuntime = Join-Path $AudioRoot "runtime"
$AudioTemp = Join-Path $AudioRoot "temp"
New-Item -ItemType Directory -Force -Path $AudioRoot,$AudioTemp | Out-Null
Set-Location $AudioRoot
```

All variables below are process-local. They are deliberately not written to
user or machine environment settings:

```powershell
$env:UV_INSTALL_DIR = Join-Path $AudioRoot "bin"
$env:UV_CACHE_DIR = Join-Path $AudioRoot "cache\uv"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $AudioRoot "python"
$env:UV_PYTHON_BIN_DIR = Join-Path $AudioRoot "python\bin"
$env:HF_HOME = Join-Path $AudioRoot "models\huggingface"
$env:HUGGINGFACE_HUB_CACHE = Join-Path $AudioRoot "models\huggingface\hub"
$env:TORCH_HOME = Join-Path $AudioRoot "cache\torch"
$env:PIP_CACHE_DIR = Join-Path $AudioRoot "cache\pip"
$env:TEMP = $AudioTemp
$env:TMP = $AudioTemp
$env:UV_NO_MODIFY_PATH = "1"
New-Item -ItemType Directory -Force -Path $env:UV_INSTALL_DIR,$env:UV_CACHE_DIR,$env:UV_PYTHON_INSTALL_DIR,$env:HF_HOME,$env:HUGGINGFACE_HUB_CACHE,$env:TORCH_HOME,$env:PIP_CACHE_DIR | Out-Null
```

## 2. Install uv and the official source

Use the official uv installer in the active shell. `UV_NO_MODIFY_PATH=1` keeps
the install from changing persistent `PATH`; invoke the resulting executable
by its absolute path:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
$Uv = Join-Path $env:UV_INSTALL_DIR "uv.exe"
if (!(Test-Path $Uv)) { throw "uv.exe was not installed under $env:UV_INSTALL_DIR" }
& $Uv python install 3.12
git clone https://github.com/Stability-AI/stable-audio-3.git $AudioRuntime
Set-Location $AudioRuntime
& $Uv venv --python 3.12 .venv
```

If `git` is unavailable, download the official repository archive manually
into `$AudioRuntime` and keep its `pyproject.toml` at that directory root.

For an NVIDIA CUDA 12.6 machine, install the pinned wheels into this isolated
environment before syncing the repository:

```powershell
& $Uv pip install --python "$AudioRuntime\.venv\Scripts\python.exe" `
  torch==2.7.1 torchaudio==2.7.1 `
  --index-url https://download.pytorch.org/whl/cu126
& $Uv sync --project $AudioRuntime --no-install-package torch --no-install-package torchaudio
```

CPU is a supported Small-SFX route; omit the CUDA wheel command and run
`& $Uv sync --project $AudioRuntime` when CUDA is not available.

## 3. Accept the model terms yourself

Open [the official Small-SFX model page](https://huggingface.co/stabilityai/stable-audio-3-small-sfx), read and personally accept the Stability AI Community License and Gemma terms. This is a hard gate: an Agent must stop here and must not click, accept, or paste a token for you.

After you confirm that authorization is complete, authenticate interactively
without putting a token in a command, README, or repository file:

```powershell
Set-Location $AudioRuntime
& "$AudioRuntime\.venv\Scripts\hf.exe" auth login
& "$AudioRuntime\.venv\Scripts\python.exe" -c "from huggingface_hub import snapshot_download; print(snapshot_download('stabilityai/stable-audio-3-small-sfx'))"
```

The snapshot must be beneath `$AudioRoot\models\huggingface` and contain
`model_config.json` and `model.safetensors`.

## 4. Configure Game Visual Forge

From the Game Visual Forge repository root, run:

```powershell
python skills/forge-text-audio/scripts/run.py audio sfx provider configure --root "$AudioRoot"
python skills/forge-text-audio/scripts/run.py audio sfx provider show-config
python skills/forge-text-audio/scripts/run.py audio sfx provider preflight
```

`configure` writes only the ignored `game-visual-forge.local.json` with
absolute paths. It is idempotent; a different existing configuration requires
`--replace`. It never stores credentials or media and never changes user
environment variables or `PATH`.

Preflight is offline and non-mutating. It must report `available: true`,
package `stable-audio-3`, model `small-sfx`, a local model snapshot, FFmpeg and
FFprobe availability, and the actual CUDA/device evidence. Missing installation
or authorization returns `needs_user_action` with a copyable setup request.

## Upgrade and removal

To upgrade, activate the same process-local variables, update the official
checkout under `$AudioRuntime`, run the documented sync command, then rerun
`provider preflight`. Do not install into the Game Visual Forge Python.

To remove the setup, first delete only `game-visual-forge.local.json` from the
repository. Display and confirm the exact value of `$AudioRoot`, then remove
that one user-selected directory. Do not use a broad wildcard or a recursive
command against an unresolved path.

## Cost and licensing boundary

This route runs the model locally; it does not charge per generation through a
hosted API. The model and source remain subject to their official licenses,
including any usage restrictions. License acceptance is always your decision.
