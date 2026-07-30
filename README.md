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

### HD background removal

For HD sprites generated on solid `#FF00FF`, install the default high-quality
backend with `pip install -e ".[background]"`. The runtime tries
BiRefNet-General on CUDA, retries on CPU, and uses deterministic chroma removal
only when rembg is unavailable or all available providers fail.

![HD background-removal comparison](assets/readme/rembg-production-comparison-on-gray.jpg)

The comparison uses one generated 1024 x 1536 source. A visible pixel has
alpha >= 8/255. The magenta ratio is the number of visible, magenta-like pixels
divided by all visible pixels, so it measures color contamination in the
extracted subject rather than empty canvas area.

| Result | Role | Magenta pixels | Visible pixels | Ratio |
| --- | --- | ---: | ---: | ---: |
| Chroma fallback | rembg unavailable; manual review required | 24,799 | 487,649 | 5.0854% |
| BiRefNet only | semantic intermediate, not a final export | 31,081 | 496,889 | 6.2551% |
| Default HD / Known-BG | recommended final output | 81 | 472,640 | 0.0171% |
| Optional PyMatting | explicit precision mode | 151 | 482,322 | 0.0313% |

Chroma fallback removes pixels close to the known key color. It is deterministic
and needs no model, but anti-aliased hair and fabric edges already contain mixed
foreground/magenta RGB, so a visible fringe remains. The default HD path combines
BiRefNet's semantic alpha with border-connected chroma evidence, then reconstructs
foreground color from the known magenta background; unstable low-alpha pixels use
nearby safe foreground colors. PyMatting builds a trimap from the same fused mask
and solves alpha/foreground separately. It is available with
`pip install -e ".[matting]"` and `"rembg_refinement": "pymatting"`, but remains
off by default because it adds cost and was not better on this sample. These
figures describe this validation image, not a universal model benchmark.

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
