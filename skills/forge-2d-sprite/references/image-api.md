# Image API workflow

For installed CLI and MCP execution, follow the [provider tool guide](../../../install/provider-tools.md).
It covers MiniMax/Wan official MCP, project Jimeng/model-specific Wan bridges, and backend-bound
attempts. Tool installation requires the user's confirmation.

Use the Agent's native image tool first when it supports the requested operation.
When native capability is missing, ask the user to select an API or another
source; recommend MiniMax among APIs. An explicit source choice overrides this
default. Neither credentials nor a preflight authorize an API fallback. This shared
Python CLI works with any Agent or directly from a terminal.
Keep the intact repository available.

## Providers and prerequisites

| Provider | Default model | Credential environment variables | Operation |
| --- | --- | --- | --- |
| MiniMax | `MiniMax-H3-Image` | `MINIMAX_API_KEY` | Synchronous generation/editing |
| Jimeng (`dreamina` alias retained) | `jimeng_t2i_v40` | `JIMENG_ACCESS_KEY`, `JIMENG_SECRET_KEY` | Async submit/query/download |
| Wanxiang | `wan2.7-image` | `DASHSCOPE_API_KEY` | Async submit/query/download |

Use Python 3.11+ and the existing Pillow image extra. No provider SDK or provider
CLI is required. Use the [Python environment guide](../../../install/python-environment.md)
when Python/packages are missing: inspect the actual OS/interpreter, give exact
instructions, or help configure an isolated environment within the user's
existing authorization. Installation and credential changes require authorization.
Configure credentials outside request files, in the process environment or a
user-managed secret store. Never print or persist their values.

`models` reports documented profiles, not account entitlement. `preflight` is
offline: it checks credential presence and the image runtime. Its
`authentication_verified=false` means live authentication and balance are untested.

```powershell
python skills/forge-2d-sprite/scripts/run.py image provider models
python skills/forge-2d-sprite/scripts/run.py image provider preflight --out <run>/preflight.json
```

Use `--provider jimeng`, `dreamina`, or `wanxiang` on these two commands to
inspect another provider after source selection. `auto` routing selects a
suitable native tool first. Otherwise the decision has no selected provider,
`requires_user_selection=true`, and `recommended_provider=minimax`. Ask for the
choice before preflighting/configuring an API. Local tools and existing images
also remain selectable. Paid confirmation is still required after API selection.

## Prepare a Sprite attempt

Complete normal intake and `sprite plan` first. A host without a native image
tool uses capabilities `{"schema_version":1,"supported":false,"operations":[]}`.
Route first without API selection or preflight. If native output fails or is
rejected, record `--native-outcome failed` or `quality-rejected` and ask the user
what source to try next. After the user selects MiniMax, run its offline
preflight and the following explicit API route:

```powershell
python skills/forge-2d-sprite/scripts/run.py sprite route `
  --request <run>/sprite-request.json --capabilities <capabilities.json> `
  --selection minimax --preflight <run>/preflight.json --out <run>/source-decision.json `
  --state <run>/job-state.json --now <utc-rfc3339>

python skills/forge-2d-sprite/scripts/run.py image provider prepare `
  --request <run>/sprite-request.json --decision <run>/source-decision.json `
  --parameters <run>/image-parameters.json --kind sprite `
  --model MiniMax-H3-Image --quantity 1 --repo-root <repo> `
  --state <run>/job-state.json --out <run>/image-attempt.json --now <utc-rfc3339>
```

Example `image-parameters.json` for one square sheet:

```json
{
  "region": "cn",
  "size": "1024x1024",
  "references": [{"path": "references/approved-hero.png"}]
}
```

Omit `references` to use the request's references and seed; use `[]` for
text-only generation. Paths are relative to `--repo-root`. Preparation hashes
every reference and submission verifies its bytes again. MiniMax and Wanxiang
submit the verified bytes as in-memory data URIs, including URL references.
Jimeng needs immutable public JPEG/PNG URLs; upload local references separately.
Signed reference URLs and embedded credentials are rejected.

Omit `prompt` to build the whole-sheet Sprite prompt with seed, identity,
frame-count, and grid constraints. An explicit prompt replaces it, so include
those constraints yourself. Quantity counts candidate images: an eight-frame
sheet is still quantity 1. Choose dimensions/aspect ratio for the declared grid
and inspect frame placement before acceptance.

MiniMax does not support native transparency. The API prompt asks for a uniform
removable background while the request retains transparent delivery. Continue
with `background_removal=auto` for rembg, or explicit chroma for a known color
key. Missing rembg or failed Alpha checks still yield `needs_attention`.

## Quote, confirm, and submit once

Obtain a current total quote from the selected provider/account. MiniMax pricing
depends on tokens and enhancement; this CLI does not invent a fixed image price.
Present provider, model, parameters, reference hashes, quantity, request
fingerprint, cost, and currency. Only after the user approves this paid attempt,
write a verified `CostEstimate` JSON: `schema_version=1`, `provider`, `currency`,
decimal string `amount`, `verified=true`, and `notice` explaining the quote's
source. The amount is the total for the attempt. Unverified quotes are rejected.

```powershell
python skills/forge-2d-sprite/scripts/run.py image provider confirm `
  --attempt <run>/image-attempt.json --quote <run>/verified-quote.json `
  --out <run>/paid-confirmation.json --now <utc-rfc3339>

python skills/forge-2d-sprite/scripts/run.py image provider submit `
  --attempt <run>/image-attempt.json --confirmation <run>/paid-confirmation.json `
  --repo-root <repo> --now <utc-rfc3339>

python skills/forge-2d-sprite/scripts/run.py image provider download `
  --attempt <run>/image-attempt.json --repo-root <repo> --now <utc-rfc3339>
```

