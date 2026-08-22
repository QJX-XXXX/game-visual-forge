# Game Visual Forge 安装指南

[English](README.md)

这是仓库唯一的安装指南，包含两种方式：复制下面的请求给 Agent，让它分步骤执行；或者按手动流程操作。仓库包含四个核心 Skill，可选 Provider 和运行时必须单独主动启用。

## 复制下面这句话给 Agent

```text
请按仓库统一安装指南，从 https://github.com/QJX-XXXX/game-visual-forge.git
安装 Game Visual Forge。请严格分步骤执行，并在运行每条命令前先展示给我。
先确认仓库根目录、目标位置、Python 3.11+ 解释器、FFmpeg、FFprobe 和 Agent
Skill 发现目录；保持 skills/、src/、pyproject.toml 属于同一个完整仓库。请在
克隆、创建链接、创建虚拟环境或安装包之前先向我确认核心安装。然后只安装或
链接这四个 Skill：forge-2d-map、forge-2d-sprite、forge-text-audio、
forge-video-to-sprite。已有 Skill 目标不得覆盖；验证每个 SKILL.md，并运行
启动器 --help 检查。除非我明确要求启用某个可选配置，不得安装或探测 Comfy
MCP、h3-prompt-writing、Provider CLI、模型、节点、凭据或付费服务。对于可选
配置，先询问是否启用，接受后只读检查，列出缺失组件计划，再次确认后只安装
已批准的缺失部分。ComfyUI MiniMax H3 的模型或节点下载，还必须单独确认许可证、
大小和目标位置。请报告所有命令、路径、结果以及仍需我处理的事项。
```

Agent 不得把这段请求理解为代替用户接受许可证、打印密钥、提交付费生成请求或覆盖已有安装的授权。

## 核心仓库与 Skill 范围

核心安装是完整仓库加上以下四个 Skill 目录：

- `forge-2d-map`
- `forge-2d-sprite`
- `forge-text-audio`
- `forge-video-to-sprite`

请让 `skills/`、`src/` 和 `pyproject.toml` 保持在同一个仓库根目录。只复制一个 Skill 目录不受支持，因为启动器需要从 `src/` 解析共享运行时。

## 手动安装 / Manual installation

### 1. 检查前置条件

获取仓库需要 Git；共享运行时需要 Python 3.11 或更高版本；本地视频/音频处理需要 FFmpeg 和 FFprobe。先只读检查，不要修改机器：

```powershell
git --version
python --version
ffmpeg -version
ffprobe -version
```

POSIX 系统如果没有 `python`，使用 `python3`。缺少的操作系统工具应通过官方渠道由用户手动安装。

### 2. 获取或复用仓库

新目录执行：

```powershell
git clone https://github.com/QJX-XXXX/game-visual-forge.git
Set-Location game-visual-forge
```

已有仓库时运行 `git rev-parse --show-toplevel`，确认其中包含 `skills/`、`src/` 和 `pyproject.toml`，并保留根目录完整。不要覆盖已有目录，也不要丢弃本地改动。

