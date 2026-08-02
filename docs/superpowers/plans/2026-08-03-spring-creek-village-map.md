# Spring Creek Village Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从零生成并验证一套 48 Tile、三页图集的春日村落地图，将其作为可行走、可碰撞、带六个建筑入口元数据的三层 Unity Tilemap Prefab 导入并放置到 `2DMirrorDemo` 当前场景。

**Architecture:** 先扩展 Python 合同、处理、质量门禁和 Unity 导入合同，让建筑入口与桥梁连通性一样成为请求到交付包的可验证数据；随后为本次运行建立审计包，按 `plan -> route -> image generation -> ingest -> process -> validate -> visual review -> Unity Import and Place -> Unity acceptance` 执行。所有图像均由本次内置图像生成得到，生成的大图只做固定 4x4 网格的 nearest-neighbor 归一化，不换槽、不重绘。

**Tech Stack:** Python 3.11+、Pillow、`unittest`/`pytest`、Game Visual Forge CLI、内置 `image_gen`、Unity 2022.3+、C# Editor API、Unity MCP。

## Global Constraints

- 设计规格是 [2026-08-03-spring-creek-village-map-design.md](../specs/2026-08-03-spring-creek-village-map-design.md)，实现不得悄悄偏离它。
- 当前工作树已有桥梁合同、质量验证、Skill 和 README 相关未提交修改。实施前先记录 `git status --short` 和相关 diff；不覆盖、不回退、不把无关 README/验收资产混入本次提交。
- 所有源代码编辑使用 `apply_patch`。每次只暂存已核对的路径或 hunk，并在提交前执行 `git diff --cached --check` 与 `git diff --cached --name-only`。
- 本次运行根目录固定为 `outputs/spring-creek-village-20260803`；不得读取旧运行的图集、placement、预览或 Unity 截图作为输入。
- 图像生成失败、未知状态、错槽、文字/水印、质量 `needs_attention` 或 `failed` 时立即保留证据并停下等待用户决定；不得自动改提示词或重试。
- 不创建室内地图、角色、NPC、出生点、村外出口或传送运行时代码。
- 不安装或升级 Unity 包。只使用 `2DMirrorDemo` 已安装的 2D Sprite、Tilemap 与 Game Visual Forge importer。
- 常规运行不修改 README，也不伪造报告、截图、哈希或 Unity 状态。

---

## Task 1: Add deterministic 4x4 atlas normalization

**Files:**

- Create: `skills/forge-2d-map/scripts/normalize_tile_atlas.py`
- Create: `tests/test_normalize_tile_atlas.py`

- [ ] **Step 1: Write failing normalization tests**

```python
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from importlib.util import module_from_spec, spec_from_file_location

from PIL import Image

SCRIPT = Path(__file__).parents[1] / "skills" / "forge-2d-map" / "scripts" / "normalize_tile_atlas.py"
SPEC = spec_from_file_location("normalize_tile_atlas", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
normalize_atlas = MODULE.normalize_atlas


class NormalizeTileAtlasTests(unittest.TestCase):
    def test_resizes_each_cell_without_reordering(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.png"
            output = root / "normalized.png"
            image = Image.new("RGBA", (1024, 1024))
            colors = []
            for row in range(4):
                for column in range(4):
                    color = (column * 50, row * 50, 100 + row * 4 + column, 255)
                    colors.append(color)
                    image.paste(color, (column * 256, row * 256, (column + 1) * 256, (row + 1) * 256))
            image.save(source)

            report = normalize_atlas(source, output, columns=4, rows=4, tile_width=32, tile_height=32)

            self.assertEqual(report["source_size"], [1024, 1024])
            self.assertEqual(report["output_size"], [128, 128])
            with Image.open(output) as normalized:
                self.assertEqual(normalized.size, (128, 128))
                for index, color in enumerate(colors):
                    x = (index % 4) * 32 + 16
                    y = (index // 4) * 32 + 16
                    self.assertEqual(normalized.getpixel((x, y)), color)

    def test_rejects_source_that_cannot_split_evenly(self) -> None:
        with TemporaryDirectory() as temp:
            source = Path(temp) / "bad.png"
            Image.new("RGBA", (1023, 1024)).save(source)
            with self.assertRaisesRegex(ValueError, "divisible"):
                normalize_atlas(source, Path(temp) / "out.png", columns=4, rows=4, tile_width=32, tile_height=32)
```

Run: `python -m unittest tests.test_normalize_tile_atlas -v`

Expected: FAIL because the module does not exist.

- [ ] **Step 2: Implement the reusable helper and CLI**

The module must expose:

