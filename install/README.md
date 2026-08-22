# Game Visual Forge Installation Guide

[简体中文](README.zh-CN.md)

This is the single installation guide for the repository. It supports two
paths: copy the Agent request below for a step-by-step installation, or follow
the manual procedure. The repository contains four core Skills; optional
providers and runtimes are separate opt-in profiles.

## Copy this request to an Agent

```text
Install Game Visual Forge from https://github.com/QJX-XXXX/game-visual-forge.git
using the repository's unified installation guide. Work step by step and show
me every command before you run it. First confirm the repository root,
destination, Python 3.11+ interpreter, FFmpeg, FFprobe, and the Agent Skill
discovery directory. Preserve skills/, src/, and pyproject.toml together.
Ask me to confirm the core installation before cloning, creating links, making
a virtual environment, or installing packages. Then install/link exactly these
four Skills: forge-2d-map, forge-2d-sprite, forge-text-audio, and
forge-video-to-sprite. Refuse to overwrite existing Skill targets; verify every
SKILL.md and run the launcher --help checks. Do not install or probe optional
Comfy MCP, h3-prompt-writing, provider CLIs, models, nodes, credentials, or
paid services unless I explicitly ask to enable that profile. For an optional
profile, ask whether to enable it, inspect read-only, show the missing-component
plan, ask for a second confirmation, and install only approved missing pieces.
For ComfyUI MiniMax H3, require a separate license, size, and destination
confirmation before any model or node download. Report the commands, paths,
results, and anything still requiring my action.
```

The Agent must not interpret this request as permission to accept licenses,
print secrets, submit paid generation requests, or overwrite an existing
installation.

## Core repository and Skill scope

The core package is the intact repository plus these four Skill directories:

- `forge-2d-map`
- `forge-2d-sprite`
- `forge-text-audio`
- `forge-video-to-sprite`

Keep `skills/`, `src/`, and `pyproject.toml` under the same repository root.
Copying one Skill directory by itself is not a supported installation because
the launcher resolves the shared runtime from `src/`.

## Manual installation

### 1. Check prerequisites

Git is needed to obtain the repository. Use Python 3.11 or newer for the shared
runtime. FFmpeg and FFprobe are required for local video/audio processing.
Check them without changing the machine:

```powershell
git --version
python --version
ffmpeg -version
ffprobe -version
```

On POSIX systems use the same commands with `python3` if `python` is not
available. Install missing operating-system tools through their official
channels before continuing.

### 2. Obtain or reuse the repository

For a new checkout:

```powershell
git clone https://github.com/QJX-XXXX/game-visual-forge.git
Set-Location game-visual-forge
```

If the repository already exists, run `git rev-parse --show-toplevel`, confirm
that it contains `skills/`, `src/`, and `pyproject.toml`, and keep that root
intact. Do not clone over an existing directory or discard local changes.

Create an isolated Python environment after confirming the destination:

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -e .
```

POSIX equivalent:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

### 3. Link the four Skills

Codex commonly discovers global Skills under `$HOME/.agents/skills`. Claude
uses `SKILL.md` as its authority; if the current Claude environment supports
the same directory, use the same links, otherwise use its documented Skill
directory and keep links back to this intact repository. `agents/openai.yaml`
is metadata for Codex compatibility, not executable instructions.

Windows PowerShell junctions (refuse existing targets):

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

POSIX symbolic links:

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

### 4. Verify and restart

Confirm every link resolves to a `SKILL.md`, then run:

```powershell
python skills/forge-2d-map/scripts/run.py --help
python skills/forge-2d-sprite/scripts/run.py --help
python skills/forge-video-to-sprite/scripts/run.py --help
python -m unittest discover -s tests -q
```

Restart the Agent session so Skill discovery reloads. To uninstall the core
links, remove only the four links under `.agents/skills`; do not delete the
repository or its `skills/` and `src/` directories.

## Optional workflow gates

Core installation does not install optional workflows. For every profile:

1. Ask whether to enable it.
2. If declined, skip it without probing or changing its environment.
3. If accepted, inspect read-only.
4. Show versions, paths, missing components, exact commands, destinations, and downloads.
5. Ask for a second installation confirmation.
6. Install only the approved missing pieces.
7. Validate the profile.

### ComfyUI MiniMax H3

#### Ask whether to enable ComfyUI MiniMax H3

Ask whether to enable ComfyUI MiniMax H3. After an explicit yes, inspect
Python, `comfy --version`, the selected ComfyUI workspace/running state, MCP
configuration, `comfy-mcp`, and `$HOME/.agents/skills/h3-prompt-writing/SKILL.md`
without installing. Present the missing-component plan before a second
confirmation. H3 workflow nodes and model weights require a separate third
confirmation with license, download size, destination, and exact identifiers.

#### Inspect without installing

The inspection is read-only and must not create links, install packages, or
download content.

#### Show the missing-component plan

Show installed versions, paths, conflicts, missing components, exact commands,
destinations, and downloads before any installation confirmation.

#### Confirm the optional installation

Ask for a second explicit confirmation of that exact plan.

#### Install only approved missing components

Install only the approved missing `comfy-cli`, Comfy MCP, or
`h3-prompt-writing` components, then validate them. Model and node downloads
remain behind the separate third confirmation described above.

### MiniMax Hailuo, Jimeng, and CLI compatibility

The MiniMax Hailuo API profile checks only `MINIMAX_API_KEY`; the Jimeng API
profile checks only `JIMENG_ACCESS_KEY` and `JIMENG_SECRET_KEY`. Never print or
store secret values, install a provider CLI, or send a paid/generative request
during installation. `mmx` and `dreamina` require a verified first-party
source and required video commands; otherwise report `CLI auto-install unavailable`
and offer the API route.

## Independent setup links

These are separate runtime or external dependency guides, not part of the
four core repository Skills:

- [Stable Audio 3 setup](stable-audio-3/README.md)
- [Comfy MCP official installation](https://docs.comfy.org/agent-tools/mcp#installation)
- [MiniMax H3 Prompt Writing Skill official installation](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/README.md#installation)
