# 春溪村 Unity Tilemap 设计规格

日期：2026-08-03

状态：待用户书面审核

目标项目：`I:/UnityProject/2DMirrorDemo`

## 1. 目标

从零生成一张可在 `2DMirrorDemo` 中实际使用的俯视角 RPG 村落地图。地图采用治愈的现代像素风，支持角色行走、Tile 碰撞、可通行木桥和建筑入口标记，最终以 Unity Tilemap Prefab 导入并放入当前场景。

本次必须完整执行 `forge-2d-map` 的标准流程：

`plan -> route -> image generation -> ingest -> process -> validate -> visual review -> Unity Import and Place -> Unity acceptance`

不得复用先前生成的图集、地图放置数据或截图作为本次结果。

## 2. 已确认需求

- 地图类型：俯视角 RPG 城镇/村落外景。
- 使用目标：角色可行走、可碰撞、可到达建筑门口。
- Unity 项目：`I:/UnityProject/2DMirrorDemo`。
- 地图尺寸：`32 x 24` 格。
- Tile 尺寸：`32 x 32` 像素；完整地图逻辑尺寸为 `1024 x 768` 像素。
- 画风：现代像素风。
- 氛围：春日晴天、嫩绿草地、野花、浅蓝溪水、暖色屋顶。
- 建筑风格：木框、浅色灰泥墙、暖色瓦顶的田园村舍。
- 水系：南北向溪流。
- 过河设施：中央东西向可通行木桥。
- 功能区：中央广场、玩家住宅、三栋村民住宅、杂货店、旅店、农田。
- 建筑范围：只制作村落外景和六个建筑入口标记，不制作室内地图，不实现传送逻辑。
- 不设计玩家出生点或村外出口。
- 美术来源：内置图像生成；不复用现有 Tileset。
- Tileset：`adaptive_hd`，48 个 Tile，三张 4x4 图集页。
- Unity 行为：质量通过且结果展示后，显式执行 `Import and Place`。

## 3. 选定制作方案

采用“定制村落 Tilemap”。地形、道路、小溪、木桥、建筑和主要阻挡物全部来自本次 48 Tile 图集，并通过三层 Unity Tilemap 组装。建筑使用为本地图定制的屋顶、墙面、门口和店铺/旅店立面组合，而不是额外生成大尺寸建筑 Sprite。

未采用的方案：

- 完全通用的模块化 Tileset：编辑自由度更高，但六栋建筑会更重复，村落构图也更难稳定。
- Tilemap 加独立建筑 Sprite：美术自由度更高，但会扩大为额外的透明资产和 Prefab 生产线，不符合本次纯 Tilemap 标准流程的范围。

## 4. 管线轴

- `map_mode`: `tile_mode`
- `visual_model`: `layered_tilemap`
- `runtime_object_model`: 最小 `scene_hooks`，仅包含建筑入口元数据
- `collision_model`: `tile_collision`
- `engine_target`: `Unity_Tilemap`
- `visual_asset_source`: `image_gen`
- `tile_size_mode`: `preset_32`
- `tileset_profile`: `adaptive_hd`
- `atlas_pages`: 3
- `atlas_grid`: 每页 4x4
- `max_tile_count`: 48
- `filter_mode`: `point`
- `texture_compression`: none
- `pixels_per_unit`: 32

## 5. 空间布局

请求和设计文档中的格坐标使用左上角原点、x 向右、y 向下。Unity 导入时由现有管线转换为左下角 Tilemap 坐标；预览和 Unity 必须使用同一份转换后的放置数据。

- 南北向溪流穿过地图中部，在桥位占据 `x=14..17`。
- 东西向主路在 `y=12` 横穿村落。
- 木桥跨度为 `(14,12)..(17,12)`，西侧道路接近格为 `(13,12)`，东侧道路接近格为 `(18,12)`。
- 中央广场位于西岸中部，约覆盖 `x=6..13, y=9..14`，并连接木桥主路。
- 西岸布置旅店、村民住宅 A 和玩家住宅。
- 东岸布置杂货店、村民住宅 B、村民住宅 C 和农田。
- 农田位于东南区域，约覆盖 `x=18..30, y=20..23`。
- 地图边缘使用树木、围栏和花草形成自然边界，但不声明玩家出生点和村外出口。

### 建筑与入口

