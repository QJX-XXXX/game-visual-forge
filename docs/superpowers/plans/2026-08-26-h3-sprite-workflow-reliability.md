# H3 Sprite Workflow Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make local MiniMax H3 FL2VA output deterministic and position-stable for game Sprite extraction without upgrading ComfyUI or downloading models.

**Architecture:** Add a pure JSON workflow inspector and sanitized provenance record for the local H3 route. Add an opt-in `reference-locked` video layout that keeps the first-frame scale and feet anchor for every extracted frame, while preserving the current alpha-tight behavior by default. Document both contracts in the public video Skill and validate them with focused unit tests.

**Tech Stack:** Python 3.12 standard library, Pillow, NumPy, existing `unittest` suite, JSON workflow files, Markdown Skill package.

**Spec:** `docs/superpowers/specs/2026-08-26-h3-sprite-workflow-design.md`

## Global Constraints

- Do not update ComfyUI, install custom nodes, download models, or submit a generation.
- Do not change hosted-provider behavior or the existing default alpha-tight layout.
- Never serialize credentials, signed URLs, Base64 media, or raw Comfy responses.
- Preserve the existing uncommitted `tests/test_tilemap_manifest_integrity.py` change.
- Public Skill files remain English-only.
- Modify only the selected local workflow's keyframe/seed/length/settings; do not touch unrelated Comfy workflows.

### Task 1: Add workflow inspection and provenance contracts

**Files:**
- Create: `src/game_visual_forge/contracts/comfy_h3.py`
- Create: `src/game_visual_forge/processing/comfy_h3_workflow.py`
- Modify: `src/game_visual_forge/contracts/__init__.py`
- Test: `tests/test_comfy_h3.py`

**Interfaces:**
- `ComfyH3WorkflowReport` is a frozen dataclass containing `schema_version`, `workflow_sha256`, `h3_node_count`, `first_frame_connected`, `last_frame_connected`, `same_keyframe_source`, `seed_mode`, `length`, `local_only`, and `errors`.
- `ComfyH3GenerationRecord` is a frozen dataclass containing request/workflow/prompt hashes, reference paths and hashes, model, seed, steps, prompt ID, terminal status, output path, and output SHA-256. Optional job fields remain `None` until known.
- `inspect_comfy_h3_workflow(workflow: Mapping[str, Any]) -> ComfyH3WorkflowReport` performs no I/O and does not mutate the input.
- `load_and_inspect_comfy_h3_workflow(path: Path) -> ComfyH3WorkflowReport` reads one JSON file and hashes its bytes.

- [ ] **Step 1: Write failing tests** for an accepted local fixed-seed FL2VA fixture, disconnected `last_frame`, randomized seed, invalid length, API/Cloud node, malformed digest, and secret-free record serialization.
- [ ] **Step 2: Run the focused tests** and confirm they fail because the contracts and inspector do not exist.
- [ ] **Step 3: Implement the immutable contracts and semantic graph traversal.** Resolve the H3 node by `class_type`/`type`, trace image links back to `LoadImage` nodes, require the same source filename for first and last frames, read the `control_after_generate` value without assuming a widget index, and reject any node type containing `API`, `Cloud`, or `Partner`.
- [ ] **Step 4: Run `python -m unittest tests.test_comfy_h3 -v`** and confirm all checks pass.
- [ ] **Step 5: Commit** with `git add src/game_visual_forge/contracts/comfy_h3.py src/game_visual_forge/processing/comfy_h3_workflow.py src/game_visual_forge/contracts/__init__.py tests/test_comfy_h3.py` and `git commit -m "feat: inspect local H3 sprite workflows"`.

### Task 2: Add reference-locked video delivery

**Files:**
- Modify: `src/game_visual_forge/contracts/video.py`
- Modify: `src/game_visual_forge/contracts/__init__.py`
- Modify: `src/game_visual_forge/processing/video_sprite.py`
- Modify: `src/game_visual_forge/quality/video.py`
- Modify: `src/game_visual_forge/processing/video_review.py`
- Test: `tests/test_video_contract.py`
- Test: `tests/test_video_processing.py`
- Test: `tests/test_video_quality.py`

**Interfaces:**
- `VideoLayoutMode(StrEnum)` has `TIGHT = "tight"` and `REFERENCE_LOCKED = "reference-locked"`.
- `VideoSpriteRequest.layout_mode: VideoLayoutMode = VideoLayoutMode.TIGHT` is serialized and defaults for old request JSON.
- `_delivery_frames` accepts the layout mode and returns the existing scale/bounds tuple; in reference-locked mode it uses the first cleaned frame's alpha bounds as the immutable reference.
- `VideoProcessingResult` diagnostics include the layout mode and reference bounds in `frame-timing.json` without changing its schema version.