```python
def normalize_atlas(
    source: Path,
    output: Path,
    *,
    columns: int,
    rows: int,
    tile_width: int,
    tile_height: int,
) -> dict[str, object]:
    """Split a source grid, resize cells with NEAREST, and preserve row-major order."""
```

Implementation rules:

- Open as RGBA.
- Require positive dimensions and exact divisibility by `columns` and `rows`.
- Crop each source cell independently, resize it with `Image.Resampling.NEAREST`, and paste at the same row-major destination cell.
- Create the parent directory and save a PNG.
- Return `source`, `output`, `columns`, `rows`, `source_cell_size`, `source_size`, `tile_size`, and `output_size` as JSON-compatible values.
- CLI arguments are `--source`, `--output`, `--columns`, `--rows`, `--tile-width`, `--tile-height`; print the report as UTF-8 JSON.

- [ ] **Step 3: Verify the helper**

Run: `python -m unittest tests.test_normalize_tile_atlas -v`

Expected: 2 tests pass.

Run: `python -m pytest tests/test_normalize_tile_atlas.py -q`

Expected: PASS with no warnings introduced by this module.

- [ ] **Step 4: Commit only normalization files**

```powershell
git add -- skills/forge-2d-map/scripts/normalize_tile_atlas.py tests/test_normalize_tile_atlas.py
git diff --cached --check
git commit -m "feat: normalize generated tile atlas pages"
```

## Task 2: Make building entrances a first-class tilemap contract

**Files:**

- Modify: `src/game_visual_forge/contracts/tilemap.py`
- Modify: `src/game_visual_forge/contracts/__init__.py`
- Modify: `tests/test_tilemap_contract.py`

- [ ] **Step 1: Add failing contract tests**

Add `BuildingEntrance` and `TileSemanticRole` to the imports, then add tests that construct a 3x2 request whose `structures` layer contains a `wall-doorway` tile:

```python
def test_building_entrances_round_trip(self) -> None:
    request = make_tilemap_request()
    doorway = TileDefinition(
        "wall-doorway",
        1,
        1,
        collider_type=TileColliderType.NONE,
        semantic_role=TileSemanticRole.DOORWAY,
    )
    updated = TileMapRequest(**{
        **request.__dict__,
        "tiles": (*request.tiles[:-1], doorway),
        "layers": (
            request.layers[0],
            TileLayer("structures", 10, True, (None, "wall-doorway", None, None, None, None)),
        ),
        "building_entrances": (
            BuildingEntrance("inn-entrance", "structures", 1, 0, "interiors/inn", "entry"),
        ),
    })
    self.assertEqual(updated.to_dict()["building_entrances"][0]["cell"], {"x": 1, "y": 0})
    self.assertEqual(TileMapRequest.from_dict(updated.to_dict()), updated)

def test_building_entrance_requires_walkable_doorway_cell(self) -> None:
    request = make_tilemap_request()
    bad_cases = (
        BuildingEntrance("bad-layer", "missing", 0, 0, "interiors/inn", "entry"),
        BuildingEntrance("bad-bounds", "ground", 3, 0, "interiors/inn", "entry"),
        BuildingEntrance("bad-role", "ground", 0, 0, "interiors/inn", "entry"),
    )
    for entrance in bad_cases:
        with self.assertRaises(ValueError):
            TileMapRequest(**{**request.__dict__, "building_entrances": (entrance,)})
```

Also add explicit cases for duplicate entrance IDs, an empty placement cell, and a `DOORWAY` tile whose collider is `GRID`.

Run: `python -m unittest tests.test_tilemap_contract.TileMapContractTests -v`

Expected: FAIL because `BuildingEntrance` and `DOORWAY` are absent.

- [ ] **Step 2: Implement the contract**

Add the enum member:

```python
class TileSemanticRole(StrEnum):
    # existing members remain unchanged
    DOORWAY = "doorway"
```

Add the immutable contract:

```python
@dataclass(frozen=True)
class BuildingEntrance:
    entrance_id: str
    layer_id: str
    x: int
    y: int
    target_scene_id: str
    target_spawn_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.entrance_id,
            "layer_id": self.layer_id,
            "cell": {"x": self.x, "y": self.y},
            "target_scene_id": self.target_scene_id,
            "target_spawn_id": self.target_spawn_id,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BuildingEntrance":
        cell = value["cell"]
        return cls(
            entrance_id=value["id"],
            layer_id=value["layer_id"],
            x=cell["x"],
            y=cell["y"],
            target_scene_id=value["target_scene_id"],
            target_spawn_id=value["target_spawn_id"],
        )
```

