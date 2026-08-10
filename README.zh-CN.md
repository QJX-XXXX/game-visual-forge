# Game Visual Forge

[English](README.md) | 简体中文

Game Visual Forge 是一个仓库内使用的 Codex Skills 集合，包含三项能力：
可玩 2D 地图、2D 精灵，以及视频转精灵动画。用户用自然语言描述目标，
对应 Skill 会生成经过验证的资源包或可交给引擎的结果。

## Skills

| Skill | 用途 | 常见输出 |
| --- | --- | --- |
| [`forge-2d-map`](skills/forge-2d-map/SKILL.md) | 可行走 2D 地图、Tilemap、地形、道具、碰撞和 Unity 交付 | 地图包、预览、摆放数据、质量证据 |
| [`forge-2d-sprite`](skills/forge-2d-sprite/SKILL.md) | 角色、生物、NPC、道具、特效和动画图集 | 透明精灵图集、帧文件、GIF 预览、元数据 |
| [`forge-video-to-sprite`](skills/forge-video-to-sprite/SKILL.md) | 将指定视频或生成的动作片段转换为高密度精灵帧 | 抽取帧、精灵条、GIF 预览、元数据 |

## 提供的能力

- 通过自然语言收集画风、布局、运行时和交付格式等关键选择。
- 需要新素材时可调用内置生图，也支持用户提供已有素材。
- 使用确定性的本地处理、质量报告和可复现的资源清单。
- 支持包含可行走区域、碰撞、对象、入口和 Unity Tilemap 的可玩地图交付。
- 原生地图图集会在验证前按声明的网格、Tile 尺寸、边距和间距进行标准化；
  处理过程保留生成源文件并记录输入/输出哈希，只统一图集几何，不修复美术、
  接缝或地图拓扑。
- 对付费或外部任务提供 Provider、费用和提交确认门禁。
- `forge-video-to-sprite` 使用 FFmpeg/FFprobe 在本地处理视频，支持按时间戳
  抽帧、rembg/Chroma 清理、稳定对齐、精灵条、图集、GIF 和动作质量证据。
- 生成视频必须明确选择海螺（MiniMax Hailuo）或即梦，以及 API 或官方 CLI
  兼容后端；工具和凭证由用户手动配置，流程不会自动切换。

## 效果展示

### 可玩地图交付

![Unity 中的自适应河流穿越地图](assets/readme/adaptive-river-crossing-map-unity-game-view.png)

示例包含 Tilemap 资源包、分层地图、桥连通性、碰撞数据和 Unity 验收证据。

### HD 精灵清理

![HD 背景移除效果对比](assets/readme/rembg-production-comparison-on-gray.jpg)

清理不是一个不透明的单步滤镜，而是由多个本地步骤组成：

- Pillow 负责 RGBA 转换，以及透明 PNG/GIF 导出。
- NumPy/SciPy 负责 alpha 遮罩和已知背景重建。
- rembg 默认使用 `birefnet-general` 做语义前景分割，相比单纯按颜色抠图，
  更能保留头发、布料和其他柔和边缘。
- 已知洋红背景重建会减少抗锯齿边缘的色边；如果 CUDA 失败，处理器会尝试
  CPU；模型仍失败时会记录原因并使用确定性的 Chroma fallback。
- 可选的 PyMatting 可进一步处理困难的半透明边缘，但速度更慢，也不保证对
  每一张素材都更好。

#### HD 清理安装

先安装项目 extra，再根据机器选择对应的 rembg ONNX Runtime 后端：

```powershell
# 仅使用 Pillow 的本地图像处理
python -m pip install -e ".[image]"

# HD 清理所需的 rembg、NumPy 和 SciPy
python -m pip install -e ".[background]"

# 二选一：CPU 兼容性最好；GPU 需要 CUDA 环境
python -m pip install "rembg[cpu]"
python -m pip install "rembg[gpu]"

# 可选 PyMatting 精细处理；先选择一个 rembg 后端
python -m pip install -e ".[matting]"
```

首次使用前初始化默认模型，让项目复用本地模型缓存：

```powershell
python -c "from rembg import new_session; new_session('birefnet-general')"
```

设置了 `U2NET_HOME` 时模型保存在该目录，否则使用 `~/.u2net`。如果需要，
可把 `U2NET_HOME` 指向一个有写权限的共享模型目录。仓库不会静默安装依赖、
下载模型或选择 GPU。兼容性优先选 CPU；批量处理高分辨率素材且 CUDA 已验证时
选 GPU；纯色背景且追求速度时选 Chroma；只有确实需要柔边精修时再启用
PyMatting。

## 安装

建议直接在仓库内使用，也可以参考对应平台的手动指南：

- [Codex 安装指南](install/codex/README.md)
- [Claude 安装指南](install/claude/README.md)

安装指南不会自动安装 Provider、FFmpeg、凭证或依赖，也不会写入用户配置目录。

## 请求示例

```text
使用 forge-2d-map 制作俯视角村落：南北向小溪、一座可通行木桥、建筑入口、
碰撞区域，并交付 Unity Tilemap。
```

```text
使用 forge-2d-sprite 制作现代像素风角色行走图，输出透明图集和预览 GIF。
```

```text
使用 forge-video-to-sprite 处理我提供的 MP4，导出脚部对齐的 24 帧精灵条和预览 GIF。
```

处理本地视频前请手动安装 FFmpeg/FFprobe，并安装 Pillow：
`python -m pip install -e ".[image]"`。需要语义清理时，可按文档选择
`.[background]` 或 `.[matting]`，再选择 rembg CPU 或 CUDA 后端。海螺 API
使用 `MINIMAX_API_KEY`；即梦 API 使用 `JIMENG_ACCESS_KEY` 和
`JIMENG_SECRET_KEY`。官方 `mmx` 与 `dreamina` CLI 是可选兼容路径。

## Unity 集成

Unity 包位于
[`integrations/unity/com.game-visual-forge.tilemap`](integrations/unity/com.game-visual-forge.tilemap)。
它会把经过验证的 Tilemap 资源包导入为可复用的纹理、Tile、Palette 和 Tilemap
Prefab，并附带 EditMode 与 PlayMode 测试。

## 仓库结构

```text
skills/       Codex Skill 说明和启动器
src/          共享契约、路由、处理器和报告
integrations/ Unity Tilemap 包及测试
assets/       小型示例和展示素材
install/      手动安装指南
```

## 开发检查

请在仓库根目录（即包含 `tests/` 的目录）运行测试：

`skills/` 目录下的文件统一使用英文；中文公共文档仅保留在 `README.zh-CN.md`。

```powershell
Set-Location "game-visual-forge项目路径"
python -m unittest discover -s tests -q
```

## 许可证

[MIT](LICENSE)
