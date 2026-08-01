# Game Visual Forge

### 可选：标准化交付尺寸

当游戏需要统一尺寸和锚点时，可在请求中设置 `delivery_normalization`。流程会保留原有的
透明 `frames/` 输出，然后按每帧可见 alpha 边界裁切，对整个动画使用同一缩放比例，并在
`delivery/` 下额外导出标准化交付包。落地角色使用 `feet`，道具或悬浮资产使用 `center`。

```json
"delivery_normalization": {
  "canvas_width": 1024,
  "canvas_height": 1024,
  "anchor": "feet",
  "fit_scale": 0.88
}
```

这是交付布局步骤，不会改善抠图本身；它可能让细微色边不那么显眼，但也会柔化细天线、手指或
发丝。manifest 会记录标准化交付包的源裁切边界和共享缩放比例。

[English](README.md) | 简体中文

Game Visual Forge 是一组独立的 Agent Skills，用于生成 2D Sprite、面向生产的
2D 地图，以及 Video -> 2D Sprite 动画。

### M0 范围

M0 提供版本化数据契约、安全的任务状态、零网络执行计划和三个 Skill 基础骨架。
M0 不调用真实生成 Provider，也不生成媒体文件。

### M1 二维精灵生成

M1 增加版本化 `SpriteRequest`、明确的 `CapabilityRouter` 路由决策、服务商付费
确认门禁、本地图像导入、确定性的帧/图集/GIF 处理、`QualityReport` 和
`AssetManifest`。

已有图像、Agent 原生图像和未来的第三方图像都会进入同一条本地处理路径。Pillow
是本地图像处理的可选依赖，rembg 是可选的背景移除后端；系统不会自动安装它们。

### HD 背景移除

对于使用纯色 `#FF00FF` 背景生成的 HD 精灵，可通过
`pip install -e ".[background]"` 安装默认高质量后端。运行时先使用 CUDA 执行
BiRefNet-General，失败后使用 CPU 重试；只有 rembg 不可用或所有可用 Provider 都失败时，
才降级到确定性的洋红色键抠图。

![HD 背景移除效果对比](assets/readme/rembg-production-comparison-on-gray.jpg)

本次对比使用同一张 1024 x 1536 生成图。alpha 不低于 8/255 的像素视为可见像素。
洋红占比等于“可见的洋红近似像素数 ÷ 全部可见像素数”，因此衡量的是角色内部及边缘
的颜色污染，不受空白画布面积影响。

| 结果 | 适用情况 | 洋红像素 | 可见像素 | 占比 |
| --- | --- | ---: | ---: | ---: |
| Chroma Fallback | rembg 不可用，需要人工检查 | 24,799 | 487,649 | 5.0854% |
| BiRefNet Only | 语义处理中间结果，不直接导出 | 31,081 | 496,889 | 6.2551% |
| 默认 HD / Known-BG | 推荐的最终输出 | 81 | 472,640 | 0.0171% |
| 可选 PyMatting | 显式启用的精细模式 | 151 | 482,322 | 0.0313% |

Chroma Fallback 直接移除接近已知洋红键色的像素，不需要模型且结果确定；但是头发和
衣摆的抗锯齿边缘已经混入前景色与洋红色，因此仍会留下可见轮廓。默认 HD 路径先融合
BiRefNet 语义 alpha 与从画布边缘连通的色键证据，再根据已知洋红背景反推前景颜色；
对不稳定的低 alpha 像素，则使用附近可靠的前景颜色修复。PyMatting 根据同一个融合
遮罩建立 Trimap，再分别求解 alpha 和前景颜色。它可通过
`pip install -e ".[matting]"` 安装并使用 `"rembg_refinement": "pymatting"`
显式启用，但由于计算开销更大且在本图上没有更好，默认保持关闭。表中数据只代表本次
验证图，并不是所有图片上的通用模型排名。

### 路由与安全规则

- 已有图像优先。
- 没有已有图像时检查 Agent 原生图像工具；支持时使用原生路径。
- 原生能力不支持 -> 由用户选择第三方 Provider、本地工具或已有素材。
- 原生生成失败或质量不达标 -> 只有在确认后，才能进入既定兜底或选择流程。
- 每次使用即梦或通义万相，都必须明确确认 Provider、模型、参数、数量、费用、币种和请求指纹。
- 不得根据凭证、登录状态或历史选择自动选择服务商，不得静默重新提交付费任务。
- `submission_unknown` 只能查询或人工核对。
- M1 不包含地图、视频、MP4、FFmpeg、自动安装依赖或自动付费重试。

### 安装

- [Codex 安装指南](install/codex/README.md)
- [Claude 安装指南](install/claude/README.md)

### 验证命令

```powershell
python -m unittest discover -s tests -v
python skills/forge-2d-sprite/scripts/run.py sprite plan `
  --request <request.json> --out-dir <output> --now <utc-rfc3339>
```
