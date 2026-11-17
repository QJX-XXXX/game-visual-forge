---
name: forge-2d-sprite
description: "Use when creating or processing production-oriented 2D game sprites, animation sheets, transparent PNG frames, characters, creatures, props, or effects from prompts, references, or existing images."
---

# Forge 2D Sprite

Use the shared CLI to orchestrate 2D Sprite generation, ingestion, processing,
and quality validation. Interpret the user request, invoke a native Agent image
tool when selected, and obtain every required user choice. Leave deterministic
media processing to the local runtime. Never duplicate processing code or
credentials in this Skill.

Before local CLI work, follow the [Python environment guide](../../install/python-environment.md).
Check the actual interpreter and task-specific dependencies. If Python or
packages are missing, explain the detected system and offer precise setup
steps or Agent assistance. Reuse existing setup authorization and verify the
chosen interpreter after configuration. Native image tools remain independent
of Python; report local processing as pending until its prerequisites are ready.

## Standard interaction

Submit one grouped intake card that collects asset type and identity, action,
direction and frame count, art direction and references, background treatment,
canvas/anchor/output formats, engine delivery, and source policy. Ask once for
all missing or contradictory fields; do not repeat answered questions. Route
the source only after the user confirms the consolidated summary.

Unless the user explicitly requests an opaque background, make transparent PNG
delivery the default and set `background_removal=auto` in the normalized Sprite
request. This policy expresses the delivery requirement independently from the
fallback processor chosen after generation.

## Seeded whole-strip animation

For any request with more than one frame, prefer a single coherent generation
request for the entire action. Use `seed_frame_path` when the user supplies an
approved seed; otherwise use the first approved reference image as the seed
metadata. Build one coherent whole animation sheet in the requested grid or
strip with the exact frame count and order. Do not generate animation cells as
independent images by default.

Preserve the seed identity, facing, palette, silhouette, outfit, equipment,
proportions, and transparent-background constraints across every frame. Set
`lock_frame1=true` only when the approved seed must become frame 01; the local
processor then replaces the generated first cell before alignment and records
the operation in the processing result. For engine delivery, use the existing
delivery normalizer so every frame receives the same shared scale and anchor,
and inspect the generated sheet or GIF before approval.

Use native image tools first when their advertised operations meet the request.
MiniMax is the recommended API when native capability is unavailable and the
user chooses an API. Follow the
[shared image API workflow](references/image-api.md) using `image provider`.
It works from Python with any Agent. The built-in imagegen
is one native tool option when advertised by the host Agent.
Treat reference-image editing, native transparency, whole-strip generation, and
fast targeted iteration as capabilities rather than model-name assumptions.
The capability declaration may expose operation tokens such as
`text-to-image`, `reference-image`, `native-alpha-generate`,
`native-alpha-edit`, and `whole-strip`; use the ones actually advertised.
Do not hard-code a model name; inspect the Agent capability declaration and let
the current tool choose its supported model or operation.

## Complex action boundary

Before source routing, warn the user when a request involves complex character motion,
including a long or multi-phase action, rapid rotation or tumbling, large pose
or scene-position changes, interaction between moving characters or objects,
or unusually strict identity, equipment, anatomy, and temporal continuity
requirements. Explain that image-grid generation can drift between
cells and recommend `forge-video-to-sprite`, which samples temporally related
frames from an existing or explicitly generated video. Ask the user to choose
whether to continue with `forge-2d-sprite` or switch to
`forge-video-to-sprite`; the Skill must not switch workflows automatically.

Give the same choice after visual review rejects generated Sprite frames for
identity drift, equipment discontinuity, anatomy changes, or incoherent
motion. Do not treat a switch recommendation as permission to preflight or
submit a video provider. If the user switches, start at the standard
interaction in `forge-video-to-sprite` and obtain every confirmation required
there. Keep short in-place actions such as idle, walk, run, compact attacks,
and small casts on the normal Sprite path unless the user requires unusually
strict temporal consistency.

## Source order

1. Prefer an existing image. Select `existing-file` and run `sprite ingest`.
2. When no image exists and source policy is `auto`, check the Agent's actual
   native operations and route to a suitable tool. Reference inputs require
   `reference-image`; text-only generation requires `text-to-image`.
3. When native generation is available, build the prompt package,
   generate the image, and return its local path to the `RawImageRecord` flow.
4. If native capability is unavailable, ask the user to choose an API,
   configured local image tool, or existing image. Recommend MiniMax among the
   APIs, with Jimeng and Wanxiang available. Credentials and preflight never
   count as source selection. Preflight only the provider the user selects.
5. If native generation fails or its quality is rejected, ask the user to retry
   native generation, switch the source, accept the current image, or stop.
6. For native failure or rejection, record `--native-outcome failed` or
   `quality-rejected` when routing again. Obtain an explicit source choice
   before API fallback and a verified quote/paid confirmation before submission.
   Explicit user source selections override the default order.

## Transparent PNG policy

When native generation is selected, ask the image tool for a true transparent PNG
with a real Alpha channel. Require background pixels to have alpha 0 and reject
rendered white, checkerboard, or color-key backgrounds as substitutes for
transparency. Keep the requested grid, containment, identity, and frame order
constraints in the same prompt package.

The prompt package's `transparent_background_prompt` is the project-owned,
verbatim background-extraction instruction. Append it unchanged to the native
transparent-generation prompt. If the first native PNG fails Alpha inspection
and the same native tool supports image editing, reuse that exact instruction
for at most one background-extraction edit before the local rembg fallback.

Before invoking processing that needs rembg, verify the background package
profile and selected model cache through the environment guide. If either is
missing, offer setup or help within the user's authorization before starting
that fallback. Do not create a rembg session just to discover an uncached model.

After native generation, ingest the unmodified PNG and run `sprite process` with
`background_removal=auto`. The processor inspects the original Alpha channel
before converting the image:

- If transparent pixels already exist, preserve the native Alpha data and skip
  background removal.
- If Alpha is absent, every pixel is opaque, or the tool returned an opaque white
  background, let the automatic path run rembg and inspect the resulting Alpha
  channel again.
- If rembg is unavailable, fails, or still returns a fully opaque image, stop with
  `needs_attention`. The asset must not be published or accepted through visual
  review alone.

Use explicit `chroma` only for a known color-key source. Use explicit `preserve`
only when the user requested an opaque background. Do not replace a failed
transparent-output check with a third-party submission without the source choice
and paid confirmation required above.

## Paid submission gate

Before a third-party submission, display and confirm the provider, model, non-sensitive parameters, quantity, cost, currency, and request fingerprint.
One confirmation authorizes one submission and must be consumed and persisted
before making the generation POST. The direct image API uses the shared
`image provider prepare`, `confirm`, `submit`, and `download` commands in the
[API reference](references/image-api.md).

Never install dependencies, CLIs, models, or credentials without authorization.
When the user authorizes Python setup, assist within that scope through the
[environment guide](../../install/python-environment.md); preserve existing
environments and separate package setup from model/cache downloads.
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