Validate slug-like entrance IDs, non-empty layer/target IDs, non-negative integer coordinates, and add `building_entrances: tuple[BuildingEntrance, ...] = ()` to `TileMapRequest`. In `TileMapRequest.__post_init__`, require:

- unique entrance IDs;
- referenced layer exists;
- coordinate is inside the map;
- referenced cell is not `None`;
- referenced tile has `semantic_role == TileSemanticRole.DOORWAY`;
- referenced tile has `collider_type == TileColliderType.NONE`.

Serialize the tuple under `building_entrances`, parse a missing key as `()`, and export `BuildingEntrance` from `contracts/__init__.py`.

- [ ] **Step 3: Verify contract compatibility**

Run: `python -m unittest tests.test_tilemap_contract -v`

Expected: all contract tests pass, including legacy payloads with no `building_entrances` key.

Run: `python -m pytest tests/test_tilemap_contract.py tests/test_tilemap_quality_metrics.py -q`

Expected: PASS.

- [ ] **Step 4: Commit reviewed contract hunks only**

Because these files already contain bridge work, use interactive staging and inspect the staged diff:

```powershell
git add -p -- src/game_visual_forge/contracts/tilemap.py src/game_visual_forge/contracts/__init__.py tests/test_tilemap_contract.py
git diff --cached --check
git diff --cached --name-only
git commit -m "feat: declare walkable building entrances"
```

If a hunk mixes prior bridge edits with entrance edits and cannot be separated safely, do not commit it yet; leave it for the final scoped audit rather than staging unrelated work.

## Task 3: Emit and validate the building entrance artifact

**Files:**

- Modify: `src/game_visual_forge/processing/tilemap.py`
- Modify: `src/game_visual_forge/quality/tilemap.py`
- Modify: `tests/test_tilemap_processing.py`
- Modify: `tests/test_tilemap_manifest_integrity.py`

- [ ] **Step 1: Add failing processing and publication tests**

Extend a test request with one valid doorway and entrance. Assert:

```python
self.assertEqual(result.building_entrances_path, "building-entrances.json")
entrances = load_json(staging / result.building_entrances_path)
self.assertEqual(entrances["coordinate_system"], "top-left-grid")
self.assertEqual(entrances["entries"][0]["cell"], {"x": 1, "y": 0})
self.assertEqual(entrances["entries"][0]["target_scene_id"], "interiors/inn")
self.assertEqual(load_json(staging / "unity-tilemap.json")["building_entrances"], "building-entrances.json")
```

Add manifest-integrity tests asserting that a missing or modified `building-entrances.json` fails validation and cannot publish `final`. Invalid doorway role, collider, layer, and coordinates are rejected earlier by the `TileMapRequest` tests from Task 2.

Run:

```powershell
python -m pytest tests/test_tilemap_processing.py tests/test_tilemap_manifest_integrity.py -q
```

Expected: FAIL on the absent artifact/result fields.

- [ ] **Step 2: Emit the approved top-left entrance payload**

Extend `TileMapProcessingResult` with backward-compatible `building_entrances_path: str = ""`. During processing, write:

```json
{
  "schema_version": 1,
  "map_id": "spring-creek-village",
  "coordinate_system": "top-left-grid",
  "transition_implementation": "out-of-scope",
  "entries": []
}
```

Populate each entry from the request without changing X or Y; this sidecar intentionally retains the design/request top-left grid. Retain `id`, `layer_id`, `cell`, `target_scene_id`, and `target_spawn_id`. `tilemap-placement.json` continues to perform its existing, separate top-left-to-bottom-left conversion for Unity cells. Set `building_entrances` in `unity-tilemap.json`, set the result path, and append `emit-building-entrances` to `processing_steps`.

- [ ] **Step 3: Add deterministic entrance artifact checks**

For every declared entrance, derive the exact expected sidecar entry from the request. The quality report must contain a `building-entrances` check that passes only when the artifact has the expected schema, map ID, `top-left-grid` coordinate system, `out-of-scope` transition implementation, and exact ordered entries. Missing, extra, reordered, or changed entries fail the check and block publication.

Include `building-entrances.json` in:

- artifact existence/hash validation;
- `_paths` or equivalent published path list;
- the asset manifest with role `building-entrances`;
- request/processing/Unity manifest integrity checks.

- [ ] **Step 4: Verify the Python pipeline**

Run:

```powershell
python -m pytest tests/test_tilemap_processing.py tests/test_tilemap_manifest_integrity.py tests/test_tilemap_contract.py -q
```

Expected: PASS; a tampered entrance artifact blocks final publication.

- [ ] **Step 5: Commit reviewed processing and quality hunks**

