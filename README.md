# Game Visual Forge

Independent Agent Skills for generating 2D Sprites, production-oriented 2D maps,
and Video -> 2D Sprite animation.

This repository is a clean-room implementation. It does not depend on
`agent-sprite-forge` and is not a Codex Plugin.

M0 contains contracts, safe job state, zero-network planning, and Skill
foundations. It does not call real generation providers.

The three M0 Skills are:

- `generate-2d-sprite` — example request: “Plan a dry-run for a side-view hero run cycle with 8 frames.”
- `generate-2d-map` — example request: “Plan a dry-run for a layered village map with collision notes.”
- `video-to-2d-sprite` — example request: “Plan a dry-run to turn an existing MP4 attack animation into a sprite sheet.”

Manual installation guides:

- [Codex install guide](install/codex/README.md)
- [Claude install guide](install/claude/README.md)

Project references:

- [Design spec](docs/superpowers/specs/2026-07-30-game-visual-forge-agent-skills-design.md)
- [Implementation plan](docs/superpowers/plans/2026-07-30-game-visual-forge-m0-foundation.md)

M0 limitations:

- zero-network only
- no provider execution
- no dependency installation
- no credential loading or credential persistence
- no FFmpeg execution
- no rembg execution
- no media generation

Routing rules in M0:

- Preferred native path: ask for Agent-native tooling first when a later milestone supports real generation.
- Third-party path: if native support is unavailable or rejected, the user must explicitly choose the third-party route each time.
- Future third-party adapters: Dreamina and Wanxiang are planned adapter targets, but they are not implemented in M0.
- Future Video -> Sprite scope: later milestones may cover provider-backed video generation, existing MP4 ingestion, extraction, cleanup, alignment, and export workflows. M0 only plans the dry-run.

Safety and clean-room rules:

- This repository is a clean-room implementation and must not import or vendor implementation from `agent-sprite-forge`.
- `.codex-plugin/` must not exist in this repository.
- Credentials, API keys, cookies, signed URLs, and provider secrets must not be stored in manifests, job state, logs, or examples.
- Manual installation only: M0 does not install dependencies, providers, FFmpeg, rembg, or credentials.

Verification commands:

```powershell
python -m unittest discover -s tests -v
python -m game_visual_forge dry-run --brief examples/briefs/sprite-auto.json --out-dir outputs/demo --now 2026-07-30T00:00:00Z
```
