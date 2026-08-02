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

The package also includes opt-in Unity tests under `Tests/Editor` and
`Tests/PlayMode`. In the consuming project's `Packages/manifest.json`, enable
the package through `testables` and run the Unity Test Runner. EditMode checks
the imported Tile count, palette population, layer order, used cells, and
obstacle collider. PlayMode contains a runtime fixture check; the current demo
scene was additionally verified through Unity MCP with three runtime Tilemaps,
renderers, and a collider. Re-importing both example bundles twice kept 16
Tiles and the same Tilemap Prefab GUID for each bundle.

#### Tile size modes

Tile requests use exactly one of these modes:

| User request | Mode | Final size |
| --- | --- | --- |
| no size | `preset_32` | 32×32 |
| 16×16 | `preset_16` | 16×16 |
| any other positive width×height | `custom` | requested dimensions |

No-size requests default to `preset_32`. A requested 16×18 tileset uses
`custom`; 16×18 is supported only when requested and is not a preset. Minimal
request examples:

```json
{"tile_size_mode":"preset_16"}
{"tile_size_mode":"preset_32"}
{"tile_size_mode":"custom","tile_width":16,"tile_height":18}
```

All atlas pages in one request share one tile size. Unity derives Grid Cell Size
from the dimensions and PPU as
`(tile_width / pixels_per_unit, tile_height / pixels_per_unit, 1)`.

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

##### Adaptive River Crossing Map (32-Tile / 2-page HD)

This is the accepted `adaptive-river-crossing-map-tilemap` validation case. It is
separate from `AutumnCreekMapDemo` and `StandardSimpleMapDemo`; those existing
maps remain reference examples. The adaptive case reuses the validated Autumn
Creek Tile grammar intentionally, so the multi-page and dynamic Tile-count
contract is tested without introducing incompatible visual semantics.

The 24x16 map contains a four-cell-wide horizontal creek, a vertical stone path
and bridge crossing, a small upper-right pond, and coherent grass, leaf, tree,
rock, and lantern details. It exports 32 Tile assets across two 4x4 atlas pages
and three layers (`ground`, `details`, and `obstacles`). Page 02 uses alternate
Tile IDs with the same visual grammar to validate page binding and idempotent
multi-page import. Page 02 is a deterministic, subtly color-shifted variant of
the same atlas grammar, so the two page files are distinct while remaining
visually compatible; this is not presented as 32 unique visual motifs.

![Adaptive River Crossing map preview](assets/readme/adaptive-river-crossing-map-preview.png)

![Adaptive River Crossing seam preview](assets/readme/adaptive-river-crossing-map-seam-preview.png)

![Adaptive River Crossing Tile usage](assets/readme/adaptive-river-crossing-map-tile-usage-preview.png)

![Adaptive River Crossing in Unity Game View](assets/readme/adaptive-river-crossing-map-unity-game-view.png)

![Adaptive River Crossing in Unity Scene View](assets/readme/adaptive-river-crossing-map-unity-scene-view.png)

Validation result:

- Python deterministic and manual visual checks passed: seams, readability, layer order, collision layer, adjacency, clipping, and no text/watermark.
- All 32 declared Tile IDs are used; no unused, clipped, or invalid-adjacency Tile IDs remain.
- Assets-only Unity import created two atlas textures, 32 Tile assets, a Palette prefab, and a Tilemap prefab without changing the Scene layout.
- The clean Assets-only run reported `scene_action=unchanged` and `scene_dirty=false`.
- Repeated Import and Place was idempotent: the first placement reported `scene_action=placed`, the second reported `scene_action=updated`; both reported stable resource GUIDs and the final hierarchy contains one v8 adaptive scene instance.
- The Unity import report records the two atlas pages, 32 Tiles, three layers, and generated v8 prefab paths. The explicit placement test leaves the editor Scene dirty; the Scene is not auto-saved.
- The [Unity acceptance summary](assets/readme/adaptive-river-crossing-map-unity-acceptance-summary.json) preserves the clean Assets-only result (`had_existing_assets=false`, `scene_action=unchanged`), the first placement (`placed`), the second idempotent update (`updated`), stable GUIDs, and the final live hierarchy check (`AutumnCreekMapDemo=false`, `StandardSimpleMapDemo=false`, one adaptive instance).

Artifacts: [map preview](assets/readme/adaptive-river-crossing-map-preview.png),
[seam preview](assets/readme/adaptive-river-crossing-map-seam-preview.png),
[Tile usage](assets/readme/adaptive-river-crossing-map-tile-usage-preview.png),
[map quality report](assets/readme/adaptive-river-crossing-map-map-quality-report.json),
[asset manifest](assets/readme/adaptive-river-crossing-map-asset-manifest.json),
and [Unity import report](assets/readme/adaptive-river-crossing-map-unity-import-report.json),
plus the [Unity acceptance summary](assets/readme/adaptive-river-crossing-map-unity-acceptance-summary.json).

### Adaptive Tilemap quality workflow

Tile mode has two profiles: `standard_16` keeps the legacy single 4x4 atlas
and up to 16 Tiles; `adaptive_hd` supports 16, 32, or 48 Tiles across one to
three 4x4 atlas pages. Use repeated `--atlas-page page-01=path.png` arguments
to bind each page explicitly. The processor emits map, seam, usage, metrics,
and `map-quality-report.json` artifacts. Unity provides **Assets-only** import
and explicit **Import and Place**; the latter reuses prefab instances and does
not save the Scene automatically. `Reports/unity-import-report.json` records
the Python report SHA-256, page count, Tile count, Palette, Prefab, and scene
action. Collision/mask data is optional spatial map data; gameplay logic is
outside scope. Routine runs never rewrite README files.

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