```powershell
git add -p -- src/game_visual_forge/processing/tilemap.py src/game_visual_forge/quality/tilemap.py tests/test_tilemap_processing.py tests/test_tilemap_manifest_integrity.py
git diff --cached --check
git commit -m "feat: validate tilemap building entrance artifacts"
```

Again, leave inseparable pre-existing bridge hunks unstaged until ownership is resolved by the final audit.

## Task 4: Preserve entrance data in the Unity import

**Files:**

- Modify: `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleContracts.cs`
- Modify: `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleImporter.cs`
- Modify: `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapImportReportWriter.cs`
- Modify: `integrations/unity/com.game-visual-forge.tilemap/Tests/Editor/TilemapBundleImporterEditModeTests.cs`
- Modify: `tests/test_unity_tilemap_integration.py`

- [ ] **Step 1: Add failing static and Editor tests**

The Python integration test must assert that the Unity contracts/importer contain `building_entrances`, `building_entrances_asset`, and `Data/building-entrances.json`. The Unity Editor test must import a fixture manifest containing `"building_entrances":"building-entrances.json"` and assert:

```csharp
Assert.AreEqual(
    "Assets/GameVisualForgeMaps/test-map/Data/building-entrances.json",
    result.building_entrances_asset);
Assert.NotNull(AssetDatabase.LoadAssetAtPath<TextAsset>(result.building_entrances_asset));
```

Run: `python -m pytest tests/test_unity_tilemap_integration.py -q`

Expected: FAIL until the contract and importer are extended.

- [ ] **Step 2: Extend the Unity contracts**

Add:

```csharp
// BundleManifest
public string building_entrances;

// ImportResult and UnityImportReport
public string building_entrances_asset;
```

The field is optional for backward compatibility with older bundles.

- [ ] **Step 3: Copy and report the entrance TextAsset**

When `manifest.building_entrances` is non-empty:

- resolve it relative to the Python bundle directory;
- reject a missing source file;
- copy it to `${generated_root}/Data/building-entrances.json` using the importer’s existing replace/preserve-meta helper;
- import and load it as `TextAsset`;
- return and report the Unity asset path;
- include it in the importer’s GUID-stability snapshot so repeat imports prove stable resources.

Do not add a teleport MonoBehaviour or create interior scene references.

- [ ] **Step 4: Run static and Unity Editor tests**

Run:

```powershell
python -m pytest tests/test_unity_tilemap_integration.py -q
```

Expected: PASS.

Through Unity MCP, run the package’s Editor tests filtered to `TilemapBundleImporterEditModeTests` in `I:/UnityProject/2DMirrorDemo`.

Expected: all selected Editor tests pass and Unity Console has no new importer errors.

- [ ] **Step 5: Commit Unity importer changes**

```powershell
git add -- integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleContracts.cs integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleImporter.cs integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapImportReportWriter.cs integrations/unity/com.game-visual-forge.tilemap/Tests/Editor/TilemapBundleImporterEditModeTests.cs tests/test_unity_tilemap_integration.py
git diff --cached --check
git commit -m "feat: import tilemap entrance metadata into Unity"
```

## Task 5: Build the exact run packet and map request

**Files:**

- Create: `outputs/spring-creek-village-20260803/source/build_request.py`
- Create: `outputs/spring-creek-village-20260803/source/tilemap-request.json`
- Create: `outputs/spring-creek-village-20260803/source/capabilities.json`
- Create: `outputs/spring-creek-village-20260803/source/page-01.prompt.txt`
- Create: `outputs/spring-creek-village-20260803/source/page-02.prompt.txt`
- Create: `outputs/spring-creek-village-20260803/source/page-03.prompt.txt`

- [ ] **Step 1: Create the source packet without using old outputs**

Copy the three approved prompts verbatim from section 10 of the design spec into the three prompt files. Write capabilities as:

```json
{
  "schema_version": 1,
  "supported": true,
  "operations": ["text-to-image"]
}
```

- [ ] **Step 2: Implement a deterministic request builder**

`build_request.py` must construct one `TileMapRequest` and write `tilemap-request.json`. Use these exact high-level values:

```python
asset_id = "spring-creek-village"
output_dir = "outputs/spring-creek-village-20260803"
source_preference = "agent-native"
tile_width = tile_height = pixels_per_unit = 32
map_width, map_height = 32, 24
tile_size_mode = "preset_32"
tileset_profile = "adaptive_hd"
max_tile_count = 48
palette_name = "Spring Creek Village Palette"
unity_generated_root = "Assets/GameVisualForgeMaps/spring-creek-village"
```

