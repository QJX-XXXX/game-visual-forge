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
