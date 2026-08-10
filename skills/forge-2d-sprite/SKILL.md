---
name: forge-2d-sprite
description: "Generate production-oriented 2D game assets from natural-language requests, references, or existing images, including characters, creatures, props, effects, frames, sheets, and transparent exports."
---

# Forge 2D Sprite

Use the shared CLI to orchestrate 2D Sprite generation, ingestion, processing,
and quality validation. Interpret the user request, invoke a native Agent image
tool when selected, and obtain every required user choice. Leave deterministic
media processing to the local runtime. Never duplicate processing code or
credentials in this Skill.

## Standard interaction

Submit one grouped intake card that collects asset type and identity, action,
direction and frame count, art direction and references, background treatment,
canvas/anchor/output formats, engine delivery, and source policy. Ask once for
all missing or contradictory fields; do not repeat answered questions. Route
the source only after the user confirms the consolidated summary.

## Source order

1. Prefer an existing image. Select `existing-file` and run `sprite ingest`.
2. When no image exists, check whether the Agent exposes a suitable native image tool.
3. When native generation is available and selected, build the prompt package,
   generate the image, and return its local path to the `RawImageRecord` flow.
4. If native generation is unavailable, ask the user to choose Jimeng,
   Wanxiang, a configured local image tool, or an existing image.
5. If native generation fails or its quality is rejected, ask the user to retry
   native generation, switch the source, accept the current image, or stop.
6. After entering a third-party route, ask the user to choose Jimeng or Wanxiang every time.
   Never infer the provider from credentials, login state, or history.

## Paid submission gate

Before a third-party submission, display and confirm the provider, model, non-sensitive parameters, quantity, cost, currency, and request fingerprint.
One confirmation authorizes one submission and must be consumed and persisted
before invoking the external CLI.

Never install dependencies, CLIs, models, or credentials automatically.
Never resubmit a failed or `submission_unknown` task; recover an unknown submission
only through query or manual provider verification.

## CLI commands

Every command emits versioned JSON. `plan` and `route` do not access the
network; `ingest`, `process`, and `validate` operate only on local files.

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

The first validation keeps staging and reports `needs_attention` until a manual
review is supplied. The review must contain exactly these six checks, each set
to `passed` or `failed`:

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

Run `validate` again with `--visual-review`. Publish the final directory only
when deterministic validation and all six visual checks pass.