- [ ] **Step 1: Add failing tests** proving old requests default to `tight`, reference-locked frames keep identical feet/scale when a later frame has a larger weapon, mixed source dimensions fail, and clipping remains reported rather than triggering auto-rescaling.
- [ ] **Step 2: Run `python -m unittest tests.test_video_contract tests.test_video_processing tests.test_video_quality -v`** and confirm the new tests fail.
- [ ] **Step 3: Implement `VideoLayoutMode` parsing and serialization** with the existing schema version and backward-compatible default.
- [ ] **Step 4: Implement reference-locked compositing.** Preserve cleaned full-frame coordinates, compute scale from the first frame's visible bounds, resize each whole source frame once, and place it using the first bounds center/bottom and the current feet safety margin. Keep alpha-tight code unchanged for `tight`.
- [ ] **Step 5: Write layout metadata and draw the immutable reference anchor** in the diagnostic; do not introduce semantic arrow removal.
- [ ] **Step 6: Run the focused tests** and confirm all pass, then run `python -m unittest tests.test_video_processing tests.test_video_quality -v` for regression coverage.
- [ ] **Step 7: Commit** with `git add src/game_visual_forge/contracts/video.py src/game_visual_forge/contracts/__init__.py src/game_visual_forge/processing/video_sprite.py src/game_visual_forge/quality/video.py src/game_visual_forge/processing/video_review.py tests/test_video_contract.py tests/test_video_processing.py tests/test_video_quality.py` and `git commit -m "feat: lock video sprite layout to reference frame"`.

### Task 3: Expose H3 inspection through the launcher

**Files:**
- Modify: `src/game_visual_forge/cli/video.py`
- Modify: `src/game_visual_forge/cli/main.py`
- Test: `tests/test_comfy_h3.py`
- Test: `tests/test_video_cli.py`

**Interfaces:**
- CLI command: `video sprite inspect-h3 --workflow <path> --out <path>`.
- `run_video_inspect_h3(workflow_path: Path, out_path: Path) -> dict[str, Any]` writes only the sanitized `ComfyH3WorkflowReport`.

- [ ] **Step 1: Add a failing CLI help/integration test** for `inspect-h3` and its JSON output.
- [ ] **Step 2: Run the focused CLI test** and confirm the parser rejects the command.
- [ ] **Step 3: Add the parser route and implementation** using the pure inspector; never rewrite the input workflow.
- [ ] **Step 4: Run `python -m unittest tests.test_comfy_h3 tests.test_video_cli -v`** and confirm it passes.
- [ ] **Step 5: Commit** with `git add src/game_visual_forge/cli/video.py src/game_visual_forge/cli/main.py tests/test_comfy_h3.py tests/test_video_cli.py` and `git commit -m "feat: expose H3 workflow inspection"`.

### Task 4: Update the public Skill and contracts

**Files:**
- Modify: `skills/forge-video-to-sprite/SKILL.md`
- Modify: `skills/forge-video-to-sprite/references/processing-and-quality.md`
- Modify: `skills/forge-video-to-sprite/references/provider-workflow.md`
- Modify: `tests/test_skill_contracts.py`

- [ ] **Step 1: Add failing contract fragments** for FL2VA first/last keyframes, fixed seed, H3 `17k + 5` length, static idle, reference-locked layout, runtime projectile ownership, and `inspect-h3`.
- [ ] **Step 2: Run `python -m unittest tests.test_skill_contracts -v`** and confirm the new fragments fail.
- [ ] **Step 3: Add concise English guidance** that preserves the existing confirmation, local-only, recovery, and visual-review rules; explicitly state that a reference-locked layout is opt-in and that the current default remains alpha-tight.
- [ ] **Step 4: Run `python -m unittest tests.test_skill_contracts -v`** and the Skill launcher help tests.
- [ ] **Step 5: Commit** with `git add skills/forge-video-to-sprite/SKILL.md skills/forge-video-to-sprite/references/processing-and-quality.md skills/forge-video-to-sprite/references/provider-workflow.md tests/test_skill_contracts.py` and `git commit -m "docs: document H3 reference-locked sprite profile"`.

### Task 5: Apply and verify the selected local Comfy workflow

**Files:**
- Modify: `I:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\2D素材生成工作流_minimax_h3_i2v_sageattention.json`
- Artifact: a sanitized inspection JSON outside the repository, next to the workflow.

- [ ] **Step 1: Save a timestamped copy** of the selected workflow in the same local workflow folder before editing; do not alter any other workflow.
- [ ] **Step 2: Add the same ready-pose `LoadImage` output to `last_frame`**, set the existing seed control to fixed, update the duration expression to a valid 124-frame H3 length, and rewrite the prompt timeline to return and hold the same pose before the end.
- [ ] **Step 3: Run the repository `inspect-h3` command** against the edited JSON and verify both keyframes, fixed seed, length, and local-only checks.
- [ ] **Step 4: If the Comfy server is running, call local Comfy MCP validation once; if it is stopped, report JSON-only validation and do not start a generation.**
- [ ] **Step 5: Re-read the JSON and compare its SHA-256 to the inspection record.**

### Task 6: Full verification and delivery

- [ ] Run `python -m unittest tests.test_comfy_h3 tests.test_video_contract tests.test_video_processing tests.test_video_quality tests.test_video_cli tests.test_skill_contracts -v`.
- [ ] Run `python -m unittest discover -s tests -q` and record the exit code.
- [ ] Run each public launcher with `--help` and run `skills/forge-video-to-sprite/scripts/quick_validate.py` if present.
- [ ] Confirm `git status --short` contains no staged or modified user file except the pre-existing `tests/test_tilemap_manifest_integrity.py` change.
- [ ] Push only the new Forge commits to `origin/main` after verifying the remote and successful tests.
- [ ] Confirm `C:\Users\QJX\.codex\skills\forge-video-to-sprite` remains a Junction to the pushed Forge Skill and report that Codex discovers the updated Skill from that path. Do not replace the standalone `h3-prompt-writing` Skill.
