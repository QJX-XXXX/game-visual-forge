# Game Visual Forge

English | [简体中文](README.zh-CN.md)

Game Visual Forge is an independent set of Agent Skills for generating 2D
sprites, production-oriented 2D maps, and Video -> 2D Sprite animation.

### M0 scope

M0 provides versioned contracts, safe job state, zero-network planning, and
three Skill foundations. It does not call real generation providers or create
media.

The three Skills are:

- `forge-2d-sprite` — plan a dry-run for a side-view hero run cycle.
- `forge-2d-map` — plan a layered village map with collision notes.
- `forge-video-to-sprite` — plan conversion of an existing MP4 into a sprite sheet.

### M1 Generate 2D Sprite

M1 adds a versioned `SpriteRequest`, explicit `CapabilityRouter` decisions,
provider confirmation gates, local image ingestion, deterministic frame/sheet/GIF
processing, `QualityReport`, and `AssetManifest`.

The local workflow is:

```powershell
python skills/forge-2d-sprite/scripts/run.py sprite plan `
  --request <request.json> --out-dir <output> --now <utc-rfc3339>
python skills/forge-2d-sprite/scripts/run.py sprite route `
  --request <output/sprite-request.json> --capabilities <capabilities.json> `
  --out <output/source-decision.json> --state <output/job-state.json> `
  --now <utc-rfc3339>
```

Use `sprite ingest`, `sprite process`, and `sprite validate` to continue an
existing-image or Agent-native workflow. Pillow is optional for local image
processing and rembg is an optional background-removal backend; neither is
installed automatically. The repository defines Dreamina and Wanxiang CLI
boundaries but does not include a default or real paid provider adapter.

### M2 2D map foundation

M2 adds a structured `MapRequest` and an offline map pipeline for existing base
images: `map plan -> map route -> map ingest -> map process -> map validate`.
The first batch produces `base-map.png`, `map-runtime.json`,
`walkable-mask.png`, `collision-mask.png`, and `debug-preview.png`.

Map geometry uses integer pixel coordinates. The walkable mask is
`walk_bounds - blockers`; the collision mask is its inverse. Zones are recorded
in runtime metadata and the debug preview but do not change collision. A spawn
point must be inside the canvas and on an unblocked walkable pixel before the
asset can pass deterministic validation. Visual review remains a required
human confirmation before publishing.

```powershell
python skills/forge-2d-map/scripts/run.py map plan `
  --request <map-request.json> --out-dir <output> --now <utc-rfc3339>
python skills/forge-2d-map/scripts/run.py map route `
  --request <output>/map-request.json --capabilities <capabilities.json> `
  --out <output>/source-decision.json --state <output>/job-state.json `
  --now <utc-rfc3339>
python skills/forge-2d-map/scripts/run.py map ingest `
  --request <output>/map-request.json --decision <output>/source-decision.json `
  --image <source.png> --repo-root <repo> --out <output>/raw-image.json `
  --state <output>/job-state.json --now <utc-rfc3339>
python skills/forge-2d-map/scripts/run.py map process `
  --request <output>/map-request.json --raw-image <output>/raw-image.json `
  --repo-root <repo> --out-dir <output> --state <output>/job-state.json `
  --now <utc-rfc3339>
python skills/forge-2d-map/scripts/run.py map validate `
  --request <output>/map-request.json --raw-image <output>/raw-image.json `
  --processing-result <staging>/processing-result.json --repo-root <repo> `
  --staging-dir <staging> --final-dir <output>/final `
  --state <output>/job-state.json --now <utc-rfc3339>
```

M2 keeps paid-provider calls behind explicit provider/model/parameter/cost
confirmation and does not silently retry unknown submissions.

### Tile mode and Unity Tilemap

Tile mode treats a generated or existing tileset PNG as the visual source and
turns it into a neutral, versioned delivery bundle. The bundle contains
`tileset.png`, `tileset-slices.json`, `tilemap-placement.json`,
`unity-tilemap.json`, and `tilemap-preview.png`. Cell arrays in the request use
top-left row-major order; Unity-facing slice rectangles and placements use a
bottom-left origin.

```powershell
python skills/forge-2d-map/scripts/run.py map tile plan `
  --request <tilemap-request.json> --out-dir <output> --now <utc-rfc3339>
python skills/forge-2d-map/scripts/run.py map tile route `
  --request <output>/tilemap-request.json --capabilities <capabilities.json> `
  --out <output>/source-decision.json --state <output>/job-state.json `
  --now <utc-rfc3339>
```