| 入口 ID | 建筑 | 建筑区域 | 门口格 | 目标场景 ID |
| --- | --- | --- | --- | --- |
| `inn-entrance` | 旅店 | `x=3..8, y=3..8` | `(5,8)` | `interiors/inn` |
| `villager-a-entrance` | 村民住宅 A | `x=9..13, y=2..7` | `(11,7)` | `interiors/villager-a` |
| `player-home-entrance` | 玩家住宅 | `x=3..9, y=17..22` | `(6,22)` | `interiors/player-home` |
| `shop-entrance` | 杂货店 | `x=20..25, y=4..9` | `(22,9)` | `interiors/shop` |
| `villager-b-entrance` | 村民住宅 B | `x=26..30, y=2..7` | `(28,7)` | `interiors/villager-b` |
| `villager-c-entrance` | 村民住宅 C | `x=23..28, y=14..19` | `(25,19)` | `interiors/villager-c` |

`target_scene_id` 是稳定的目标标识，不代表本次会创建相应室内场景。传送组件和运行时代码不在本次范围内。

## 6. Tilemap 图层与碰撞

### `ground`

- 排序顺序：0。
- 内容：草地、道路、广场、农田、小溪、木桥。
- 启用 `TilemapCollider2D`。
- 水 Tile 使用 `grid` Collider。
- 草地、道路、广场、农田和桥 Tile 使用 `none` Collider。
- 桥位的 `ground` 单元直接使用桥 Tile，不在桥下保留有碰撞的水 Tile，避免视觉连通但实际无法过桥。

### `structures`

- 排序顺序：10。
- 内容：建筑屋顶与墙体、树木、围栏。
- 启用 `TilemapCollider2D`。
- 屋顶、墙体、树木和围栏使用 `grid` Collider。
- `wall-doorway` 使用 `none` Collider，保证入口格可到达。

### `details`

- 排序顺序：20。
- 内容：野花、草簇、作物细节和非阻挡装饰。
- 不创建 Collider。

## 7. 建筑入口数据

输出 `building-entrances.json`：

```json
{
  "schema_version": 1,
  "map_id": "spring-creek-village",
  "coordinate_system": "top-left-grid",
  "transition_implementation": "out-of-scope",
  "entries": [
    {
      "id": "inn-entrance",
      "cell": {"x": 5, "y": 8},
      "target_scene_id": "interiors/inn",
      "target_spawn_id": "entry"
    }
  ]
}
```

最终文件包含第 5 节列出的六条记录。每个入口坐标必须落在 `wall-doorway` Tile 上，且该 Tile 不产生碰撞。

## 8. 木桥连通合同

在 `ground` 层声明：

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

- 四个跨度格必须使用 `semantic_role=bridge`。
- `(13,12)` 与 `(18,12)` 必须使用 `semantic_role=road`。
- 桥跨度格不得存在水 Tile Collider。
- 任意桥格或道路接近格错误都必须阻止发布 `final` 目录。

## 9. 三页图集槽位

槽位均采用 row-major 顺序。

### Page 01：地形、道路、广场、农田

| 行 | 第 1 列 | 第 2 列 | 第 3 列 | 第 4 列 |
| --- | --- | --- | --- | --- |
| 1 | `grass-base` | `grass-alt` | `grass-flower-sparse` | `dirt-path-horizontal` |
| 2 | `dirt-path-vertical` | `path-turn-ne` | `path-turn-nw` | `path-turn-se` |
| 3 | `path-turn-sw` | `path-cross` | `plaza-cobble` | `plaza-border-horizontal` |
| 4 | `plaza-border-vertical` | `farm-soil` | `farm-crop-young` | `farm-crop-mature` |

### Page 02：小溪与木桥

| 行 | 第 1 列 | 第 2 列 | 第 3 列 | 第 4 列 |
| --- | --- | --- | --- | --- |
| 1 | `creek-center` | `creek-current` | `creek-bank-west` | `creek-bank-east` |
| 2 | `bank-west-flower` | `bank-east-reed` | `bend-west-top` | `bend-west-bottom` |
| 3 | `bend-east-top` | `bend-east-bottom` | `bridge-west` | `bridge-middle-a` |
| 4 | `bridge-middle-b` | `bridge-east` | `bridge-approach-west` | `bridge-approach-east` |

### Page 03：建筑与阻挡物