Define three `AtlasPageDefinition` values `page-01`, `page-02`, and `page-03`, each 4x4 and linked to the corresponding full prompt. Define all 48 tiles with these exact page-local row-major slots:

```python
PAGE_01 = (
    "grass-base", "grass-alt", "grass-flower-sparse", "dirt-path-horizontal",
    "dirt-path-vertical", "path-turn-ne", "path-turn-nw", "path-turn-se",
    "path-turn-sw", "path-cross", "plaza-cobble", "plaza-border-horizontal",
    "plaza-border-vertical", "farm-soil", "farm-crop-young", "farm-crop-mature",
)
PAGE_02 = (
    "creek-center", "creek-current", "creek-bank-west", "creek-bank-east",
    "bank-west-flower", "bank-east-reed", "bend-west-top", "bend-west-bottom",
    "bend-east-top", "bend-east-bottom", "bridge-west", "bridge-middle-a",
    "bridge-middle-b", "bridge-east", "bridge-approach-west", "bridge-approach-east",
)
PAGE_03 = (
    "roof-top-left", "roof-top-middle", "roof-top-right", "roof-bottom-left",
    "roof-bottom-middle", "roof-bottom-right", "wall-left", "wall-window",
    "wall-doorway", "wall-right", "shop-front-sign", "inn-front-sign",
    "fence-horizontal", "fence-vertical", "large-rock", "spring-tree",
)
```

Semantic/collider rules:

- grass, paths, plaza, farm: terrain/road as appropriate, collider `none`;
- creek and banks that represent impassable water: `water`, collider `grid`;
- `bridge-west`, `bridge-middle-a`, `bridge-middle-b`, `bridge-east`: `bridge`, collider `none`;
- bridge approaches: `road`, collider `none`;
- roof, wall, signs, fence, rock, tree: `prop`, collider `grid`;
- `wall-doorway`: `doorway`, collider `none`;
- decorative grass/flowers/crop detail tiles on `details`: `decoration`, collider `none`.

Use helpers `index(x, y) = y * 32 + x`, `paint_rect`, `paint_row`, and `paint_building`. Start the ground layer as `grass-base`, then paint:

- the north-south creek at `x=14..17` for all rows except bridge span `y=12`;
- the east-west road at `y=12`, with approach cells `(13,12)` and `(18,12)` and the four bridge cells `(14,12)..(17,12)`;
- central plaza `x=6..13, y=9..14`, preserving the road/bridge contract;
- farm `x=18..30, y=20..23`;
- paths from every doorway to the nearest plaza/main-road cell without crossing a structure collider.

Paint structures for exactly these inclusive regions and doorway cells:

| Entrance | Region | Door | Target |
| --- | --- | --- | --- |
| `inn-entrance` | `x=3..8,y=3..8` | `(5,8)` | `interiors/inn` |
| `villager-a-entrance` | `x=9..13,y=2..7` | `(11,7)` | `interiors/villager-a` |
| `player-home-entrance` | `x=3..9,y=17..22` | `(6,22)` | `interiors/player-home` |
| `shop-entrance` | `x=20..25,y=4..9` | `(22,9)` | `interiors/shop` |
| `villager-b-entrance` | `x=26..30,y=2..7` | `(28,7)` | `interiors/villager-b` |
| `villager-c-entrance` | `x=23..28,y=14..19` | `(25,19)` | `interiors/villager-c` |

`paint_building(x0, y0, x1, y1, door_x, facade=None)` uses the full inclusive rectangle: the first roof row is left/middle/right, intermediate roof rows are bottom-left/bottom-middle/bottom-right, and the final row is wall-left, repeated wall-window, wall-doorway at `door_x`, and wall-right. For `inn-entrance`, replace the wall-window immediately left of the door with `inn-front-sign`; for `shop-entrance`, use `shop-front-sign`. This leaves the doorway as the only non-colliding structures cell in each building rectangle.

Each entrance uses layer `structures`, target spawn `entry`, and the actual `wall-doorway` placement. The structures layer has sorting order 10 and collider enabled; details has sorting order 20 and collider disabled; ground has sorting order 0 and collider enabled.

Add the exact bridge rule:

```json
{
  "id": "central-creek-bridge",
  "orientation": "horizontal",
  "bridge_layer_id": "ground",
  "approach_layer_id": "ground",
  "start": {"x": 14, "y": 12},
  "end": {"x": 17, "y": 12}
}
```

Use boundary trees, fences, rocks, wildflowers, and crop variations so every declared tile appears at least once, while keeping paths, bridge, and doorway cells free of structure colliders.