确认目录后创建隔离 Python 环境：

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -e .
```

POSIX 等价命令：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

### 3. 链接四个 Skill

Codex 通常从 `$HOME/.agents/skills` 发现全局 Skill。Claude 以 `SKILL.md` 为权威；如果当前 Claude 环境支持相同目录，就使用相同链接，否则使用 Claude 文档规定的 Skill 目录，并保持链接指向本仓库。 `agents/openai.yaml` 只是 Codex 兼容元数据，不是执行指令。

Windows PowerShell Junction（已有目标直接拒绝）：

```powershell
$ForgeRoot = (Resolve-Path -LiteralPath (Get-Location)).Path
$SkillHome = Join-Path ([Environment]::GetFolderPath("UserProfile")) ".agents\\skills"
$SkillNames = @("forge-2d-map", "forge-2d-sprite", "forge-text-audio", "forge-video-to-sprite")
New-Item -ItemType Directory -Force -Path $SkillHome | Out-Null
foreach ($SkillName in $SkillNames) {
    $Source = Join-Path $ForgeRoot "skills\\$SkillName"
    $Target = Join-Path $SkillHome $SkillName
    if (!(Test-Path -LiteralPath (Join-Path $Source "SKILL.md"))) { throw "Missing Skill source: $Source" }
    if (Test-Path -LiteralPath $Target) { throw "Skill target already exists: $Target" }
    New-Item -ItemType Junction -Path $Target -Target $Source | Out-Null
}
```

POSIX symbolic link：

```bash
forge_root="$(pwd -P)"
skill_home="$HOME/.agents/skills"
mkdir -p "$skill_home"
for skill_name in forge-2d-map forge-2d-sprite forge-text-audio forge-video-to-sprite; do
  source_path="$forge_root/skills/$skill_name"
  target_path="$skill_home/$skill_name"
  test -f "$source_path/SKILL.md" || { echo "Missing Skill source: $source_path" >&2; exit 1; }
  test ! -e "$target_path" && test ! -L "$target_path" || { echo "Skill target already exists: $target_path" >&2; exit 1; }
  ln -s "$source_path" "$target_path"
done
```

### 4. 验证并重启

确认每个链接都能解析到 `SKILL.md`，然后运行：

```powershell
python skills/forge-2d-map/scripts/run.py --help
python skills/forge-2d-sprite/scripts/run.py --help
python skills/forge-video-to-sprite/scripts/run.py --help
python -m unittest discover -s tests -q
```

重启 Agent 会话，让 Skill 发现重新加载。卸载核心链接时，只删除 `.agents/skills` 下的四个链接，不要删除仓库或其中的 `skills/`、`src/` 目录。

## 可选工作流门禁

核心安装不会安装可选工作流。每个配置都必须遵循：

1. 询问是否启用。
2. 拒绝时跳过，不探测、不修改环境。
3. 接受后只读检查。
4. 展示版本、路径、缺失组件、精确命令、目标位置和下载项。
5. 再次确认安装。
6. 只安装用户批准的缺失部分。
7. 验证配置。

### ComfyUI MiniMax H3

#### 询问是否启用 ComfyUI MiniMax H3

先询问是否启用 ComfyUI MiniMax H3。明确同意后，执行下一步。

#### 只读检查，不执行安装

检查 Python、`comfy --version`、选定的 ComfyUI 工作区/运行状态、MCP 配置、`comfy-mcp` 和 `$HOME/.agents/skills/h3-prompt-writing/SKILL.md`，全程只读，不创建链接、不安装包、不下载内容。

#### 展示缺失组件计划

展示已安装版本和路径、冲突、缺失组件、精确命令、目标位置和下载项，并附上官方安装链接；明确说明此时仍只是计划，没有安装任何内容。

#### 确认可选安装

展示计划后再次确认。没有批准精确命令、目标位置和下载项时不得继续。

#### 只安装已批准的缺失组件

只安装已批准的 `comfy-cli`、`Comfy MCP` 和 `h3-prompt-writing` 缺失部分。H3 工作流节点和模型权重还必须进行第三次确认，展示许可证、下载大小、目标位置和精确标识符。

### 海螺/MiniMax（MiniMax Hailuo API）、即梦（Jimeng API）与 CLI 兼容

海螺/MiniMax API 只检查 `MINIMAX_API_KEY`；即梦 API 只检查 `JIMENG_ACCESS_KEY` 和 `JIMENG_SECRET_KEY`。绝不打印或保存密钥，绝不在安装过程中安装 Provider CLI 或发送付费/生成请求。 `mmx` 与 `dreamina` 必须先确认经过验证的第一方来源和所需视频命令，否则报告 `CLI auto-install unavailable` 并提供 API 路线。

## 独立安装链接

以下是独立运行时或外部依赖的安装说明，不属于四个核心仓库 Skill：

- [Stable Audio 3 安装指南](stable-audio-3/README.zh-CN.md)
- [Comfy MCP 官方安装说明](https://docs.comfy.org/agent-tools/mcp#installation)
- [MiniMax H3 Prompt Writing Skill 官方安装说明](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/README.md#installation)
