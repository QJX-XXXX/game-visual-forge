---
name: forge-2d-map
description: "Generate production-oriented 2D game maps with explicit visual, layer, runtime-object, collision, and export models."
---

# Forge 2D Map

先确认地图视觉模型、图层、运行时对象、碰撞和交互目标，再建立 `AssetBrief`。当前 M0 只支持零网络 `dry-run`，不生成地图媒体或运行时数据。

需要生成底图或 Props 时，默认先使用 Agent 原生工具。原生不支持时，要求用户选择即梦、万相、本地图像工具或已有素材；每次都由用户选择来源。

第三方预检和费用摘要完成后必须取得独立付费确认。不得根据凭据或历史选择自动选择服务商，不得自动安装工具，不得自动重新提交失败或 `submission_unknown` 的任务。

```powershell
python skills/forge-2d-map/scripts/run.py dry-run `
  --brief <brief.json> --out-dir <output> --now <utc-rfc3339>
```