- [ ] **Step 3: Generate and inspect the request**

Run:

```powershell
python outputs/spring-creek-village-20260803/source/build_request.py
python -c "import json; from pathlib import Path; from game_visual_forge.contracts import TileMapRequest; p=Path('outputs/spring-creek-village-20260803/source/tilemap-request.json'); r=TileMapRequest.from_dict(json.loads(p.read_text(encoding='utf-8'))); assert len(r.tiles)==48; assert len(r.atlas_pages)==3; assert len(r.building_entrances)==6; print(r.asset_id, len(r.tiles), len(r.building_entrances))"
```

Expected: `spring-creek-village 48 6`.

Run a local assertion script over the JSON to confirm bridge cell roles, approach roles, six doorway cell roles/colliders, three layer sizes of 768, unique tile IDs, and zero unused tile IDs.

- [ ] **Step 4: Run planning before generating images**

```powershell
python skills/forge-2d-map/scripts/run.py map tile plan --request outputs/spring-creek-village-20260803/source/tilemap-request.json --out-dir outputs/spring-creek-village-20260803/job --now 2026-08-03T10:00:00+08:00
```

Expected: the normalized request, execution plan, and job state are written successfully.

Generated run files stay ignored; do not force-add them to Git.

## Task 6: Route, generate three new pages, normalize, ingest, and process

**Files:**

- Create: `outputs/spring-creek-village-20260803/job/source-decision.json`
- Create: `outputs/spring-creek-village-20260803/raw/page-01-generated.png`
- Create: `outputs/spring-creek-village-20260803/raw/page-02-generated.png`
- Create: `outputs/spring-creek-village-20260803/raw/page-03-generated.png`
- Create: `outputs/spring-creek-village-20260803/raw/tileset-page-01.png`
- Create: `outputs/spring-creek-village-20260803/raw/tileset-page-02.png`
- Create: `outputs/spring-creek-village-20260803/raw/tileset-page-03.png`
- Create: `outputs/spring-creek-village-20260803/job/raw-source-set.json`
- Create: `outputs/spring-creek-village-20260803/job/processing-result.json`

- [ ] **Step 1: Route explicitly to built-in image generation**

```powershell
python skills/forge-2d-map/scripts/run.py map tile route --request outputs/spring-creek-village-20260803/source/tilemap-request.json --capabilities outputs/spring-creek-village-20260803/source/capabilities.json --out outputs/spring-creek-village-20260803/job/source-decision.json --state outputs/spring-creek-village-20260803/job/job-state.json --now 2026-08-03T10:01:00+08:00
```

Inspect the decision and assert `source_type == "agent-native"`, `selected_provider is null`, `requires_user_selection == false`, and `requires_paid_confirmation == false`.

- [ ] **Step 2: Generate Page 01 once**

Call built-in `image_gen` with the complete Page 01 prompt. Save the returned bitmap as `raw/page-01-generated.png`, retain `source/page-01.prompt.txt`, and inspect the raw image at original detail. If it has anything other than a clean 4x4 atlas, correct row-major subjects, or contains text/watermark, stop and show it to the user.

- [ ] **Step 3: Generate and inspect Pages 02 and 03 once each**

Repeat with their complete prompt files. These are independent calls, but each page is generated only once unless the user explicitly approves a retry after seeing failure evidence. Verify cross-page palette, camera, pixel density, and upper-left lighting consistency.

- [ ] **Step 4: Normalize each accepted page to 128x128**

```powershell
python skills/forge-2d-map/scripts/normalize_tile_atlas.py --source outputs/spring-creek-village-20260803/raw/page-01-generated.png --output outputs/spring-creek-village-20260803/raw/tileset-page-01.png --columns 4 --rows 4 --tile-width 32 --tile-height 32
python skills/forge-2d-map/scripts/normalize_tile_atlas.py --source outputs/spring-creek-village-20260803/raw/page-02-generated.png --output outputs/spring-creek-village-20260803/raw/tileset-page-02.png --columns 4 --rows 4 --tile-width 32 --tile-height 32
python skills/forge-2d-map/scripts/normalize_tile_atlas.py --source outputs/spring-creek-village-20260803/raw/page-03-generated.png --output outputs/spring-creek-village-20260803/raw/tileset-page-03.png --columns 4 --rows 4 --tile-width 32 --tile-height 32
```

Inspect all normalized pages at original detail. Confirm they are exactly 128x128 and no slot was reordered.

- [ ] **Step 5: Ingest all pages in one source set**

