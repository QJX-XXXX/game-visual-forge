---
name: generate-2d-sprite
description: "Generate production-oriented 2D game assets from natural-language requests, references, or existing images, including characters, creatures, props, effects, frames, sheets, and transparent exports."
---

# Generate 2D Sprite

先从用户请求建立并确认 `AssetBrief`。M0 只生成零网络 `dry-run`，不生成媒体。
图片来源默认先使用 Agent 原生工具。原生不支持时，询问是否使用第三方；原生生成失败或质量不达标时，询问“继续尝试原生”或“使用第三方”。
进入第三方流程后，每次都由用户选择即梦或通义万相，不得根据凭证、登录状态或历史自动选择。
第三方预检和费用摘要完成后必须取得独立付费确认。不得自动安装工具，不得自动重新提交失败或 `submission_unknown` 的付费任务。
用户提供已有图片时跳过生成。
确定性操作统一委托给：

```powershell
python skills/generate-2d-sprite/scripts/run.py dry-run `
  --brief <brief.json> --out-dir <output> --now <utc-rfc3339>
```
