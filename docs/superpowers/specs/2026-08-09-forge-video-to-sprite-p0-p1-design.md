# Forge Video to Sprite P0 + P1 Design

## 1. Goal

Turn `forge-video-to-sprite` from an M0 planning-only Skill into a complete,
recoverable video-to-Sprite workflow.

- P0 makes an existing local video usable end to end: inspect, trim, sample,
  extract, clean, align, export, validate, review, and publish.
- P1 adds paid video generation through MiniMax Hailuo and Jimeng. Both
  providers use an API-first backend and an official CLI compatibility backend.
- Every paid submit is explicitly confirmed, uniquely bound, persisted before
  transport, and never retried automatically after an uncertain outcome.
- The final published bundle is provider-neutral and reproducible from one
  immutable source video.

## 2. Current State

The Skill currently exposes only the generic top-level `dry-run` command and an
`AssetBrief`. The repository already has reusable image cleanup, rembg/chroma
fallback, frame alignment, delivery normalization, Sprite Sheet/GIF export,
quality reports, manifests, provider subprocess isolation, paid confirmation,
and recoverable job state.

It does not yet have a video-specific request, FFmpeg probing or extraction,
time-based sampling, video provenance, temporal quality checks, real MiniMax or
Jimeng adapters, model synchronization, or a complete video CLI workflow.

## 3. Scope

### 3.1 P0: Existing Video

Support user-provided or already-downloaded video without invoking any image or
video generation provider. Validate MP4, MOV, and WebM in the test matrix while
accepting any format that the selected FFmpeg installation can probe and
decode.

P0 includes:

- FFmpeg/FFprobe discovery and capability reporting;
- source-video hashing and media metadata;
- optional start/end trimming;
- timestamp-based loop-aware frame sampling;
- one or more requested frame densities;
- background preservation, chroma removal, or rembg cleanup;
- stable feet/bottom-center alignment and delivery normalization;
- frame, strip, sheet, GIF, contact-sheet, and diagnostic exports;
- deterministic and visual quality gates;
- staging and atomic final publication.

### 3.2 P1: Generated Video

Support exactly these video providers:

- MiniMax Hailuo;
- Jimeng.

Each provider has `api` and `cli` backends. API is the recommended default;
CLI is a compatibility backend for users who already have the official CLI,
authentication, subscription, membership, or account credits.

P1 includes capability preflight, model discovery, model compatibility,
estimate presentation, paid confirmation, one-shot submission, query, recovery,
download, provenance, and handoff to the P0 pipeline.

### 3.3 Non-goals

- Do not make MCP a required or primary provider transport.
- Do not install FFmpeg, provider CLIs, Python extras, models, or credentials.
- Do not write credentials, authorization headers, Base64 media, signed URLs,
  or provider response bodies into repository artifacts.
- Do not provide a general-purpose nonlinear video editor.
- Do not automatically regenerate a rejected, failed, timed-out, or uncertain
  paid task.
- Do not treat automatic image metrics as proof that an action is visually
  correct.
- Do not add another repository Skill or an alias for
  `forge-video-to-sprite`.

## 4. User Interaction and Approval Gates

The standard workflow has three user-facing confirmation points.

### 4.1 Creative and Delivery Summary

Extract known information from the request and conversation before asking
anything. Ask one consolidated question for missing or contradictory fields
instead of repeating similar questions. Summarize:

- character identity, action, view, camera behavior, loop, and start/end pose;
- background and cleanup intent;
- source: existing video, MiniMax, or Jimeng;
- generation mode and required reference frames;
- clip interval and frame densities;
- frame, strip, sheet, and GIF delivery requirements;
- anchor, canvas, pixel/HD processing mode, and target-engine notes.

Do not preflight a provider, prepare generated reference media, or create a
video task until this summary is accepted. Existing-video requests skip all
provider work after this gate.

### 4.2 Paid Submit Confirmation

Only generated-video routes have this gate. Present provider, backend, region,
model-catalog snapshot, model, mode, duration, resolution, input hashes,
billing context, estimate status, and one attempt fingerprint together.

An unverified price must be labeled as unverified and direct the user to the
provider console. Free trials and account credits still require confirmation.
Changing any bound value invalidates the confirmation.

### 4.3 Final Motion Review

After local processing and automated checks, present the source clip or chosen
interval, timestamped contact sheet, transparent GIF, anchor/bounds diagnostic,
motion-difference image, and final strips/sheets together.

Local extraction, cleanup, alignment, or export changes reuse the existing
video. Only a user request to generate a different video returns to provider
selection and a new paid confirmation.

