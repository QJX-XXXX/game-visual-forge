# Provider workflow

## Contents

- [Route and backend](#route-and-backend)
- [MiniMax Hailuo](#minimax-hailuo)
- [Jimeng](#jimeng)
- [Local subprocess protocol](#local-subprocess-protocol)
- [Paid confirmation and recovery](#paid-confirmation-and-recovery)

## Route and backend

The supported generated-video providers are MiniMax Hailuo and Jimeng. Each has
two explicit backends:

| Provider | API backend | CLI compatibility backend |
| --- | --- | --- |
| MiniMax | REST API with the selected China/global region and current model snapshot | official `mmx` CLI and its existing local authentication/account context |
| Jimeng | Volcengine Jimeng Visual REST API with local AK/SK HMAC signing | official `dreamina` CLI and its existing OAuth/account-credit context |

API and CLI task IDs, credentials, billing, and recovery calls are not
interchangeable. A capability or credential check only reports availability.
The user must choose the provider and backend before preflight and the choice is
stored in the attempt.

Install and authenticate these tools yourself according to their official
instructions. This repository does not install, update, log in to, or copy any
credential file.

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
