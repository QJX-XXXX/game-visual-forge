---
name: forge-2d-sprite
description: "Generate production-oriented 2D game assets from natural-language requests, references, or existing images, including characters, creatures, props, effects, frames, sheets, and transparent exports."
---

# Forge 2D Sprite

使用共享 CLI 编排二维精灵生成、导入、处理和质量验证。Skill 负责理解用户请求、调用 Agent 原生图像工具和取得用户选择；本地运行时负责确定性处理。不得在 Skill 中复制图像处理实现或凭据。

## 标准交互

首次只提交一张分组需求卡，一次收集资产类型与身份特征、动作/朝向与帧数、画风与参考图、背景处理、画布/锚点/输出格式、引擎交付和来源策略。合并询问缺失或矛盾的字段，不得逐字段重复提问；用户确认汇总后再进入来源路由。

## 来源顺序

1. 已有图像优先，直接选择 `existing-file` 并执行 `sprite ingest`。
2. 没有已有图像时，检查 Agent 是否提供合适的原生图像工具。
3. 原生能力可用时使用 Agent 原生图像工具，生成提示词包后把本地图像交回 `RawImageRecord` 流程。
4. 原生能力不支持时，要求用户选择即梦、万相、已配置的本地图像工具或已有图像。
5. 原生生成失败或质量不合格时，要求用户选择继续尝试原生、切换来源、接受当前图像并继续，或停止。
6. 进入第三方流程后，每次都由用户选择即梦或万相；不得根据凭据、登录状态或历史选择自动选择服务商。

## 付费门禁

第三方提交前，展示并确认服务商、模型、非敏感参数、数量、费用、币种和请求指纹。每份确认只授权一次提交，必须在调用外部 CLI 前消费并持久化。

不得自动安装依赖、CLI、模型或凭据。不得自动重新提交失败或 `submission_unknown` 的任务；未知提交只能查询或人工核对。

## CLI 命令

所有命令都输出版本化 JSON；`plan`、`route` 不访问网络，`ingest`、`process`、`validate` 只操作本地文件。

```powershell
python skills/forge-2d-sprite/scripts/run.py sprite plan `
  --request <request.json> --out-dir <output> --now <utc-rfc3339>

python skills/forge-2d-sprite/scripts/run.py sprite route `
  --request <output/sprite-request.json> --capabilities <capabilities.json> `
  --out <output/source-decision.json> --state <output/job-state.json> `
  --now <utc-rfc3339>

python skills/forge-2d-sprite/scripts/run.py sprite ingest `
  --request <output/sprite-request.json> --decision <output/source-decision.json> `
  --image <repo-relative-image> --repo-root <repo> --out <output/raw-image.json> `
  --state <output/job-state.json> --now <utc-rfc3339>

python skills/forge-2d-sprite/scripts/run.py sprite process `
  --request <output/sprite-request.json> --raw-image <output/raw-image.json> `
  --repo-root <repo> --out-dir <repo>/outputs/<asset-id> `
  --state <output/job-state.json> --now <utc-rfc3339>

python skills/forge-2d-sprite/scripts/run.py sprite validate `
  --request <output/sprite-request.json> --raw-image <output/raw-image.json> `
  --processing-result <staging>/processing-result.json --repo-root <repo> `
  --staging-dir <staging> --final-dir <repo>/outputs/<asset-id> `
  --visual-review <output/visual-review.json> `
  --state <output/job-state.json> --now <utc-rfc3339>
```

首次验证会保留暂存目录并进入 `needs_attention`，等待人工视觉审查。审查文件必须使用以下完整且唯一的六项检查；每项值只能是 `passed` 或 `failed`：

```json
{
  "schema_version": 1,
  "checks": {
    "character-identity-consistency": "passed",
    "action-and-direction-correctness": "passed",
    "equipment-continuity": "passed",
    "anatomy-and-silhouette": "passed",
    "unwanted-text-or-watermark": "passed",
    "semantic-duplicate-frames": "passed"
  }
}
```

提供该审查文件后再次运行带 `--visual-review` 的 `validate`；确定性检查和六项视觉检查都通过时才发布最终目录。
