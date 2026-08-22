---
name: forge-video-to-sprite
description: "Use when existing, MiniMax Hailuo, Jimeng, optional local ComfyUI MiniMax H3 video must become a validated 2D Sprite animation."
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
3. Route explicitly to `existing-file`, `comfyui-h3`, `minimax`, or `jimeng`.
   `comfyui-h3` uses the conditional `comfy-mcp` backend. Hosted generation
   asks for `api` or `cli` in the same route choice. Detection reports
   availability; it never chooses or switches a route or backend.
4. For `comfyui-h3`, require the H3 Prompt Writing Skill and Comfy MCP, use the
   prompt Skill for the selected H3 mode, then preflight and validate the local
   workflow. Bind the prompt, references, workflow, model, duration, resolution,
   and their hashes before execution. Inspect the graph for Cloud or partner
   nodes; obtain explicit spend confirmation when it can consume credits or the
   billing boundary is unverified. A fully local graph needs no paid confirmation.
5. Run a confirmed ComfyUI graph once, persist its `prompt_id`, and recover it
   through the Comfy MCP job/status and output-fetch tools. Never rerun an
   uncertain graph automatically. Fetch one immutable video before local ingest.
6. For MiniMax Hailuo or Jimeng, refresh the provider model snapshot, show provider,
   backend, region, model, mode, references and hashes, duration, resolution,
   billing context, estimate status, and request fingerprint. Ask for one
   paid-submit confirmation. An unverified estimate is labelled unverified and
   must be acknowledged explicitly. The current MiniMax-H3 V2 profile and its
   exact duration, resolution, ratio, and reference limits are visible; a
   discovered-unprofiled model is shown but cannot be submitted through API.
7. Submit exactly once after the confirmation is persisted. Query or download
   an existing task when recovering; never resubmit `submission_unknown`.
8. Ingest the immutable video, sample by presentation timestamp, clean and
   align frames, export the requested densities, and run deterministic checks.
9. Present source interval, timestamped contact sheet, transparent GIF,
   motion-difference image, anchor diagnostic, strips, and sheets for the final
   motion review. Only a current approved review allows publication.

Existing-video work never invokes a provider. Local processing changes reuse the
same source video and do not create a new paid task.

- Provider subprocesses use binary UTF-8 JSON, and chroma delivery must pass the all-density residue gate before publication.

## Conditional prerequisites

The `comfyui-h3` route requires both dependencies below. If a prerequisite is absent during ordinary asset work, report it and stop the selected route. Do not install it. Only when the user explicitly asks to install or enable a workflow, hand off to the repository Agent installation guide. That guide must ask whether to enable ComfyUI MiniMax H3, inspect first, display the missing-component plan, and obtain installation confirmation before installing Comfy MCP or `h3-prompt-writing`.

- [Comfy MCP official installation](https://docs.comfy.org/agent-tools/mcp#installation)
- [MiniMax H3 Prompt Writing Skill official installation](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/README.md#installation)
- [Unified repository installation guide](../../install/README.md)

Other routes remain available when these conditional dependencies are absent.

## Commands

```powershell
python skills/forge-video-to-sprite/scripts/run.py video sprite plan --request inputs/video-request.json --out-dir runs/video --now 2026-08-09T00:00:00Z
python skills/forge-video-to-sprite/scripts/run.py video sprite route --request inputs/video-request.json --out runs/video/source-decision.json --state runs/video/job-state.json --now 2026-08-09T00:00:00Z
python skills/forge-video-to-sprite/scripts/run.py video sprite route --request inputs/comfyui-h3-request.json --selection comfyui-h3 --backend comfy-mcp --available runs/video/comfyui-availability.json --out runs/video/source-decision.json --state runs/video/job-state.json --now 2026-08-09T00:00:00Z
python skills/forge-video-to-sprite/scripts/run.py video sprite ingest --request inputs/video-request.json --video inputs/source.mp4 --repo-root . --out runs/video/video-source-record.json --state runs/video/job-state.json --now 2026-08-09T00:00:00Z
python skills/forge-video-to-sprite/scripts/run.py video sprite process --request inputs/video-request.json --source runs/video/video-source-record.json --repo-root . --out-dir runs/video --state runs/video/job-state.json --now 2026-08-09T00:00:00Z
python skills/forge-video-to-sprite/scripts/run.py video sprite record-review --request inputs/video-request.json --source runs/video/video-source-record.json --processing-result runs/video/processing-result.json --repo-root . --quality-report runs/video/video-quality-report.json --out runs/video/video-motion-review.json --checks runs/video/review-checks.json --now 2026-08-09T00:00:00Z
python skills/forge-video-to-sprite/scripts/run.py video sprite validate --request inputs/video-request.json --source runs/video/video-source-record.json --processing-result runs/video/processing-result.json --review runs/video/video-motion-review.json --quality-report runs/video/video-quality-report.json --repo-root . --final-dir outputs/video --now 2026-08-09T00:00:00Z
```

Provider adapter commands are documented in
[`references/provider-workflow.md`](references/provider-workflow.md). Local
sampling, cleanup, output, and quality details are in
[`references/processing-and-quality.md`](references/processing-and-quality.md).

The hosted-provider command surface is `video provider models`, `preflight`,
`estimate`, `submit`, `query`, and `download`. Local source work uses FFmpeg
and FFprobe without modifying the source video. ComfyUI execution is performed
through Comfy MCP rather than the hosted-provider command surface.

## Safety rules

- Never install FFmpeg, `mmx`, `dreamina`, Comfy MCP, the H3 Prompt Writing
  Skill, Python extras, models, or credentials.
- Never write credentials, authorization headers, Base64 media, signed URLs, or
  raw provider responses to repository artifacts.
- Bind a local first-frame PNG by repository-relative path and SHA-256; create
  any provider Data URI only in memory immediately before the confirmed submit.
- Never retry a paid request automatically, and never switch API/CLI after a
  task has been created.
- Never rerun a ComfyUI graph automatically after an unknown submission result;
  recover the persisted `prompt_id` or inspect the existing queue/history first.
- Treat automatic metrics as review evidence, not proof of identity, anatomy,
  action semantics, or loop quality.
