# Game Visual Forge

English | [简体中文](README.zh-CN.md)

Game Visual Forge is an independent set of Agent Skills for generating 2D
sprites, production-oriented 2D maps, and Video -> 2D Sprite animation.

### M0 scope

M0 provides versioned contracts, safe job state, zero-network planning, and
three Skill foundations. It does not call real generation providers or create
media.

The three Skills are:

- `generate-2d-sprite` — plan a dry-run for a side-view hero run cycle.
- `generate-2d-map` — plan a layered village map with collision notes.
- `video-to-2d-sprite` — plan conversion of an existing MP4 into a sprite sheet.

### M1 Generate 2D Sprite

M1 adds a versioned `SpriteRequest`, explicit `CapabilityRouter` decisions,
provider confirmation gates, local image ingestion, deterministic frame/sheet/GIF
processing, `QualityReport`, and `AssetManifest`.

The local workflow is:

```powershell
python skills/generate-2d-sprite/scripts/run.py sprite plan `
  --request <request.json> --out-dir <output> --now <utc-rfc3339>
python skills/generate-2d-sprite/scripts/run.py sprite route `
  --request <output/sprite-request.json> --capabilities <capabilities.json> `
  --out <output/source-decision.json> --state <output/job-state.json> `
  --now <utc-rfc3339>
```

Use `sprite ingest`, `sprite process`, and `sprite validate` to continue an
existing-image or Agent-native workflow. Pillow is optional for local image
processing and rembg is an optional background-removal backend; neither is
installed automatically. The repository defines Dreamina and Wanxiang CLI
boundaries but does not include a default or real paid provider adapter.

### Routing and safety

- native supported -> native path
- native unsupported -> user chooses third party/local/existing
- native failure or quality rejection -> defined fallback/choice only after confirmation
- every Dreamina/Wanxiang third-party attempt has explicit provider/model/parameter/cost confirmation and no silent resubmission
- `submission_unknown` may only be queried or manually reconciled.
- M1 does not implement maps, video, MP4, FFmpeg, automatic dependency installation, or silent paid retries.

### Installation

- [Codex installation guide](install/codex/README.md)
- [Claude installation guide](install/claude/README.md)

### Verification

```powershell
python -m unittest discover -s tests -v
python skills/generate-2d-sprite/scripts/run.py dry-run `
  --brief examples/briefs/sprite-auto.json `
  --out-dir outputs/demo --now 2026-07-30T00:00:00Z
```