| 行 | 第 1 列 | 第 2 列 | 第 3 列 | 第 4 列 |
| --- | --- | --- | --- | --- |
| 1 | `roof-top-left` | `roof-top-middle` | `roof-top-right` | `roof-bottom-left` |
| 2 | `roof-bottom-middle` | `roof-bottom-right` | `wall-left` | `wall-window` |
| 3 | `wall-doorway` | `wall-right` | `shop-front-sign` | `inn-front-sign` |
| 4 | `fence-horizontal` | `fence-vertical` | `large-rock` | `spring-tree` |

## 10. 图像生成提示词

### Page 01

Create one production-ready 4x4 tileset atlas page for a top-down cozy RPG village, modern pixel art, spring sunny palette, fresh light-green grass, tiny wildflowers, warm beige dirt paths, soft gray-beige plaza cobbles, golden-brown farm soil and cheerful green crops. Exact orthographic top-down view, crisp readable silhouettes, consistent light from upper left, no perspective drift. Sixteen equal square cells in strict row-major order: grass base; alternate grass; sparse flower grass; horizontal dirt path; vertical dirt path; northeast path turn; northwest path turn; southeast path turn; southwest path turn; four-way path crossing; plaza cobble; horizontal plaza border; vertical plaza border; farm soil; young crop row; mature crop row. Path and terrain edges must be tileable and align at opposite cell boundaries. No buildings, water, bridge, characters, creatures, UI, labels, letters, numbers, watermark, frame, or decorative atlas border. Keep every design inside its cell and preserve clean cell separation.

### Page 02

Create one production-ready 4x4 tileset atlas page for the same top-down cozy spring RPG village, modern pixel art, matching Page 01 exactly in palette, pixel density, orthographic camera and upper-left lighting. The creek runs north-south with shallow clear light-blue water, gentle white highlights, grassy banks, small stones, flowers and reeds. The bridge runs west-east and is a warm honey-brown wooden footbridge with readable rails and seamless deck continuity. Sixteen equal square cells in strict row-major order: creek center; alternate flowing current; west bank; east bank; flowered west bank; reedy east bank; westward bend upper piece; westward bend lower piece; eastward bend upper piece; eastward bend lower piece; bridge west end; bridge middle variation A; bridge middle variation B; bridge east end; west road approach; east road approach. Water and bank edges must align across neighboring cells. The four bridge cells must form one continuous horizontal bridge; approach cells must visually connect dirt road to bridge. No buildings, characters, creatures, UI, labels, text, numbers, watermark, frame, or atlas border. Keep every design inside its cell and preserve clean cell separation.

### Page 03

Create one production-ready 4x4 tileset atlas page for the same top-down cozy spring RPG village, modern pixel art, matching Pages 01 and 02 exactly in palette, pixel density, orthographic camera and upper-left lighting. Architecture uses warm terracotta roof tiles, pale cream plaster walls, dark timber framing and welcoming wooden doors. Sixteen equal square cells in strict row-major order: roof top-left; roof top-middle; roof top-right; roof bottom-left; roof bottom-middle; roof bottom-right; wall left edge; wall with window; open walkable doorway; wall right edge; shop facade with a purely pictorial hanging goods sign and no letters; inn facade with a purely pictorial bed or mug sign and no letters; horizontal wooden fence; vertical wooden fence; large rounded field rock; leafy spring tree. Building pieces must assemble into coherent multi-tile cottages. Roof, wall, fence, rock and tree silhouettes must remain inside their cells; the doorway must read as passable. No characters, creatures, readable writing, UI, labels, letters, numbers, watermark, frame, or atlas border. Preserve clean cell separation.

## 11. 生成与处理数据流

1. 根据本规格建立 `TileMapRequest`、能力描述和三页提示词文件。
2. 执行 `map tile plan`。
3. 执行 `map tile route`，明确选择内置图像生成，不选择外部付费 Provider。
4. 按 Page 01、Page 02、Page 03 顺序生成全新原始图集。
5. 每次生成后保存原图和对应 `.prompt.txt`，并进行视觉检查。
6. 图像生成服务若返回较大的正方形图，将整页按固定 4x4 网格使用 nearest-neighbor 归一化为 `128 x 128`；不得单独重排、重绘或替换槽位。
7. 以显式 `page-01`、`page-02`、`page-03` atlas ID 执行 `ingest`。
8. 执行 `process`，生成切片、三层摆放、入口数据、Unity 清单和 QA 预览。
9. 执行 `validate` 和人工视觉检查。只有全部通过才发布 `final`。
10. 向用户展示当前输出预览、接缝图、使用图和质量报告。
11. 用户已选择 Unity `Import and Place`；只有第 10 步完成后才执行 Unity 导入与放置。

