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
- 对付费或外部任务提供 Provider、费用和提交确认门禁。

## 效果展示

### 可玩地图交付

![Unity 中的自适应河流穿越地图](assets/readme/adaptive-river-crossing-map-unity-game-view.png)

示例包含 Tilemap 资源包、分层地图、桥连通性、碰撞数据和 Unity 验收证据。

### HD 精灵清理

![HD 背景移除效果对比](assets/readme/rembg-production-comparison-on-gray.jpg)

本地处理器会导出透明素材，并记录清理结果。

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

```powershell
python -m unittest discover -s tests -q
```

## 许可证

[MIT](LICENSE)
