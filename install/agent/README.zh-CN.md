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
