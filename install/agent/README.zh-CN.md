# 通过 Agent 安装 Game Visual Forge

[English](README.md)

本指南是 Agent 可执行安装流程的权威核心安装契约。

核心范围：

- 安装全部四个 Skill：`forge-2d-map`、`forge-2d-sprite`、`forge-text-audio`、`forge-video-to-sprite`。
- 始终一起保留 `skills/`、`src/` 与 `pyproject.toml`，它们必须来自同一个仓库根目录。
- 使用 Codex 可发现的 `.agents/skills` 路径，并把 Skill 目录链接进去，而不是单独复制某一个 Skill。
- 共享运行时要求 `Python 3.11` 或更新版本；本地音视频处理还需要单独规划 `FFmpeg` 与 `FFprobe`。

权限与安全边界：

- 在创建链接或安装任何 Python 包之前，必须先请求核心安装确认。
- 不得覆盖现有目标；发现已存在的目标时，应检查后改用其他位置或直接停止。
- 为每个 Skill 创建链接前，都要先验证 `SKILL.md` 存在。
- 此核心流程不会安装可选工作流、Comfy MCP、`h3-prompt-writing`、provider CLI、模型、自定义节点、凭据或任何付费服务。
- 此核心流程不会安装可选工作流，也不会在核心安装完成后自动启用任何可选项。

执行前，先向用户展示：

- 目标 Agent 与 `.agents/skills` 目录；
- 保留 `skills/`、`src/`、`pyproject.toml` 的仓库根目录；
- 将运行共享包的 `Python 3.11+` 解释器；
- `FFmpeg` 与 `FFprobe` 是否已存在，或是否仍需单独进行系统级安装；
- 确认后才会创建的精确链接与 Python 包安装位置。

Windows PowerShell 目录联接流程：

```powershell
$ForgeRoot = (Resolve-Path -LiteralPath (Get-Location)).Path
$SkillHome = Join-Path ([Environment]::GetFolderPath("UserProfile")) ".agents\skills"
$SkillNames = @("forge-2d-map", "forge-2d-sprite", "forge-text-audio", "forge-video-to-sprite")
New-Item -ItemType Directory -Force -Path $SkillHome | Out-Null
foreach ($SkillName in $SkillNames) {
    $Source = Join-Path $ForgeRoot "skills\$SkillName"
    $Target = Join-Path $SkillHome $SkillName
    if (!(Test-Path -LiteralPath (Join-Path $Source "SKILL.md"))) { throw "Missing Skill source: $Source" }
    if (Test-Path -LiteralPath $Target) { throw "Skill target already exists: $Target" }
    New-Item -ItemType Junction -Path $Target -Target $Source | Out-Null
}
```

POSIX 符号链接流程：

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

核心流程：

1. 先定位同时包含 `skills/`、`src/`、`pyproject.toml` 的仓库根目录。
2. 展示 `.agents/skills` 目标位置、所选的 `Python 3.11+` 解释器，以及独立的 `FFmpeg`/`FFprobe` 安装计划。
3. 在创建链接或安装任何包之前，请求用户明确确认核心安装。
4. 只创建四个 Skill 链接；只要任何目标已存在，就立即停止。
5. 只有在核心确认之后，才允许把 Python 包安装到用户选定的隔离环境中。
6. 验证 `.agents/skills` 下四个已链接 Skill 的 `SKILL.md` 都能正确解析。
7. 使用选定的 Python 解释器运行 launcher `--help`，确认 `src/` 共享运行时可被正确解析。

核心安装完成；没有安装任何可选工作流。

## 可选工作流

核心安装并不授予以下配置的任何默认安装权限。一次只处理一个配置。必须先询问是否启用；如果用户拒绝，就跳过该配置，不做探测，也不改动它的环境。

### ComfyUI MiniMax H3

#### 询问是否启用 ComfyUI MiniMax H3

在核心安装完成后，先询问是否启用本地可选的 ComfyUI MiniMax H3 工作流。如果用户拒绝，就立即停止该配置，不检查 `comfy-cli`、`Comfy MCP`、`h3-prompt-writing`、模型、节点或凭据。

#### 只读检查，不执行安装

只有在用户接受该配置后，才允许执行只读检查。检查所选 Python 解释器、`comfy --version`、所选 ComfyUI 工作区及该实例是否正在运行、当前 MCP 配置、`comfy-mcp` 命令是否已可用，以及 `$HOME/.agents/skills/h3-prompt-writing/SKILL.md` 是否已存在。在这个检查步骤中，不得创建链接、安装任何包，也不得下载任何内容。

#### 展示缺失组件计划

展示已安装版本与路径、任何冲突、每一个缺失组件、准备执行的精确命令、每一个目标路径，以及 `comfy-cli`、`Comfy MCP`、`h3-prompt-writing` 所需的全部下载项。附上当前官方 [Comfy MCP 安装说明](https://docs.comfy.org/agent-tools/mcp#installation) 与 [MiniMax H3 Skill 安装说明](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/README.md#installation) 链接。必须明确说明这一步仍然只是计划，尚未安装任何内容。

#### 确认可选安装

在展示缺失组件计划后，再次请求明确确认。如果用户没有批准这些精确命令、目标路径与下载项，就不得继续。

#### 只安装已批准的缺失组件

只安装用户批准的 `comfy-cli`、`Comfy MCP`、`h3-prompt-writing` 缺失部分。本步骤不得安装 H3 工作流节点，也不得安装 MiniMax H3 模型权重。安装后应通过重新检查版本、路径、命令可用性与 prompt Skill 链接目标来验证该已批准配置。

H3 工作流节点与 MiniMax H3 模型权重属于单独的可选安装。必须先展示许可证、下载大小、目标路径，以及精确的节点/模型标识符，然后再次请求确认。不得因为 Comfy MCP/H3 Skill 的确认而顺带下载它们。

### MiniMax Hailuo API

先询问是否启用 `MiniMax Hailuo API`。如果用户拒绝，就跳过且不做探测。如果用户接受，只检查 `MINIMAX_API_KEY` 是否存在；不得打印其值，也不得安装任何 CLI。展示无计费的预检或模型发现命令，以及 `provider-workflow.md` 已使用的官方 API 参考，然后在运行这些无计费检查之前再次请求确认。安装过程中绝不提交付费请求，也绝不发送生成请求。

### Jimeng API

先询问是否启用 `Jimeng API`。如果用户拒绝，就跳过且不做探测。如果用户接受，只检查 `JIMENG_ACCESS_KEY` 与 `JIMENG_SECRET_KEY` 是否存在；不得打印其值，也不得安装任何 CLI。展示仓库中的无计费预检命令，在执行这些命令前再次请求确认，并且绝不提交生成请求。

### CLI 兼容性

只有当用户明确要求 CLI 兼容性时，才评估 `mmx` 与 `dreamina`。除非在安装当时已经确认存在经过验证的第一方来源，并且已确认具备所需的视频命令，否则绝不能安装任一 CLI。否则应报告 `CLI auto-install unavailable`，并提供对应的 API 路线，但不得自动切换。

### Stable Audio 3

先询问是否启用 `Stable Audio 3`。如果用户拒绝，就跳过且不做探测，也不改动它的环境。如果用户接受，委托给 `../stable-audio-3/README.md`，并保留该文档中的目录选择确认、个人许可证/模型访问确认，以及执行安装步骤前所需的任何下载批准。