## 5. Contracts

Add focused version-1 contracts rather than extending `AssetBrief` with
video-only fields.

### 5.1 `VideoSpriteRequest`

The request contains:

- `asset_id`, prompt/action name, output directory, and target-engine notes;
- source preference: `existing-file`, `minimax`, or `jimeng`;
- optional provider backend (`api` or `cli`) and region;
- generation mode: `t2v`, `i2v-first`, `i2v-first-tail`, or
  `reference-to-video` when the selected model supports it;
- first-frame, last-frame, and reference-media paths as applicable;
- loop flag, optional clip start/end seconds, and requested frame counts;
- outputs: frames, strips, sheets, and/or GIF;
- background removal: `preserve`, `chroma`, or `rembg`;
- optional chroma color and rembg refinement;
- processing mode: `pixel` or `hd`;
- delivery canvas, anchor, and fit scale.

Paths are repository-relative and normalized. Frame counts are positive,
unique, sorted for serialization, and bounded by an implementation safety
limit. The default when the user does not specify a density is 24 frames.

### 5.2 Provider and Model Contracts

Add:

- `VideoSourceDecision` for source, provider, backend, region, selection needs,
  and paid-confirmation needs;
- `VideoModelCatalogSnapshot` for provider, backend, region, refresh time,
  adapter/CLI version, discovered models, source, and snapshot hash;
- `VideoModelProfile` for endpoint generation, supported modes, reference
  roles, duration/resolution/ratio constraints, audio behavior, and backend
  support;
- `VideoGenerationAttempt` for request fingerprint, confirmation binding,
  provider/backend, model snapshot, non-secret parameters, task/file IDs,
  status, downloaded path, and SHA-256.

### 5.3 Media and Processing Contracts

Add:

- `VideoSourceRecord` for immutable local video path/hash, container, codecs,
  dimensions, display rotation, duration, average/real frame rates, variable-FPS
  status, frame count when known, audio presence, provider provenance, and
  request fingerprint;
- `VideoFrameRecord` for output index, source timestamp, source-frame index when
  known, raw/clean/delivery paths, and hashes;
- `VideoProcessingResult` for staging directory, frame sets, strips, sheets,
  previews, timing metadata, cleanup/alignment metadata, diagnostics, and
  attention state;
- `VideoQualityReport` for deterministic checks, temporal metrics, visual
  checks, and aggregate status.

## 6. Provider Architecture

The shared core invokes provider adapters through the repository's safe JSON
subprocess boundary. Each adapter supports `capabilities`, `models`,
`preflight`, `estimate`, `prepare`, `submit`, `query`, and `download`.

### 6.1 MiniMax Hailuo

Use one provider identity, `minimax`, with:

- `backend=api`: official MiniMax REST API, China/global region support, and
  pay-as-you-go API key read only from the current environment;
- `backend=cli`: official `mmx` CLI compatibility path using its existing local
  authentication and Token Plan context.

The API adapter supports both legacy and current endpoint generations through
explicit model profiles. Initial implementation must include the current
`MiniMax-H3` `/v2/video_generation` content-array request and retain profiles
for older models only when the selected account/backend still exposes them.

The CLI adapter validates the installed version, authentication, region,
billing context, and current video command capabilities. It does not read or
copy the CLI credential file and does not auto-update the CLI.

### 6.2 Jimeng

Use one provider identity, `jimeng`, with:

- `backend=api`: official Volcengine Jimeng Visual REST API using AK/SK from the
  current environment and local HMAC request signing;
- `backend=cli`: official `dreamina` CLI compatibility path using its existing
  OAuth/account-credit state.

API and CLI task IDs, authentication, billing, and recovery calls are not
interchangeable. A task always resumes with the backend saved in its attempt
record.

### 6.3 No Automatic Backend Switching

Provider or credential detection only reports availability. It never selects a
provider or changes a saved backend. A failure in one backend cannot create a
task in the other backend. If both are available, include backend choice in the
same consolidated source confirmation.

## 7. Model Synchronization

Model choice must stay current without allowing unknown paid payloads.

### 7.1 Live Discovery

At the model-selection stage:

- MiniMax API refreshes the official model-list endpoint for the selected
  account/region;
- MiniMax CLI records the current `mmx` version and video command capability;
- Jimeng API records the current product capability evidence available to the
  adapter and its official-source revision;
- Jimeng CLI records the current `dreamina` version and video command help.

Save a sanitized snapshot with a timestamp and SHA-256. Do not refresh silently
after paid confirmation.