```powershell
python skills/forge-2d-map/scripts/run.py map tile ingest --request outputs/spring-creek-village-20260803/source/tilemap-request.json --decision outputs/spring-creek-village-20260803/job/source-decision.json --atlas-page page-01=outputs/spring-creek-village-20260803/raw/tileset-page-01.png --atlas-page page-02=outputs/spring-creek-village-20260803/raw/tileset-page-02.png --atlas-page page-03=outputs/spring-creek-village-20260803/raw/tileset-page-03.png --repo-root . --out outputs/spring-creek-village-20260803/job/raw-source-set.json --state outputs/spring-creek-village-20260803/job/job-state.json --now 2026-08-03T10:10:00+08:00
```

Expected: source set contains exactly `page-01`, `page-02`, and `page-03`, each with a content hash and this request fingerprint.

- [ ] **Step 6: Process into staging**

```powershell
python skills/forge-2d-map/scripts/run.py map tile process --request outputs/spring-creek-village-20260803/source/tilemap-request.json --raw-image outputs/spring-creek-village-20260803/job/raw-source-set.json --repo-root . --out-dir outputs/spring-creek-village-20260803/final --state outputs/spring-creek-village-20260803/job/job-state.json --now 2026-08-03T10:11:00+08:00 > outputs/spring-creek-village-20260803/job/processing-result.json
```

Read `staging_dir` from the returned JSON. Do not guess or hard-code the fingerprinted staging directory.

## Task 7: Perform visual review and publish only a passing bundle

**Files:**

- Create: `outputs/spring-creek-village-20260803/source/visual-review.json`
- Create: `outputs/spring-creek-village-20260803/final/*`

- [ ] **Step 1: Inspect all generated QA evidence**

Open from the discovered staging directory:

- `tilemap-preview.png` at original detail;
- `tile-seam-preview.png`;
- `tile-usage-preview.png`;
- all three normalized tileset pages;
- `tilemap-quality-metrics.json`;
- `building-entrances.json`;
- `tilemap-placement.json`;
- `unity-tilemap.json`.

Confirm the map reads as a cozy spring village, the creek is continuous north-south, the bridge is continuous west-east, six cottages assemble without broken roofs/walls, and there is no text/watermark.

- [ ] **Step 2: Verify deterministic quality facts**

Use a read-only Python assertion script to require:

- all three atlas pages exist and are 128x128;
- 48 unique tiles and every tile has usage count greater than zero;
- `clipped_tiles`, `overused_tiles`, `invalid_adjacencies`, and `invalid_bridge_connectivity` are empty;
- maximum seam score is at or below 48;
- preview contract is 32x24 cells at 32x32 pixels;
- bridge cells `(14..17,12)` are bridge/none and approaches `(13,12)`, `(18,12)` are road/none;
- the six entrance records match the approved IDs/targets and point to doorway/none cells;
- request, placement, quality report, and Unity manifest hashes/contracts agree.

- [ ] **Step 3: Record human review only after actually viewing evidence**

Write `visual-review.json` with exactly these passed check IDs and the schema accepted by `apply_tilemap_visual_review`:

```json
{
  "schema_version": 1,
  "checks": {
    "tileset-seams": "passed",
    "tilemap-readability": "passed",
    "layer-order": "passed",
    "collision-layer": "passed",
    "unwanted-text-or-watermark": "passed"
  }
}
```

If any statement is not true, do not write a passing review; show the evidence and wait for user direction.

- [ ] **Step 4: Validate and publish final**

Read the exact `staging_dir` from `processing-result.json` and pass it directly:

```powershell
$springVillageStaging = (Get-Content -Raw 'outputs/spring-creek-village-20260803/job/processing-result.json' | ConvertFrom-Json).staging_dir
python skills/forge-2d-map/scripts/run.py map tile validate --request outputs/spring-creek-village-20260803/source/tilemap-request.json --raw-image outputs/spring-creek-village-20260803/job/raw-source-set.json --processing-result outputs/spring-creek-village-20260803/job/processing-result.json --repo-root . --staging-dir $springVillageStaging --final-dir outputs/spring-creek-village-20260803/final --visual-review outputs/spring-creek-village-20260803/source/visual-review.json --state outputs/spring-creek-village-20260803/job/job-state.json --now 2026-08-03T10:15:00+08:00
```

Expected: job phase `completed`, quality `passed`, and `final` published atomically. Show the user the current run’s preview, seam preview, usage preview, and concise quality result before Unity import.

## Task 8: Import and place in `2DMirrorDemo`, then accept the scene

**Files:**

- Modify: active scene in `I:/UnityProject/2DMirrorDemo`
- Create/update: `I:/UnityProject/2DMirrorDemo/Assets/GameVisualForgeMaps/spring-creek-village/**`
- Create: current-run Unity acceptance screenshot under `outputs/spring-creek-village-20260803/unity/`

