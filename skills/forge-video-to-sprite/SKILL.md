---
name: forge-video-to-sprite
description: "Convert generated or existing video into 2D Sprite animation with safe provider selection, recoverable jobs, frame extraction, sampling, cleanup, alignment, and exports."
---

# Forge Video to Sprite

先确认动作、角色、视角、循环、起止状态、镜头和背景，再建立 `AssetBrief`。用户提供已有 MP4 时跳过图像与视频生成；当前 M0 只支持零网络 `dry-run`，不调用服务商或 FFmpeg。

需要首帧或参考图时，默认先使用 Agent 原生工具。原生不支持或质量不达标时，要求用户选择替代来源；每次都由用户选择即梦或万相。

任何第三方任务都必须先明确选择来源，再展示模型、模式、素材和费用，并取得独立付费确认。不得自动安装工具，不得自动重新提交失败或 `submission_unknown` 的任务；查询、恢复、下载或本地拆帧失败都不能触发新的视频生成。

后续里程碑会在 clean-room 边界内处理视频媒体；当前仅规划：

```powershell
python skills/forge-video-to-sprite/scripts/run.py dry-run `
  --brief <brief.json> --out-dir <output> --now <utc-rfc3339>
```
