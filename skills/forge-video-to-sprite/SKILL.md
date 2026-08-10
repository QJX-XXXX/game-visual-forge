---
name: forge-video-to-sprite
description: "Convert an existing or explicitly generated video into validated 2D Sprite animation with timestamp sampling, cleanup, stable alignment, quality review, and recoverable MiniMax Hailuo or Jimeng API/CLI workflows."
---

# Forge Video to Sprite

Use this Skill for a local MP4, MOV, WebM, or an explicitly selected generated
motion clip that must become game-ready Sprite frames. Keep the repository root
and shared `src/` package available; the launcher is
`skills/forge-video-to-sprite/scripts/run.py`.

## Standard interaction

1. Extract the character, action, view, camera, loop, start/end pose,
   background, frame densities, outputs, anchor, canvas, processing mode, and
   engine notes from the request and conversation.
2. Ask one consolidated creative/delivery confirmation for missing or
   contradictory fields. Do not preflight a provider or create a paid task
   before this confirmation.
3. Route explicitly to `existing-file`, `minimax`, or `jimeng`. For generated
   video ask for `api` or `cli` in the same route choice. Detection reports
   availability; it never chooses or switches a backend.
4. For generated video, refresh the provider model snapshot, show provider,
   backend, region, model, mode, references and hashes, duration, resolution,
   billing context, estimate status, and request fingerprint. Ask for one
   paid-submit confirmation. An unverified estimate is labelled unverified and
   must be acknowledged explicitly. The current MiniMax-H3 V2 profile and its
   exact duration, resolution, ratio, and reference limits are visible; a
   discovered-unprofiled model is shown but cannot be submitted through API.
5. Submit exactly once after the confirmation is persisted. Query or download
   an existing task when recovering; never resubmit `submission_unknown`.
6. Ingest the immutable video, sample by presentation timestamp, clean and
   align frames, export the requested densities, and run deterministic checks.
7. Present source interval, timestamped contact sheet, transparent GIF,
   motion-difference image, anchor diagnostic, strips, and sheets for the final
   motion review. Only a current approved review allows publication.

Existing-video work never invokes a provider. Local processing changes reuse the
same source video and do not create a new paid task.

- Provider subprocesses use binary UTF-8 JSON, and chroma delivery must pass the all-density residue gate before publication.

## Commands

```powershell
python skills/forge-video-to-sprite/scripts/run.py video sprite plan --request inputs/video-request.json --out-dir runs/video --now 2026-08-09T00:00:00Z
python skills/forge-video-to-sprite/scripts/run.py video sprite route --request inputs/video-request.json --out runs/video/source-decision.json --state runs/video/job-state.json --now 2026-08-09T00:00:00Z
python skills/forge-video-to-sprite/scripts/run.py video sprite ingest --request inputs/video-request.json --video inputs/source.mp4 --repo-root . --out runs/video/video-source-record.json --state runs/video/job-state.json --now 2026-08-09T00:00:00Z
python skills/forge-video-to-sprite/scripts/run.py video sprite process --request inputs/video-request.json --source runs/video/video-source-record.json --repo-root . --out-dir runs/video --state runs/video/job-state.json --now 2026-08-09T00:00:00Z
python skills/forge-video-to-sprite/scripts/run.py video sprite record-review --request inputs/video-request.json --source runs/video/video-source-record.json --processing-result runs/video/processing-result.json --repo-root . --quality-report runs/video/video-quality-report.json --out runs/video/video-motion-review.json --checks runs/video/review-checks.json --now 2026-08-09T00:00:00Z
python skills/forge-video-to-sprite/scripts/run.py video sprite validate --request inputs/video-request.json --source runs/video/video-source-record.json --processing-result runs/video/processing-result.json --review runs/video/video-motion-review.json --quality-report runs/video/video-quality-report.json --repo-root . --final-dir outputs/video --now 2026-08-09T00:00:00Z
```

Provider adapter commands are documented in
[`references/provider-workflow.md`](references/provider-workflow.md). Local
sampling, cleanup, output, and quality details are in
[`references/processing-and-quality.md`](references/processing-and-quality.md).

The provider command surface is `video provider models`, `preflight`,
`estimate`, `submit`, `query`, and `download`. Local source work uses FFmpeg
and FFprobe without modifying the source video.

## Safety rules

- Never install FFmpeg, `mmx`, `dreamina`, Python extras, models, or credentials.
- Never write credentials, authorization headers, Base64 media, signed URLs, or
  raw provider responses to repository artifacts.
- Bind a local first-frame PNG by repository-relative path and SHA-256; create
  any provider Data URI only in memory immediately before the confirmed submit.
- Never retry a paid request automatically, and never switch API/CLI after a
  task has been created.
- Treat automatic metrics as review evidence, not proof of identity, anatomy,
  action semantics, or loop quality.
