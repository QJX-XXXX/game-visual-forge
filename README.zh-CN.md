# Game Visual Forge

[English](README.md) | 简体中文

Game Visual Forge 是一个仓库内使用的四个 Codex Skills 集合，覆盖可玩 2D 地图、2D 精灵、视频转精灵，以及用户明确提出的游戏音效制作。Skill 会把自然语言需求转换为经过验证的资源包或 Unity 可交付结果。

## Skills

| Skill | 用途 | 常见输出 |
| --- | --- | --- |
| [`forge-2d-map`](skills/forge-2d-map/SKILL.md) | 可行走 2D 地图、Tilemap、地形、碰撞、建筑和 Unity 交付 | 地图包、预览、摆放数据、质量证据 |
| [`forge-2d-sprite`](skills/forge-2d-sprite/SKILL.md) | 角色、生物、NPC、道具、特效和动画图集 | 透明精灵图集、帧文件、GIF 预览、元数据 |
| [`forge-video-to-sprite`](skills/forge-video-to-sprite/SKILL.md) | 将指定视频动作转换为高密度精灵帧 | 抽帧、精灵条、GIF 预览、元数据 |
| [`forge-text-audio`](skills/forge-text-audio/SKILL.md) | 明确请求的 SFX、UI 音效、动作音效和环境音 | 审核后的 44,100 Hz 16-bit PCM WAV、Unity AudioClip 清单 |

## 提供的能力

- 使用自然语言收集风格、布局、运行时和交付格式等关键选择。
- 需要新视觉素材时可使用内置生图，也支持用户提供已有素材。
- 使用确定性的本地处理、质量报告和可复现清单。
- 地图交付包含可行走区域、碰撞、对象、入口和 Unity Tilemap 支持。
- `forge-video-to-sprite` 使用 FFmpeg/FFprobe、本地时间戳抽帧、rembg/Chroma 清理、稳定对齐、图集和运动质量证据。
- `forge-text-audio` 使用本地 `stable-audio-tools` 和 Stable Audio 3 `small-sfx`，支持 text-to-audio、redraw、inpaint、continue 四种模式，只发布 WAV，并要求最终试听审核。

![HD 背景移除对比](assets/readme/rembg-production-comparison-on-gray.jpg)

## 安装和手动依赖

- [Codex 安装指南](install/codex/README.md)
- [Claude 安装指南](install/claude/README.md)

安装指南只负责手动复制仓库，不会自动安装 Provider、FFmpeg、凭证或模型。

视频处理需要手动安装 FFmpeg 和 FFprobe，并可安装 Pillow：

```powershell
python -m pip install -e ".[image]"
```

HD 清理使用 Pillow、NumPy/SciPy 和 rembg 的 `birefnet-general` 模型；按机器选择 CPU 或 CUDA 后端：

```powershell
python -m pip install -e ".[background]"
python -m pip install "rembg[cpu]"
python -m pip install "rembg[gpu]"
python -m pip install -e ".[matting]"
python -c "from rembg import new_session; new_session('birefnet-general')"
```

模型目录可通过 `U2NET_HOME` 指定。PyMatting 适合需要额外软边修补的情况，但速度更慢；CPU 兼容性更好，CUDA 适合已验证的批处理环境。

`forge-text-audio` 需要手动安装官方 `stable-audio-tools`，接受 Stable Audio 3 的 license acceptance，在本地缓存 `stabilityai/stable-audio-3-small-sfx`，并安装 FFmpeg/FFprobe。仓库不会下载权重、自动安装依赖或调用托管音频 API。

视频 Provider 的 API/CLI 兼容路径是可选的：MiniMax 使用 `MINIMAX_API_KEY`，即梦使用 `JIMENG_ACCESS_KEY` 和 `JIMENG_SECRET_KEY`；`mmx` 和 `dreamina` CLI 由用户手动配置。

## 请求示例

```text
使用 forge-2d-map 制作俯视角村落：南北向小溪、一座可通行木桥、建筑入口、碰撞和 Unity Tilemap。
```

```text
使用 forge-2d-sprite 制作现代像素风角色行走图，输出透明图集和预览 GIF。
```

```text
使用 forge-video-to-sprite 处理我提供的 MP4，导出脚部对齐的 24 帧精灵条和预览 GIF。
```

```text
使用 forge-text-audio 制作三组干净的铁剑击中钢盾音效，不要音乐和人声，审核候选并准备 Unity AudioClip。
```

## Unity 集成

Tilemap 包位于 [`integrations/unity/com.game-visual-forge.tilemap`](integrations/unity/com.game-visual-forge.tilemap)，音频包位于 [`integrations/unity/com.game-visual-forge.audio`](integrations/unity/com.game-visual-forge.audio)。音频包只导入并配置 AudioClip，不修改场景；只有用户明确要求时，才通过 Unity MCP 放置 AudioSource。

## 仓库结构

```text
skills/       Codex Skill 说明和启动器
src/          共享合同、路由、本地处理和报告
integrations/ Unity Tilemap 与 AudioClip 包及测试
assets/       小型示例和展示素材
install/      手动安装指南
```

## 开发检查

请在仓库根目录（包含 `tests/` 的目录）运行：

```powershell
Set-Location "game-visual-forge项目路径"
python -m unittest discover -s tests -q
```

## 许可证

[MIT](LICENSE)
