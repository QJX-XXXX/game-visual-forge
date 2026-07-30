---
name: generate-2d-map
description: "Generate production-oriented 2D game maps with explicit visual, layer, runtime-object, collision, and export models."
---

# Generate 2D Map

先确认地图视觉模型、图层、运行时对象、碰撞和交付目标，再建立 `AssetBrief`。M0 只生成零网络 `dry-run`，不生成地图图片或运行时数据。
需要生成底图或 Props 时默认先使用 Agent 原生工具。原生不支持时，询问是否使用第三方；原生失败或质量不达标时，询问“继续尝试原生”或“使用第三方”。
进入第三方流程后，每次都由用户选择即梦或通义万相，不得从凭证或历史自动选择平台。
第三方提交必须经过独立付费确认；不得自动安装工具，不得自动重新提交失败或 `submission_unknown` 的任务。
用户提供已有地图素材时跳过生成。
确定性操作统一委托给：

```powershell
python skills/generate-2d-map/scripts/run.py dry-run `
  --brief <brief.json> --out-dir <output> --now <utc-rfc3339>
```
