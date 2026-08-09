# Provider workflow

## Contents

- [Route and backend](#route-and-backend)
- [MiniMax Hailuo](#minimax-hailuo)
- [Jimeng](#jimeng)
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
The initial compatible profile is `MiniMax-H3` using `/v2/video_generation` and
its content-array request. A discovered model without a compatible profile is
shown as `discovered-unprofiled` and cannot be submitted through the API. It is
not silently hidden.

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