- [ ] **Step 1: Inspect Unity state without mutation**

Use Unity MCP to read the active project, Editor state, active scene path, package availability, console baseline, and custom tools. Require the project to be `I:/UnityProject/2DMirrorDemo`, the Editor to be ready, and the active scene to be the user’s current scene. Do not switch scenes unless the user explicitly asks.

- [ ] **Step 2: Import and place the validated bundle**

Invoke Editor code through Unity MCP that calls:

```csharp
var manifestPath = @"G:\GitProject\game-visual-forge\outputs\spring-creek-village-20260803\final\unity-tilemap.json";
var json = GameVisualForge.Unity.TilemapBundleImporter.ImportAndPlaceBundleForAutomation(manifestPath);
UnityEngine.Debug.Log(json);
```

Wait for asset refresh/compilation to finish. Parse the returned import result and require:

- generated root `Assets/GameVisualForgeMaps/spring-creek-village`;
- 3 atlas assets and 48 Tile assets;
- prefab `spring-creek-village-tilemap.prefab`;
- entrance TextAsset `Data/building-entrances.json`;
- scene action is `created` or `updated`;
- placed instance is `spring-creek-village-tilemap`.

- [ ] **Step 3: Clean up only scene visibility**

If `standard-bridge-flow-tilemap` exists in the current scene, set that instance inactive without deleting the GameObject, Prefab, or generated assets. Ensure exactly one active `spring-creek-village-tilemap` root exists.

- [ ] **Step 4: Save and verify scene structure**

Save the active scene, wait for refresh, and verify `isDirty == false`. Inspect the new root:

- children are `ground`, `structures`, `details`;
- sorting orders are 0, 10, 20;
- `ground` and `structures` have `TilemapCollider2D`;
- `details` has no collider;
- entrance data loads as a Unity `TextAsset` with exactly six records;
- bridge span, approaches, water collision, and six doorway cells match the final manifests.

- [ ] **Step 5: Frame the map and capture acceptance evidence**

Adjust the scene’s existing camera position/orthographic size only as needed to frame the complete 32x24 map in Game View. Do not add gameplay scripts. Capture a current-run Game View screenshot to `outputs/spring-creek-village-20260803/unity/` and inspect it visually.

Read Console messages since the baseline. Require no errors related to Game Visual Forge, import, assets, prefab, Tilemap, or Collider; report unrelated pre-existing warnings separately.

- [ ] **Step 6: Repeat import to prove idempotency**

Call `ImportAndPlaceBundleForAutomation` a second time with the same manifest. Require:

- `had_existing_assets == true`;
- `resource_guids_stable == true`;
- scene action `updated`;
- still exactly one active placed instance;
- scene saves cleanly again.

- [ ] **Step 7: Run final repository regression tests**

```powershell
python -m pytest tests/test_tilemap_contract.py tests/test_tilemap_processing.py tests/test_tilemap_quality_metrics.py tests/test_tilemap_manifest_integrity.py tests/test_unity_tilemap_integration.py tests/test_skill_contracts.py -q
git diff --check
git status --short
```

Expected: all selected tests pass. Inspect status and ensure no README or unrelated pre-existing asset changes were staged by this work.

- [ ] **Step 8: Report completion with evidence**

Provide clickable paths for the final preview, quality report, building entrance data, Unity manifest, Unity import report, and Game View screenshot. State the active scene path, placed root, layer/collider summary, six entrance count, bridge result, repeat-import GUID result, and any unrelated Unity warnings. Do not claim completion if final publication, scene save, console verification, or screenshot inspection failed.

## Final Coverage Audit

- [ ] Search the produced code and run packet for unfinished markers, fake paths, and unexecuted example values; remove or resolve them before implementation is declared complete.
- [ ] Compare all 48 tile IDs and all six entrance coordinates against design sections 5 and 9.
- [ ] Confirm `building-entrances.json` preserves top-left request coordinates, while `tilemap-placement.json` independently converts cells once for Unity’s bottom-left coordinates.
- [ ] Confirm every new field is backward compatible for old requests and old Unity manifests.
- [ ] Confirm image generation occurred only after successful `plan` and `route` and each page was generated from its saved prompt.
- [ ] Confirm no old atlas, placement, preview, screenshot, README evidence, or automatically retried generation entered the run.
- [ ] Confirm `final` exists only after deterministic and visual quality both pass.
- [ ] Confirm Unity Import and Place happened only after the current result was shown and only in the active `2DMirrorDemo` scene.
