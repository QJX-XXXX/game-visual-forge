---
name: video-to-2d-sprite
description: "Convert generated or existing video into 2D Sprite animation with safe provider selection, recoverable jobs, frame extraction, sampling, cleanup, alignment, and exports."
---

# Video to 2D Sprite

先确认动作、角色、视角、循环、起止状态、镜头和背景，再建立 `AssetBrief`。用户提供已有 MP4 时跳过图片与视频生成。M0 只生成零网络 `dry-run`，不调用供应商或 FFmpeg。
需要首帧或参考图时默认先使用 Agent 原生工具。原生不支持时询问是否使用第三方；原生失败或质量不达标时询问“继续尝试原生”或“使用第三方”。
进入第三方图片流程后，每次都由用户选择即梦或通义万相。
后续里程碑 clean-room 重写并保留 MiniMax REST、MiniMax CLI、Dreamina CLI、即梦视觉 REST、Grok/Agent 原生视频工具和已有 MP4。
任何第三方任务都必须先明确选择来源，再显示模型、模式、素材和费用，并取得独立付费确认。
不得自动安装工具，不得自动重新提交失败或 `submission_unknown` 的任务；查询、恢复、下载或本地拆帧失败都不能触发新的视频生成。
确定性操作统一委托给：

```powershell
python skills/video-to-2d-sprite/scripts/run.py dry-run `
  --brief <brief.json> --out-dir <output> --now <utc-rfc3339>
```
