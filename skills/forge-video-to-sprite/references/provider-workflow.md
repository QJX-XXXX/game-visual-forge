# Provider workflow

## Contents

- [Route and backend](#route-and-backend)
- [Local ComfyUI MiniMax H3](#local-comfyui-minimax-h3)
- [MiniMax Hailuo](#minimax-hailuo)
- [Jimeng](#jimeng)
- [Local subprocess protocol](#local-subprocess-protocol)
- [Paid confirmation and recovery](#paid-confirmation-and-recovery)

## Route and backend

Generated video has one local MCP route and two hosted-provider routes:

| Route | Backend | Execution boundary |
| --- | --- | --- |
| `comfyui-h3` | `comfy-mcp` | Comfy MCP drives a local ComfyUI MiniMax H3 graph; Cloud or partner nodes inside the graph are a separate spend boundary |
| `minimax` | `api` or `cli` | REST API with the selected region, or official `mmx` CLI with its existing local account context |
| `jimeng` | `api` or `cli` | Jimeng Visual REST API with local AK/SK signing, or official `dreamina` CLI with its existing account context |

API and CLI task IDs, credentials, billing, and recovery calls are not
interchangeable. A capability or credential check only reports availability.
The user must choose the route and backend before preflight; the choice is
stored in the route decision or hosted-provider attempt.

Install and authenticate these tools yourself according to their official
instructions. This repository does not install, update, log in to, or copy any
credential file during ordinary generation work. Only an explicit installation
request should hand off to the repository [Agent guide](../../install/agent/README.md).

## Local ComfyUI MiniMax H3

This route is conditional on [Comfy MCP](https://docs.comfy.org/agent-tools/mcp#installation)
and the [MiniMax H3 Prompt Writing Skill](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/README.md#installation).
If either dependency is unavailable during ordinary generation work, report the
appropriate official link and stop this route without installing anything.
Existing-file and hosted-provider routes remain usable. Only when the user
explicitly asks to install or enable this workflow should you hand off to the
repository [Agent guide](../../install/agent/README.md); normal generation
never activates installer authority.

Use `source_preference: comfyui-h3`, `backend: comfy-mcp`, and no external
`provider`. After `server_info` confirms a running local ComfyUI, write this
availability artifact for the repository router:

```json
{"backends":{"comfyui-h3":["comfy-mcp"]}}
```

Do not infer availability from installed files alone. Use the live Comfy MCP
capabilities to inspect the target, installed nodes and models, and validate the
selected workflow before execution. Do not install a workflow, custom node, or
model. If no runnable MiniMax H3 graph exists, report the missing capability and
stop.

### H3 prompt handoff

Invoke the H3 Prompt Writing Skill rather than recreating its prompt rules.
Map the request modes as follows:

| Forge mode | H3 mode | Required media |
| --- | --- | --- |
| `t2v` | T2VA | none |
| `i2v-first` | I2VA | first frame |
| `i2v-last` | L2VA | last frame |
| `i2v-first-tail` | FL2VA | first and last frames |
| `reference-to-video` | Ref2VA | reference media |

Preserve the exact H3 field names, section order, labels, and timing produced by
that Skill. Bind the effective duration to 4–15 whole seconds. The sprite
pipeline records whether the fetched video has audio but does not export audio.

Persist the optimized prompt as UTF-8 `comfyui-h3-prompt.txt` before graph
execution. Bind its SHA-256 together with the request fingerprint, reference
paths, roles and hashes, workflow JSON path and hash, Comfy target, H3
checkpoint/model, duration, resolution, and sanitized parameters in
`comfyui-h3-generation.json`. The record has `route`, `backend`, `prompt`,
`references`, `workflow`, `spend`, `run`, and `output` sections; initialize the
last two before execution and update them with `prompt_id`, terminal status,
selected video path, and video SHA-256. Do not store credentials, Base64 media,
authorization headers, signed URLs, or raw service responses.

### Spend boundary and recovery

A graph made entirely of local nodes and local weights has no paid-submit gate.
Before running any graph, inspect it for Comfy Cloud, partner-API, or other
credit-consuming nodes. Show the provider or node, model, parameters, duration,
resolution, billing context, estimate status, prompt hash, workflow hash, and
request fingerprint. If the graph can consume credits or the boundary cannot be
verified, obtain explicit confirmation bound to those values. Any change
invalidates that confirmation.

Run the validated graph once and persist the returned `prompt_id` immediately.
Use the available Comfy MCP job/status or wait operation to recover it and the
output-fetch operation to copy its completed output. If the run result is
unknown, inspect the existing queue/history before considering another run;
never rerun automatically. A non-terminal record for the same request,
prompt, and workflow hashes must be recovered rather than replaced by a second
run. If ComfyUI accepted the graph but no `prompt_id` was persisted, bind an
existing queue/history item only when it can be identified uniquely; otherwise
stop for user selection and keep the state uncertain.

Record the final job status, fetched repository-relative video path, and video
SHA-256 without storing transient output URLs. If a graph produces multiple
complete videos, show their paths, media properties, and hashes and ask the user
to select one. Persist that choice; never choose by list order, filename, or
modification time.

The workflow must yield one complete MP4, MOV, or WebM with a decodable video
stream. Treat missing, partial, still-image-only, or ambiguous outputs as needing
attention. Once fetched, keep the source immutable and continue through the
standard ingest, timestamp sampling, cleanup, review, and validation stages.

## MiniMax Hailuo

Set `MINIMAX_API_KEY` only in the current process when using the API. The adapter
refreshes the official model list and stores a sanitized timestamped snapshot.
The compatible profile is `MiniMax-H3`. China-region API calls default to
`https://api.minimaxi.com`; global calls default to
`https://api.minimax.io`. A discovered model without a compatible profile is
shown as `discovered-unprofiled` and cannot be submitted through the API. It is
not silently hidden.

Official references: [H3 workflow](https://platform.minimaxi.com/docs/guides/video-generation),
[V2 create](https://platform.minimaxi.com/docs/api-reference/video-generation-v2-create),
and [V2 query](https://platform.minimaxi.com/docs/api-reference/video-generation-v2-query).

H3 creates tasks with `POST /v2/video_generation` and the official multimodal
`content[]` request. It supports 4–15 whole seconds, `768P` or `2K`, and
`adaptive`, `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, or `9:16`. Text-to-video
requires a concrete ratio. First/last-frame generation is always adaptive.
Reference generation accepts up to 9 images, 3 videos, and 3 audio files, with
12 total reference files; its roles are `reference_image`, `reference_video`,
and `reference_audio`. First/last-frame roles and reference roles cannot be
mixed in one request.

For a generated or local first-frame PNG, persist a repository-relative
`first_frame_path` and its `first_frame_sha256`; include the same digest in the
paid reference binding. The adapter verifies the bytes immediately before
submit and creates the H3 `Data URI` only in memory. It never stores Base64 in
the attempt, confirmation, receipt, or logs. Changing the image bytes, path,
mode, model snapshot, or parameters invalidates the previous confirmation.

Query H3 through `GET /v2/query/video_generation/{task_id}`. A succeeded task
returns its MP4 address in `task.content.url`; `download` streams that address
to the requested local path. The transient address, raw response, and API key
are not included in the sanitized receipt. Failed, cancelled, queued, or
running tasks are never downloaded.

The official `mmx` compatibility path records its version and video command
capability. It may validate a newly discovered model through a no-charge CLI
check when the installed CLI supports that check; it never updates the CLI.

## Jimeng

Set `JIMENG_ACCESS_KEY` and `JIMENG_SECRET_KEY` only in the current process when
using the API. The adapter canonicalizes the request body, signs it locally with
HMAC, and discards transient authorization material after transport. Provider
task IDs and download calls remain API-specific.

The official `dreamina` compatibility path checks version/help and uses its
existing account state. It does not read API secrets and cannot query an API
attempt.

## Local subprocess protocol

Repository provider launchers and their parent orchestrators exchange one JSON
object through a binary UTF-8 JSON stdin/stdout protocol. Successful stdout ends
with one newline.
Stdout decoding is strict; stderr is diagnostic-only and uses replacement for
invalid bytes. A malformed submit response remains `submission_unknown` and is
recovered only through query/download—never by automatic resubmission.

## Paid confirmation and recovery

Before confirmation, show:

- provider, backend, region, model and model-snapshot SHA-256;
- generation mode, duration, resolution, references and reference hashes;
- sanitized parameters, quantity, estimate amount/currency/status, and request
  fingerprint.

Persist the sanitized attempt in `prepared` or `awaiting_confirmation` state,
then persist the consumed confirmation before issuing exactly one submit call.
If the transport has no definitive receipt, save `submission_unknown`. Use only
`video provider query` and `video provider download` to recover it. Never issue
another submit from an uncertain or failed state.