### 7.2 Compatibility Profiles

Live discovery says that a model exists; a versioned profile says how to call
it safely. Only a discovered model with a compatible profile is directly
selectable on the API backend.

An unknown discovered model is shown as `discovered-unprofiled`, not hidden.
It cannot submit through the API until its endpoint and parameter profile are
implemented. If the current official CLI accepts that model in a no-charge
validation/dry-run, the user may explicitly choose the CLI compatibility
backend as the faster supported path.

Models that disappear from current discovery are not offered for new tasks,
but historical task query/download remains supported from saved state.

### 7.3 Confirmation Binding

Bind paid confirmation to provider, backend, region, model snapshot hash, model
ID, mode, duration, resolution, references and their hashes, parameters,
quantity, estimate, and request fingerprint. A refreshed snapshot or changed
parameter requires a new confirmation.

## 8. Task State and Recovery

Keep workflow `JobState` separate from provider `VideoGenerationAttempt`. The
attempt status set includes at least:

- `prepared`;
- `awaiting_confirmation`;
- `submitting`;
- `submitted`;
- `running`;
- `completed`;
- `downloaded`;
- `submission_unknown`;
- `failed`;
- `cancelled`.

The submit sequence is fixed:

```text
validate request, model snapshot, media, estimate, and confirmation
-> persist sanitized submitting attempt atomically
-> consume and persist the one-shot confirmation
-> issue exactly one paid submit call
-> persist task ID and submitted status
```

If transport returns no definitive provider result, persist
`submission_unknown`. Query and download commands only read existing attempts
and never call submit. Download uses a temporary file, verifies non-empty media,
computes SHA-256, then atomically replaces the destination. Signed download URLs
remain in memory only.

## 9. CLI Surface

Keep the existing top-level `dry-run` command unchanged as an M0 compatibility
entry. Add the complete workflow under:

```text
video sprite plan
video sprite route
video provider models
video provider preflight
video provider estimate
video provider submit
video provider query
video provider download
video sprite ingest
video sprite process
video sprite record-review
video sprite validate
```

The Skill launcher remains
`skills/forge-video-to-sprite/scripts/run.py`. Commands print versioned,
machine-readable JSON on success and sanitized structured errors on failure.

## 10. Local Video Processing

### 10.1 Tool Discovery and Probe

Discover `ffmpeg` and `ffprobe` in this order:

1. explicit command arguments;
2. dedicated environment variables;
3. `PATH`;
4. documented Windows package locations.

Do not install them. Run FFprobe with JSON output and no shell. Reject missing
video streams, invalid duration, invalid dimensions, undecodable input, and
out-of-range trim intervals before writing frame outputs.

### 10.2 Sampling

Sample by presentation timestamp so variable-frame-rate media remains stable.
Normalize display rotation. When multiple frame counts are requested, extract
the highest density once and derive every lower density deterministically from
that ordered timeline.

- Looping animation samples `[start, end)` so the endpoint does not duplicate
  the first pose.
- Non-looping animation includes both endpoints when more than one frame is
  requested.
- Record source timestamp and source-frame index when FFmpeg can report it.

Do not modify or re-encode the source video. Record audio presence but do not
include audio in Sprite artifacts.

### 10.3 Cleanup and Alignment

Reuse the shared Sprite image-processing components:

- `preserve` retains the source background;
- `chroma` requires an explicit known background color;
- `rembg` prefers CUDA, falls back to CPU, and may fall back to chroma only when
  a valid chroma color is declared.

If rembg fails without a valid chroma fallback, mark the run as needing
attention; do not label opaque frames as transparent output.

Trim transparent bounds per frame, compute stable bottom-center/feet anchors,
and normalize the full sequence onto one canvas using one scale policy. Use
nearest-neighbor resizing for `pixel` and high-quality resampling for `hd`.

### 10.4 Outputs

The staging bundle contains:

```text
source/video-source-record.json
raw-frames/
clean-frames/
delivery/frames/
delivery/strips/
delivery/sheets/
delivery/previews/preview.gif
delivery/previews/contact-sheet.png
delivery/previews/motion-difference.png
frame-timing.json
processing-result.json
video-quality-report.json
```

Publish only requested runtime formats plus required provenance and quality
evidence. Preserve raw frames in staging/run evidence, not necessarily in the
minimal runtime bundle.

## 11. Quality Gates

### 11.1 Deterministic Blocking Checks

Block publication for:

