# Stable Audio 3 本地运行时

这是 `forge-text-audio` 的可选安装。它会把官方
`Stability-AI/stable-audio-3` 源码、独立 Python 环境、模型缓存和临时文件
放在你选择的同一个目录下。不调用托管音频 API，不修改用户变量或 `PATH`，
也不会代替你接受许可证。

English: [README.md](README.md)

## 1. 选择目录

请在新的 PowerShell 进程中运行。这里可以填写任意绝对路径，包括系统盘；
不要替换为仓库相对路径或固定盘符：

```powershell
$AudioRoot = Read-Host "Stable Audio 3 installation directory"
$AudioRoot = [System.IO.Path]::GetFullPath($AudioRoot)
$AudioRuntime = Join-Path $AudioRoot "runtime"
$AudioTemp = Join-Path $AudioRoot "temp"
New-Item -ItemType Directory -Force -Path $AudioRoot,$AudioTemp | Out-Null
Set-Location $AudioRoot
```

下面的变量只存在于当前安装进程，不会写入用户或系统环境变量：

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

## 2. 安装 uv 和官方源码

使用官方 uv 安装器，并在当前进程中禁用持久化 `PATH` 修改：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
$Uv = Join-Path $env:UV_INSTALL_DIR "uv.exe"
if (!(Test-Path $Uv)) { throw "uv.exe was not installed under $env:UV_INSTALL_DIR" }
& $Uv python install 3.10
git clone https://github.com/Stability-AI/stable-audio-3.git $AudioRuntime
Set-Location $AudioRuntime
& $Uv venv --python 3.10 .venv
```

如果没有 `git`，请手动下载官方仓库压缩包并解压到 `$AudioRuntime`，确保该目录
根部存在 `pyproject.toml`。

NVIDIA CUDA 12.6 可先安装固定版本的 CUDA wheels，再同步仓库依赖：

```powershell
& $Uv pip install --python "$AudioRuntime\.venv\Scripts\python.exe" `
  torch==2.7.1 torchaudio==2.7.1 `
  --index-url https://download.pytorch.org/whl/cu126
& $Uv sync --project $AudioRuntime --no-install-package torch --no-install-package torchaudio
```

Small-SFX 也支持 CPU；没有 CUDA 时跳过 wheels 命令，执行
`& $Uv sync --project $AudioRuntime` 即可。

## 3. 由你本人接受模型条款

打开[官方 Small-SFX 模型页面](https://huggingface.co/stabilityai/stable-audio-3-small-sfx)，
阅读并由你本人接受 Stability AI Community License 和 Gemma 条款（license acceptance）。这是硬性停点：
Agent 不得代你点击、接受或粘贴 token。

你确认授权完成后，再交互式登录，不要把 token 放进命令、README 或仓库文件：

```powershell
Set-Location $AudioRuntime
& "$AudioRuntime\.venv\Scripts\hf.exe" auth login
& "$AudioRuntime\.venv\Scripts\python.exe" -c "from huggingface_hub import snapshot_download; print(snapshot_download('stabilityai/stable-audio-3-small-sfx'))"
```

模型快照必须位于 `$AudioRoot\models\huggingface` 下，并包含
`model_config.json` 和 `model.safetensors`。

## 4. 配置 Game Visual Forge

在 Game Visual Forge 仓库根目录运行：

```powershell
python skills/forge-text-audio/scripts/run.py audio sfx provider configure --root "$AudioRoot"
python skills/forge-text-audio/scripts/run.py audio sfx provider show-config
python skills/forge-text-audio/scripts/run.py audio sfx provider preflight
```

`configure` 只写入被 Git 忽略的 `game-visual-forge.local.json` 和绝对路径。
同一配置可重复执行；已有不同配置时必须显式加 `--replace`。它不会保存凭据或媒体，
也不会修改用户环境变量或 `PATH`。

预检是离线且不改变状态的操作，必须报告 `available: true`、包
`stable-audio-3`、模型 `small-sfx`、本地模型快照、FFmpeg/FFprobe 和实际 CUDA/设备信息。
安装或授权缺失时返回 `needs_user_action`，并给出可复制的安装请求。

## 升级和移除

升级时在同一个临时变量进程中更新 `$AudioRuntime` 下的官方源码，运行同步命令，
再执行 `provider preflight`。不要把 Stable Audio 安装进 Game Visual Forge 的 Python。

移除时先只删除仓库中的 `game-visual-forge.local.json`。显示并确认 `$AudioRoot`
的精确值后，再删除这一个用户选定目录；不要对未解析路径使用通配符或宽泛递归命令。

## 费用与许可证边界

此方案在本地运行模型，不通过托管 API 按次收费。模型和源码仍受官方许可证及其使用
限制约束，许可证是否接受始终由你决定。