`prepare` reads references but performs no paid generation. One confirmation
authorizes one POST and is consumed before submission. Changes to region,
workspace, prompt, quantity, or reference bytes require a new attempt and
approval. Do not edit attempts to retry. Concurrent submits are locked; no
generation POST is retried automatically. Persisted receipts exclude secrets,
inline media, raw responses, and transient result URLs.

MiniMax waits up to 600 seconds, requests PNG `b64_json`, and saves verified
images during submit. Download reuses local images, records the manifest, and
advances the optional parent job to `ready`. Choose an `outputs[].path`:

```powershell
python skills/forge-2d-sprite/scripts/run.py sprite ingest `
  --request <run>/sprite-request.json --decision <run>/source-decision.json `
  --image <repo>/<outputs[0].path> --image-attempt <run>/image-attempt.json `
  --repo-root <repo> --out <run>/raw-image.json `
  --state <run>/job-state.json --now <utc-rfc3339>
```

Then use normal `sprite process`, `sprite validate`, and all six visual checks.
`--image-attempt` verifies candidate hashes and preserves its model provenance.
API completion does not approve artwork or publish the final asset.

## Recovery

MiniMax has no image task-query API. Timeout or malformed output produces
`submission_unknown`: inspect saved candidates and resolve billing/outcome in
the provider account. Never repeat the POST. Explicit item failures retain
successful candidates with `needs_attention`; malformed/missing items stay
unknown. Review partial candidates before requesting a new paid attempt.
Each returned image is saved independently. If a local rename or receipt write
was interrupted, `download` also recovers verified staged/final candidate files
from this attempt's directory without sending another generation request.

Jimeng/Wanxiang persist a task ID. Query/download can be repeated without
another generation POST:

```powershell
python skills/forge-2d-sprite/scripts/run.py image provider query `
  --attempt <run>/image-attempt.json --repo-root <repo> --now <utc-rfc3339>
```

For unknown async submissions only, add `--task-id <provider-verified-task-id>`.
When an abnormal submission response contains a valid task ID, that ID is
retained with `submission_unknown` and can be queried directly.
Downloads re-query fresh result URLs (normally valid 24 hours), verify and save
each image independently, and resume interruptions without replacing saved
candidates. Failed, canceled, expired, or missing tasks need user/provider
resolution. A new generation always needs a new quote and confirmation.

## Model parameters and limits

- MiniMax: `MiniMax-H3-Image` or `MiniMax-H3-Image-Highspeed`; region `cn`
  (`api.minimax.cn`) or `global` (`api.minimax.io`); prompt 1–32000 characters;
  1–10 candidates; up to 16 JPEG/PNG/WebP references, 128–8192px, at most 4:1,
  64 MiB per file and encoded request. Use `size=auto`, `area=1K|2K|4K`, and
  `aspect_ratio=auto|X:Y` (components 1–300, ratio 1:3–3:1); or explicit
  `WIDTHxHEIGHT` with area 655360–20000000 and ratio 1:3–3:1. Explicit size
  excludes area/aspect_ratio. Here automatic area defaults to 1K. Total PNG
  response area is at most 20000000 pixels across all candidates. Optional
  boolean `aigc_watermark`; text-only boolean `disable_prompt_enhanced` requires
  explicit dimensions or ratio. No seed option.
- Jimeng: prompt at most 800 characters; region `cn-north-1`; width/height or
  pixel-area size (1024 squared–4096 squared); scale 0–1; min_ratio/max_ratio
  default 1:3–3:1. Force_single is true, quantity 1. Up to ten public JPEG/PNG
  references, at most 15 MiB/4096px, ratio 1:3–3:1. No seed field.
- Wanxiang: `wan2.7-image` or `wan2.7-image-pro`; region `cn-beijing` or
  `ap-southeast-1`; optional workspace_id selects its domain for submit/query.
  Prompt at most 5000 characters; up to nine opaque JPEG/PNG/BMP/WebP references,
  240–8000px, 20 MiB, ratio 1:8–8:1, no Alpha channel. Size 1K/2K or
  `WIDTH*HEIGHT`; 4K is pro text-only without sequential generation. Optional
  seed 0–2147483647 and booleans watermark/thinking_mode/enable_sequential.
  Quantity 1–4, or 1–12 sequentially; actual sequential count may be smaller.
  Output dimensions can vary slightly.

Unknown parameters are rejected before generation. HEIC/HEIF references and
provider-managed file IDs are outside this adapter's first release.

## Map handoff

The map Skill launcher supports the same `image provider` commands. Use native
first, then ask for the API source when needed. Route an explicitly selected
API with matching preflight, then prepare with `--kind map` for `map-request.json` or
`--kind tilemap` for `tilemap-request.json`. Provide explicit prompt/dimensions
for each foundation, atlas page, or object, each with its own confirmation.
Subsequent candidate attempts can link the same matching parent job state.
Feed downloaded paths into `map ingest` or `map tile` candidate preflight and
ingestion. Keep style, critical-asset, and assembled-map approvals; downloads
do not bypass gates or silently normalize external atlas geometry.

## Official sources (verified 2026-11-17)

- [MiniMax generations](https://platform.minimax.cn/docs/api-reference/image-generation-h3-generations)
- [MiniMax edits](https://platform.minimax.cn/docs/api-reference/image-generation-h3-edits)
- [MiniMax image guide](https://platform.minimax.cn/docs/guides/image-generation)
- [Jimeng image 4.0](https://docs.volcengine.com/docs/jimeng-ai/jimeng-ai-image-generation-40-interface-documentation?lang=zh)
- [Wan 2.7 image API](https://help.aliyun.com/zh/model-studio/wan-image-generation-and-editing-api-reference)
