# Game Visual Forge

## English

Game Visual Forge is an independent set of Agent Skills for generating 2D
sprites, production-oriented 2D maps, and Video -> 2D Sprite animation.

This repository is a clean-room implementation. It does not depend on
`agent-sprite-forge` and is not a Codex Plugin.

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

### Routing and safety

- native supported -> native path
- native unsupported -> user chooses third party/local/existing
- native failure or quality rejection -> defined fallback/choice only after confirmation
- every Dreamina/Wanxiang third-party attempt has explicit provider/model/parameter/cost confirmation and no silent resubmission
- `submission_unknown` may only be queried or manually reconciled.
- M1 does not implement maps, video, MP4, FFmpeg, automatic dependency installation, or silent paid retries.

### Installation and references

- [Codex installation guide](install/codex/README.md)
- [Claude installation guide](install/claude/README.md)
- [M0 design specification](docs/superpowers/specs/2026-07-30-game-visual-forge-agent-skills-design.md)
- [M0 implementation plan](docs/superpowers/plans/2026-07-30-game-visual-forge-m0-foundation.md)
- [M1 design specification](docs/superpowers/specs/2026-07-30-game-visual-forge-m1-sprite-design.md)
- [M1 Chinese design specification](docs/superpowers/specs/2026-07-30-game-visual-forge-m1-sprite-design.zh-CN.md)
- [M1 implementation plan](docs/superpowers/plans/2026-07-30-game-visual-forge-m1-sprite.md)

### Verification

```powershell
python -m unittest discover -s tests -v
python skills/generate-2d-sprite/scripts/run.py dry-run `
  --brief examples/briefs/sprite-auto.json `
  --out-dir outputs/demo --now 2026-07-30T00:00:00Z
```

## 中文

Game Visual Forge 是一组独立的 Agent Skills，用于生成 2D Sprite、面向生产的
2D 地图，以及 Video -> 2D Sprite 动画。

本仓库采用 clean-room 方式实现，不依赖 `agent-sprite-forge`，也不是 Codex
Plugin。

### M0 范围

M0 提供版本化数据契约、安全的任务状态、零网络执行计划和三个 Skill 基础骨架。
M0 不调用真实生成 Provider，也不生成媒体文件。

### M1 二维精灵生成

M1 增加版本化 `SpriteRequest`、明确的 `CapabilityRouter` 路由决策、服务商付费
确认门禁、本地图像导入、确定性的帧/图集/GIF 处理、`QualityReport` 和
`AssetManifest`。

已有图像、Agent 原生图像和未来的第三方图像都会进入同一条本地处理路径。Pillow
是本地图像处理的可选依赖，rembg 是可选的背景移除后端；系统不会自动安装它们。

### 路由与安全规则

- 已有图像优先。
- 没有已有图像时检查 Agent 原生图像工具；支持时使用原生路径。
- 原生能力不支持 -> 由用户选择第三方 Provider、本地工具或已有素材。
- 原生生成失败或质量不达标 -> 只有在确认后，才能进入既定兜底或选择流程。
- 每次使用即梦或通义万相，都必须明确确认 Provider、模型、参数、数量、费用、币种和请求指纹。
- 不得根据凭证、登录状态或历史选择自动选择服务商，不得静默重新提交付费任务。
- `submission_unknown` 只能查询或人工核对。
- M1 不包含地图、视频、MP4、FFmpeg、自动安装依赖或自动付费重试。

### 安装与参考资料

- [Codex 安装指南](install/codex/README.md)
- [Claude 安装指南](install/claude/README.md)
- [M0 设计规范](docs/superpowers/specs/2026-07-30-game-visual-forge-agent-skills-design.md)
- [M0 实施计划](docs/superpowers/plans/2026-07-30-game-visual-forge-m0-foundation.md)
- [M1 设计规范](docs/superpowers/specs/2026-07-30-game-visual-forge-m1-sprite-design.zh-CN.md)
- [M1 实施计划](docs/superpowers/plans/2026-07-30-game-visual-forge-m1-sprite.md)

### 验证命令

```powershell
python -m unittest discover -s tests -v
python skills/generate-2d-sprite/scripts/run.py sprite plan `
  --request <request.json> --out-dir <output> --now <utc-rfc3339>
```
