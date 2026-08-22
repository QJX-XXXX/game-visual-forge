# Agent-Executable Installation Design

## Goal

Make Game Visual Forge installable by giving an Agent one repository document.
The Agent installs all four Forge Skills and the shared repository runtime, then
installs only the tool profiles the user selects. Ordinary asset-generation
workflows remain unable to install software.

The public video-to-sprite summary stays concise while naming every supported
source family:

- English: `Turn existing, ComfyUI MiniMax H3, MiniMax Hailuo, or Jimeng video into sprite frames.`
- Chinese: `将现有或由 ComfyUI MiniMax H3、海螺/MiniMax、即梦生成的视频转换为精灵帧。`

## Chosen Approach

Use a shared Agent-executable installation guide with thin Codex and Claude
entrypoints. Do not create a one-shot installer program and do not convert this
repository into a plugin in this change.

This approach was selected over:

1. A Codex plugin, which is a better long-term distribution unit but would
   restructure the repository and would not install FFmpeg, local models, or
   Claude dependencies by itself.
2. A monolithic installer script, which would need broad OS/package-manager
   support and would make account, license, and large-model boundaries harder to
   review.

The Agent guide is executable prose: it defines decisions, permitted mutations,
commands to discover at runtime from official documentation, validation, and
stopping conditions. The Agent performs the platform-specific operations using
the tools available in its current environment.

## Skill Installation

Keep the repository's `skills/` and `src/` layout intact because every launcher
resolves the shared Python package from the repository root.

The Agent must:

1. Resolve the current repository root or ask for an installation root before
   cloning/copying it.
2. Install all four Skill folders as discoverable links rather than copying one
   Skill in isolation.
3. For Codex, use the officially documented global `~/.agents/skills` directory
   or repository `.agents/skills` directory. For Claude, use its supported Skill
   directory while preserving links to the full repository.
4. Refuse to overwrite an existing Skill path. Inspect it and ask whether to
   reuse, update, or choose another destination.
5. Verify that each linked `SKILL.md`, launcher, and shared `src/` tree resolves
   from the installed location.
6. Restart or reload the target Agent after installation, then verify discovery
   and launcher help.

On Windows, prefer PowerShell directory junctions. On macOS/Linux, prefer
symbolic links. If links are unavailable, copy the full repository to the chosen
installation root and link only the Skill discovery entries to that preserved
root.

## Installation Profiles

The guide presents one required core profile and optional profiles. The Agent
asks for the desired profiles in one consolidated confirmation before mutating
the machine.

### Core Skill Pack

- All four Forge Skills and shared `src/` package.
- Python 3.11 or newer.
- Repository package and selected image/background extras in an isolated
  environment when the user requests local processing.
- FFmpeg and FFprobe for video/audio inspection and processing.
- Skill validation and launcher smoke tests.

### Video: Local ComfyUI MiniMax H3

- ComfyUI/comfy-cli and the first-party Comfy MCP connection.
- The official `h3-prompt-writing` Skill.
- A live ComfyUI preflight.
- MiniMax H3 workflow, node, and model checks only after the user has accepted
  applicable licenses and approved model download size/location.

### Video: MiniMax Hailuo API

- No provider CLI installation.
- Official API documentation, endpoint/region selection, and a preflight for
  `MINIMAX_API_KEY` supplied by the user.
- No test request that can incur cost.

### Video: Jimeng API

- No provider CLI installation.
- Official API documentation and a preflight for user-supplied
  `JIMENG_ACCESS_KEY` and `JIMENG_SECRET_KEY`.
- No test request that can incur cost.

### Video CLI Compatibility

`mmx` and `dreamina` remain compatibility backends only. The Agent may install
one only when the installation guide contains a verified first-party source and
the current official documentation still supports the required video commands.
Otherwise it reports that automated CLI installation is unavailable and offers
the corresponding API route. It must not install a similarly named community
package.

### Stable Audio 3

Delegate to the existing isolated Stable Audio 3 guide. License acceptance,
gated model access, model location, and large downloads remain explicit user
actions. The Agent can execute the remaining steps after those gates are met.

## Authority and Safety

An explicit request such as "follow the Game Visual Forge installation guide"
authorizes the Agent to perform the confirmed installation profiles. It does
not authorize unrelated system changes.

Before execution the Agent shows:

- target Agent and Skill directory;
- repository/runtime installation directory;
- selected profiles;
- package managers and persistent configuration files to be changed;
- external downloads, estimated sizes when available, and model/cache paths;
- account, API-key, license, and potential-cost gates.

The Agent may install packages and create Skill links after this confirmation.
It must stop for administrator elevation, destructive replacement, license
acceptance, account login, secrets, model downloads without a confirmed size and
location, or any paid request. Credentials never enter repository files or
command output.

Ordinary Forge Skills retain their `Never install` rules. They may point to the
Agent installation guide when a prerequisite is missing; they do not inherit
the installer's authority.

## Documentation Layout

- `install/agent/README.md`: authoritative Agent-executable workflow.
- `install/agent/README.zh-CN.md`: Chinese equivalent.
- `install/codex/README.md`: Codex entrypoint and discovery-specific notes.
- `install/claude/README.md`: Claude entrypoint and discovery-specific notes.
- Root English/Chinese README files: concise Skill descriptions and one Agent
  installation entrypoint.

Provider-specific procedures remain linked to official sources instead of
copying vendor manuals into the repository.

## Error Handling and Recovery

- Every installation operation starts with detection and is idempotent when the
  detected installation matches the requested version/path.
- An existing conflicting Skill link, repository, virtual environment, MCP
  entry, or executable causes a stop and explicit reuse/update/alternate-path
  choice; nothing is overwritten automatically.
- Partial installations produce a summary of completed, skipped, and blocked
  profiles plus the exact safe resume point.
- Authentication and preflight failures never trigger reinstall or backend
  switching.
- Unverified or unavailable CLI sources do not block API or existing-file
  routes.

## Validation

The Agent finishes by reporting, without secrets:

- resolved Skill paths and all four discovered names;
- repository and Python versions;
- launcher `--help` results;
- FFmpeg/FFprobe versions when the core local-processing profile was selected;
- Comfy MCP `server_info` and H3 Skill presence for the ComfyUI profile;
- credential presence booleans and no-charge preflight results for selected API
  profiles;
- Stable Audio offline preflight when selected;
- test and Skill-validator results.

Behavioral validation uses two Agent scenarios:

1. Install the core pack plus ComfyUI H3 on a machine with nothing configured.
   The Agent must ask for paths/profiles, stop at license or model gates, then
   resume and validate without installing unselected providers.
2. Install MiniMax and Jimeng API profiles. The Agent must explain that the APIs
   require credentials but no provider CLI, never submit a paid request, and
   leave CLI compatibility uninstalled without verified first-party sources.