## 12. 质量门禁

### 确定性检查

- 三张源图集存在，尺寸与 4x4 网格声明一致。
- 48 个 Tile ID 唯一，atlas ID 和坐标有效。
- 三层摆放数据可解析，所有引用的 Tile 存在。
- 输出预览尺寸与 `32 x 24`、`32 x 32` Tile 合同一致。
- 无裁切 Tile、未使用 Tile、非法邻接或非法桥梁连接。
- 接缝分数不超过当前管线配置阈值。
- 六个建筑入口坐标均使用 `wall-doorway`，且无 Collider。
- 水 Tile 有 Collider；桥、道路和入口 Tile 无 Collider。
- Unity 清单与请求、质量报告哈希一致。

### 人工视觉检查

- `tileset-seams`
- `tilemap-readability`
- `layer-order`
- `collision-layer`
- `unwanted-text-or-watermark`
- 建筑模块能拼成六栋完整村舍，屋顶和墙体没有断裂。
- 小溪南北连续，桥梁东西连续，桥两端与道路对齐。
- 现代像素风、春日色彩和三页光照保持一致。

如果结果为 `needs_attention` 或 `failed`，必须展示当前证据并等待用户决定。不得自动修改提示词、替换图集页或重新提交图像生成任务。

## 13. Unity 导入与验收

- 导入根目录：`Assets/GameVisualForgeMaps/spring-creek-village`
- Palette：`Spring Creek Village Palette`
- Prefab：`spring-creek-village-tilemap.prefab`
- 场景根对象：`spring-creek-village-tilemap`
- 导入模式：`Import and Place`
- 目标场景：导入时 `2DMirrorDemo` 当前活动场景。

导入器应生成或更新三页 Sprite、48 个 Tile、Palette、三层 Tilemap Prefab 和导入报告。重复导入必须复用现有 Prefab 实例并保持资源 GUID 稳定。

为了查看新地图，可将旧的 `standard-bridge-flow-tilemap` 测试实例设为 inactive，但不得删除它或其资源。导入后验证：

- 场景中只有一个活动的 `spring-creek-village-tilemap` 实例。
- 子层为 `ground`、`structures`、`details`，排序顺序分别为 0、10、20。
- `ground` 和 `structures` 存在 `TilemapCollider2D`，`details` 不存在 Collider。
- 桥梁跨度、道路接近格、水碰撞和六个门口格符合本规格。
- `building-entrances.json` 作为交付数据保留，并可被 Unity 项目读取为 TextAsset 或等价项目数据。
- 活动场景已保存且 `isDirty=false`。
- Console 没有地图导入、资源、Prefab、Tilemap 或 Collider 相关错误。
- Game View 能完整展示村落，并保存当前输出截图。

## 14. 错误处理与范围边界

- 图像生成失败或提交状态未知时停止，不自动重试。
- 任一图集页槽位错位、出现文字/水印或无法可靠切片时停止，并展示该页。
- 验证失败时保留 staging 证据，不发布 `final`。
- Unity 导入失败时不宣称完成，保留 Python 交付包并报告具体 Console 错误。
- 本次不创建室内地图、玩家角色、NPC、任务、门传送逻辑、玩家出生点或村外出口。
- 常规运行不得改写 README 或伪造验收证据链接。

## 15. 完成标准

只有同时满足以下条件才算完成：

1. 三页图集均来自本次内置图像生成，并保存提示词。
2. `forge-2d-map` 五段 CLI 流程全部成功。
3. 确定性与人工质量检查全部通过。
4. 当前生成的地图预览已展示给用户。
5. Unity 成功导入并放置新的三层 Tilemap Prefab。
6. 角色通行语义满足：草地、道路、广场、农田边缘、桥面和门口可行走；溪水、建筑墙体、树木和围栏不可穿越。
7. 六个建筑入口记录有效，但不包含传送逻辑实现。
8. Unity 场景保存、无地图相关错误，并提供 Game View 截图。
