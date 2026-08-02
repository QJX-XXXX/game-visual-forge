---
name: forge-2d-map
description: "Generate production-oriented 2D game maps with explicit visual, layer, runtime-object, collision, and export models."
---

# Forge 2D Map

## Tile 模式与 Unity Tilemap

当用户要求像素风格 Tileset、Tile Palette 或 Unity Tilemap 时，先确认 Tile
尺寸、图集行列、地图宽高、图层、碰撞层和每个 Tile 的 atlas 坐标，再建立
`TileMapRequest`。可见美术必须来自图像生成工具或用户素材；本地脚本只负责切片、
组装、坐标转换、验证和导出，不用程序绘制替代最终美术。

使用 `map tile plan -> map tile route -> map tile ingest -> map tile process ->
map tile validate`。输出必须包含 Tileset、切片描述、摆放数据、Unity 导入清单和
预览图。发布前检查接缝、可读性、图层顺序、碰撞层和意外文字/水印。

Unity 目标使用仓库中的 `com.game-visual-forge.tilemap` Editor Package。依赖必须由
用户明确安装；Skill 和导入器不得静默安装 Package。导入器只生成或更新 Sprite、
Tile、Tile Palette 与 Tilemap Prefab，不修改当前打开的 Scene。默认 Point 过滤、
无纹理压缩、一个 Tile 对应一个 Unity 单位，并优先保持资源 GUID 与重复导入幂等。

先确认地图视觉模型、图层、运行时对象、碰撞和交互目标，再建立 `MapRequest`。M2 第一批支持已有底图的零网络地图管线：规划、能力路由、底图导入、碰撞派生和质量验证。

需要生成底图或 Props 时，默认先使用 Agent 原生工具。原生不支持时，要求用户选择即梦、万相、本地图像工具或已有素材；每次都由用户选择来源。

第三方预检和费用摘要完成后必须取得独立付费确认。不得根据凭据或历史选择自动选择服务商，不得自动安装工具，不得自动重新提交失败或 `submission_unknown` 的任务。

```powershell
python skills/forge-2d-map/scripts/run.py dry-run `
  --brief <brief.json> --out-dir <output> --now <utc-rfc3339>
```

## Adaptive Tilemap quality workflow

Tile mode supports two explicit profiles:

- `standard_16`: one legacy atlas page and up to 16 Tiles.
- `adaptive_hd`: 16, 32, or 48 Tiles across one to three 4x4 atlas pages.

Before image generation, infer the semantic Tile requirements, choose the
profile, prepare an ordered multi-page confirmation packet, and wait for
explicit user confirmation. The packet must show the selected profile, atlas
page count, ordered slots, and the prompt for every page before any page is
generated. After confirmation, generate all pages and ingest them with explicit
atlas IDs via repeated `--atlas-page` arguments:

```text
--atlas-page page-01=outputs/adaptive-map/raw/tileset-page-01.png
--atlas-page page-02=outputs/adaptive-map/raw/tileset-page-02.png
```

Run `map tile plan -> route -> ingest -> process -> validate`; inspect
`tilemap-preview.png`, `tile-seam-preview.png`, `tile-usage-preview.png`, and
the `map-quality-report.json` quality preview artifacts. If quality is
`needs_attention`, show the evidence and request confirmation before changing
prompts or regenerating pages. Choose Unity **Assets-only** import by default,
or explicitly choose **Import and Place** when the user wants a prefab
instance placed in the active Scene. Collision/mask layers are optional
spatial data; gameplay objects, NPCs, exits, quests, interaction systems, and
runtime game logic are outside this Skill's scope. Routine runs write JSON
reports such as `map-quality-report.json` and
`Reports/unity-import-report.json`, but never rewrite README files or invent
README evidence links.

## Tile size modes

Choose exactly one tile size mode from the user's request. The decision table is:

| User request | Mode | Final size |
| --- | --- | --- |
| no size | `preset_32` | 32×32 |
| 16×16 | `preset_16` | 16×16 |
| any other positive width×height | `custom` | requested dimensions |

The 16×18 size is supported when explicitly requested through `custom`; it is
not a preset. Minimal request examples are:

```json
{"tile_size_mode":"preset_16"}
{"tile_size_mode":"preset_32"}
{"tile_size_mode":"custom","tile_width":16,"tile_height":18}
```

No-size requests use `preset_32`. All atlas pages in one request share the
selected tile size. Unity derives Grid Cell Size as
`(tile_width / pixels_per_unit, tile_height / pixels_per_unit, 1)`.

## M2 本地地图管线

地图请求使用整数像素坐标描述 `spawn`、`walk_bounds`、`blockers` 和 `zones`。处理器不修改原始底图，输出 `base-map.png`、`map-runtime.json`、`walkable-mask.png`、`collision-mask.png` 和 `debug-preview.png`。其中可行走区域为 `walk_bounds - blockers`，碰撞区域为其反集；`zones` 只写入运行时元数据和调试预览。

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

地图生成 Provider 仍遵循显式能力路由和付费确认规则；M2 不自动调用付费服务，也不自动重试未知提交状态。发布前必须通过确定性质量检查，并完成 `visual-review`。