Continue with `map tile ingest`, `map tile process`, and `map tile validate`.
The Unity 2022.3 LTS / Unity 6 Editor importer is provided as the local package
`integrations/unity/com.game-visual-forge.tilemap`. Install it explicitly with
Unity Package Manager's **Add package from disk** command. The package declares
`com.unity.2d.sprite` and `com.unity.2d.tilemap`; the importer itself never
installs packages or modifies the open Scene. From **Tools > Game Visual Forge >
Import Tilemap Bundle**, select `unity-tilemap.json`. It creates or updates the
sliced Sprite texture, Tile assets, Tile Palette, and layered Tilemap Prefab
under the bundle's `generated_root`. Defaults are Point filtering, uncompressed
textures, and one tile per Unity unit when pixels-per-unit equals tile width.

#### Unity success examples

##### Standard Simple Forest Map

The first end-to-end map run uses a 20x14 top-down forest layout with a vertical
dirt path, a 3x5 pond with a bridge, trees, rocks, and flowers. It demonstrates
the baseline two-layer Tilemap delivery.

![Standard Simple Forest Map in Unity Game View](assets/readme/standard-simple-map-game-view.png)

![Standard Simple Forest Map pipeline preview](assets/readme/standard-simple-map-pipeline-preview.png)

![Standard Simple Forest Map in Unity Scene View](assets/readme/standard-simple-map-scene-view.png)

Run result:

- 16 generated Tiles in a 4x4 atlas; 20x14 map; Point filtering; 256 pixels per Unity unit.
- 280 ground placements and 41 detail placements across two layers.
- Unity import and scene placement succeeded; deterministic and visual checks passed.
- Artifacts: [Unity bundle](assets/readme/standard-simple-map-unity-tilemap.json), [quality report](assets/readme/standard-simple-map-quality-report.json), and [tilemap placement data](assets/readme/standard-simple-map-tilemap-placement.json).

##### Autumn Creek Map

The second end-to-end map run uses a generated 4x4 autumn Tileset to build a
24x16 top-down creek crossing. The vertical stone path crosses a four-cell-wide
creek on a wooden bridge; trees, rocks, leaf patches, and lanterns are delivered
as separate Tilemap layers.

![Autumn Creek Map in Unity Game View](assets/readme/autumn-creek-map-game-view.png)

![Autumn Creek Map pipeline preview](assets/readme/autumn-creek-map-pipeline-preview.png)

![Autumn Creek Map in Unity Scene View](assets/readme/autumn-creek-map-scene-view.png)

Run result:

- 16 generated Tiles in a 4x4, 1024x1024 atlas; Point filtering; 256 pixels per Unity unit.
- 384 ground placements, 28 detail placements, and 22 obstacle placements across three layers.
- The `tree-canopy` Tile was regenerated as a complete, centered single-cell tree with transparent margins; all Unity tree placements were re-imported and re-captured.
- Unity import succeeded with `AutumnCreekMapDemo` in `Assets/Scenes/SampleScene.unity`.
- Deterministic checks passed: source dimensions, readable artifacts, raster dimensions, and Unity bundle contract.
- Manual visual checks passed: seams, readability, layer order, collision layer, and no text/watermark.
- The `obstacles` Tilemap has a `TilemapCollider2D`; the saved scene is clean after import.

Artifacts: [Unity bundle](assets/readme/autumn-creek-map-unity-tilemap.json),
[quality report](assets/readme/autumn-creek-map-quality-report.json),
[Tileset prompt](assets/readme/autumn-creek-tileset.prompt.txt),
[tree replacement prompt](assets/readme/tree-canopy-replacement.prompt.txt),
and [tilemap placement data](assets/readme/autumn-creek-map-tilemap-placement.json).

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

### Optional delivery normalization

Set `delivery_normalization` when a game needs a consistently sized, anchored
delivery copy. The normalizer keeps the regular transparent `frames/` output,
then crops each frame to its visible alpha bounds, applies one shared LANCZOS
scale for the whole animation, and exports a second bundle under `delivery/`.
Use `feet` for grounded characters and `center` for props or hovering assets.

```json
"delivery_normalization": {
  "canvas_width": 1024,
  "canvas_height": 1024,
  "anchor": "feet",
  "fit_scale": 0.88
}
```

This is a delivery-layout step, not a background-removal improvement: it can
make tiny color fringes less visible but may soften fine antennae, fingers, or
hair. The manifest records the source bounds and shared scale for the delivery
bundle.

### Routing and safety

- native supported -> native path
- native unsupported -> user chooses third party/local/existing
- native failure or quality rejection -> defined fallback/choice only after confirmation
- every Dreamina/Wanxiang third-party attempt has explicit provider/model/parameter/cost confirmation and no silent resubmission
- `submission_unknown` may only be queried or manually reconciled.
- M2 does not implement video, MP4, FFmpeg, automatic dependency installation, or silent paid retries.

### Installation

- [Codex installation guide](install/codex/README.md)
- [Claude installation guide](install/claude/README.md)

### Verification

```powershell
python -m unittest discover -s tests -v
python skills/forge-2d-sprite/scripts/run.py dry-run `
  --brief examples/briefs/sprite-auto.json `
  --out-dir outputs/demo --now 2026-07-30T00:00:00Z
```
