# Install Game Visual Forge with an Agent

[简体中文](README.zh-CN.md)

This guide is the authoritative core installation contract for an Agent-executable setup.

Core scope:

- Install all four Skills: `forge-2d-map`, `forge-2d-sprite`, `forge-text-audio`, and `forge-video-to-sprite`.
- Preserve `skills/`, `src/`, and `pyproject.toml` together from one repository root.
- Use Codex's discoverable `.agents/skills` path with linked Skill directories instead of copying one Skill in isolation.
- Require Python 3.11 or newer for the shared runtime, and plan `FFmpeg` plus `FFprobe` separately for local audio/video processing.

Authority and safety:

- Ask for core installation confirmation before creating links or installing packages.
- Refuse to overwrite an existing target; inspect it and choose another destination or stop.
- Validate `SKILL.md` exists before linking each Skill.
- This core flow does not install optional workflows, Comfy MCP, `h3-prompt-writing`, provider CLIs, models, custom nodes, credentials, or paid services.
- This core flow does not install optional workflows automatically after the core pack succeeds.

Before execution, show the user:

- the target Agent and the `.agents/skills` directory;
- the repository root that preserves `skills/`, `src/`, and `pyproject.toml`;
- the Python 3.11+ interpreter that will run the shared package;
- whether `FFmpeg` and `FFprobe` are already present or still need a separate OS-level install;
- the exact links and package-install locations that would be created after confirmation.

Windows PowerShell junction procedure:

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

POSIX symbolic-link procedure:

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

Core flow:

1. Resolve the repository root that contains `skills/`, `src/`, and `pyproject.toml`.
2. Show the `.agents/skills` destination, the chosen Python 3.11+ interpreter, and the separate `FFmpeg`/`FFprobe` plan.
3. Ask for explicit core installation confirmation before creating links or installing packages.
4. Create only the four Skill links, and stop immediately if any target already exists.
5. Install Python packages only after the core confirmation and only into a chosen isolated environment.
6. Verify all four linked `SKILL.md` files resolve from `.agents/skills`.
7. Run launcher `--help` with the chosen Python interpreter to confirm the shared runtime resolves from `src/`.

Core installation complete; no optional workflow was installed.

## Optional workflows

Core installation grants no authority for the profiles below. Handle one profile at a time. Ask whether to enable it; when declined, skip it without probing or changing its environment.

### ComfyUI MiniMax H3

#### Ask whether to enable ComfyUI MiniMax H3

Ask whether to enable the optional local ComfyUI MiniMax H3 workflow after the core install is complete. If the user declines, stop this profile immediately without checking `comfy-cli`, `Comfy MCP`, `h3-prompt-writing`, models, nodes, or credentials.

#### Inspect without installing

Inspect read-only only after the user accepts this profile. Check the selected Python interpreter, `comfy --version`, the selected ComfyUI workspace and whether that ComfyUI instance is running, the current MCP configuration, whether the `comfy-mcp` command is already available, and whether `$HOME/.agents/skills/h3-prompt-writing/SKILL.md` already exists. Do not create links, install packages, or download anything in this inspection step.

#### Show the missing-component plan

Show installed versions and paths, any conflicts, every missing component, the exact commands you would run, every destination path, and every download that would be required for `comfy-cli`, `Comfy MCP`, and `h3-prompt-writing`. Include the current official [Comfy MCP installation](https://docs.comfy.org/agent-tools/mcp#installation) and [MiniMax H3 Skill installation](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/README.md#installation) references. State clearly that this step is still a plan and that nothing has been installed yet.

#### Confirm the optional installation

Ask for a second explicit confirmation after presenting the missing-component plan. Do not continue if the user does not approve the exact commands, destinations, and downloads.

#### Install only approved missing components

Install only the approved missing pieces for `comfy-cli`, `Comfy MCP`, and `h3-prompt-writing`. Do not install H3 workflow nodes or MiniMax H3 model weights in this step. Validate the approved profile after installation by re-checking versions, paths, command availability, and the prompt-skill link target.

Workflow nodes and MiniMax H3 model weights are a separate optional install. Show license, download size, destination, and exact node/model identifiers, then ask again. Do not download them from the Comfy MCP/H3 Skill confirmation alone.

### MiniMax Hailuo API

Ask whether to enable `MiniMax Hailuo API`. If declined, skip it without probing. If accepted, inspect only whether `MINIMAX_API_KEY` is present, without printing the value and without installing any CLI. Show the no-charge preflight or model-discovery commands and the official API reference already used by `provider-workflow.md`, then ask for confirmation before running only those no-charge checks. Never submit a paid or generative request during installation.

### Jimeng API

Ask whether to enable `Jimeng API`. If declined, skip it without probing. If accepted, inspect only whether `JIMENG_ACCESS_KEY` and `JIMENG_SECRET_KEY` are present, without printing the values and without installing any CLI. Show the repository's no-charge preflight commands, ask for confirmation before running them, and never submit a generation request during installation.

### CLI compatibility

Evaluate `mmx` and `dreamina` only when the user explicitly asks for CLI compatibility. Never install either CLI unless a verified first-party source and the required video commands are both established at installation time. Otherwise report `CLI auto-install unavailable` and offer the corresponding API route without switching automatically.

### Stable Audio 3

Ask whether to enable `Stable Audio 3`. If declined, skip it without probing or changing its environment. If accepted, delegate to `../stable-audio-3/README.md`, preserve its directory-choice gate, preserve personal license/model-access confirmation, and preserve any required download approval before executing its installation steps.