- request, source, provider-attempt, model-snapshot, or artifact hash mismatch;
- missing, corrupt, unordered, out-of-range, or wrong-count frames;
- incorrect frame, strip, or sheet dimensions/order;
- empty visible content or content outside the declared canvas;
- requested transparency with entirely opaque outputs;
- manifest paths, roles, or hashes that do not match staged files.

### 11.2 Temporal Attention Metrics

Report exact and near-duplicate rates, motion coverage, static intervals,
subject bounds/area variation, source and normalized anchor jitter, first/last
loop difference, alpha coverage, chroma residue, clipping risk, background
change, and frame flicker.

These metrics can produce `needs_attention`; they do not independently prove
semantic correctness because holds, impacts, and anticipation frames can be
intentional.

### 11.3 Visual Review Checks

Final review checks character identity, clothing/colors/equipment, action and
direction, timing, start/end pose, anatomy, camera lock, unwanted scale/drift,
background cleanup, edge quality, loop continuity, text/watermarks, and
semantic duplicates.

The review record binds the request, source video, quality report, contact
sheet, preview GIF, diagnostics, strips, and sheets by hash. Only an approved,
current record allows final publication.

## 12. Security and Path Safety

- Pass subprocess arguments as arrays with `shell=False`.
- Normalize repository-relative contract paths and reject absolute paths,
  traversal, duplicate outputs, and writes outside declared run/staging/final
  roots.
- Redact provider errors before serialization.
- Reject secret-shaped provider payload fields and responses.
- Never log command lines that contain credentials.
- Store only stable provider IDs and local artifact hashes, never transient
  download URLs or raw provider response bodies.

## 13. Dependencies and Installation

- Python 3.11+ remains required.
- Pillow is required for frame post-processing and image exports.
- rembg/ONNX Runtime and PyMatting remain optional extras with the existing
  documented installation choices.
- FFmpeg/FFprobe are external tools and must be installed by the user.
- MiniMax `mmx` and Jimeng `dreamina` are optional compatibility tools and are
  never installed automatically.
- API adapters use the Python standard library HTTP/signing boundary so the
  base repository does not require a provider SDK merely to run preflight or
  local-video P0.

Update the English and Simplified Chinese repository documentation with concise
installation and capability notes. Keep the detailed operational sequence in
`skills/forge-video-to-sprite/SKILL.md` and focused references rather than
expanding the root README into a full tutorial.

## 14. Testing

All automated tests are zero-cost and must not call a live provider.

Add tests for:

1. every new contract, serialization rule, enum, path boundary, and hash;
2. FFprobe parsing, rotation, variable FPS, invalid media, and trim ranges;
3. looping/non-looping timestamp selection and 8/16/24/48 derivation;
4. cleanup, rembg/chroma fallback, pixel/HD resize, anchor, and canvas behavior;
5. strips, sheets, GIFs, contact sheets, timing records, and manifests;
6. deterministic quality checks and temporal attention metrics;
7. MiniMax API/CLI preflight, current-model snapshot, `MiniMax-H3`, unknown new
   models, backend separation, and CLI validation compatibility;
8. Jimeng API signing/products and CLI capability/backend separation;
9. estimate binding, confirmation consumption, one-shot submit,
   `submission_unknown`, query-only recovery, and atomic download;
10. secret redaction and forbidden provider payloads;
11. fake provider and fake FFmpeg end-to-end workflows;
12. optional real-FFmpeg synthetic-video integration when FFmpeg is available;
13. a clean existing-video workflow through final manifest publication;
14. Skill contract tests and `quick_validate.py`.

The full repository unit-test suite must pass after integration.

## 15. Success Criteria

The feature is complete when:

- a new user can install the documented local dependencies and convert an
  existing supported video into validated game-ready Sprite outputs;
- a configured user can explicitly choose MiniMax or Jimeng and API or CLI,
  confirm one paid attempt, resume it without resubmission, download the video,
  and enter the same local pipeline;
- current MiniMax models, including `MiniMax-H3`, appear through refreshed model
  evidence and unknown future models are visible without unsafe API submission;
- local reprocessing never creates a provider task;
- every final artifact is traceable to request, source video, timing, processing,
  review, and SHA-256 evidence;
- no credential or transient provider URL is written to repository artifacts;
- the repository continues to expose exactly `forge-2d-map`,
  `forge-2d-sprite`, and `forge-video-to-sprite`.

## 16. Commit Hygiene

Implementation commits must stage explicit paths. Do not include the pending
bridge-connectivity showcase evidence or its sample-specific test changes in
the design, plan, implementation, or documentation commits for this feature.
