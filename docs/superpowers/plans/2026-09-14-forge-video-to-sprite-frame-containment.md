# Forge Video Sprite Frame Containment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an executable safe-frame and swept-containment contract to
`forge-video-to-sprite`, expose the evidence in quality reports, and align the
local H3 character prompt guidance with the new game-asset boundary.

**Architecture:** Keep request validation in `contracts.video`, geometric
evidence in `processing.video_review`, source-edge evidence in
`processing.video_sprite`, and deterministic publication gating in
`quality.video`. Extend `VideoQualityReport` additively, preserve old report
deserialization, and keep H3 wording in the repository-owned Skill references
while preserving the external H3 Prompt Writing Skill's exact field order.

**Tech Stack:** Python 3.11 dataclasses and `StrEnum`, Pillow, existing JSON
serialization, `unittest`, repository Skill contract tests, and the existing
skill validator.

**Spec:** `docs/superpowers/specs/2026-09-14-forge-video-to-sprite-frame-containment-design.md`

## Global Constraints

- Preserve unrelated user changes, especially `tests/test_tilemap_manifest_integrity.py`.
- Do not modify ComfyUI, installed models, custom nodes, global workflows, or project-local absolute-path settings.
- Keep all public Skill Markdown, YAML, and Python files English-only.
- Preserve H3 alignment-line and core-field order: `integrated_multimodal_description`, `overall_soundscape`, `non_diegetic_music`.
- Keep `preserve` background runs explicitly unevaluable; strict publication must hard-fail them, while report-only may require manual review.
- Strict containment failures must block publication even after an approved manual review.
- Do not add an uncalibrated sharpness gate or silently rescale/crop unsafe source content.
- No commit, push, asset deletion, ComfyUI generation, model download, or workflow installation is part of this change.

---

### Task 1: Add RED tests for the containment contract

**Files:**
- Modify: `tests/test_video_contract.py`
- Modify: `tests/test_video_review.py`
- Modify: `tests/test_video_quality.py`
- Modify: `tests/test_skill_contracts.py`
- Read: `docs/superpowers/specs/2026-09-14-forge-video-to-sprite-frame-containment-design.md`

**Interfaces:**
- Consumes: current request, temporal-metric, quality-report, and Skill APIs.
- Produces: failing tests for policy validation, safe bounds, source-edge
  evidence, deterministic hard failure, report fields, and required docs.

- [x] **Step 1: Test request defaults, validation, and round-trip fields**

Add assertions that a request defaults to `strict` and `0.05`, serializes
`canvas_policy` and `safe_frame_margin`, accepts `report-only`, rejects a zero
margin under strict policy, and rejects negative or `>= 0.5` margins and
unknown policies.

- [x] **Step 2: Test geometric metrics and diagnostic inputs**

Add transparent synthetic frames whose weapon-shaped rectangle reaches the
right edge and assert `edge_contact_frames`, `out_of_safe_frame_frames`,
`swept_bounds`, `safe_frame_bounds`, `minimum_margin`, and a failed
containment result. Add a clean sequence assertion and pass safe/swept bounds
to `create_anchor_diagnostic`.

- [x] **Step 3: Test the quality hard gate and backward-compatible report**

Mutate a delivered transparent frame into the safe margin and assert the
`canvas-containment` deterministic check fails, `canvas_containment` is
serialized, and publication is blocked. Add a preserved-background assertion
that strict containment fails, while an explicit `report-only` request is
`needs_attention`/unevaluable. Deserialize a legacy report with no new field.

- [x] **Step 4: Test the Skill contract text**

Require `canvas_policy`, `safe_frame_margin`, `swept_bounds`,
`source_edge_contact_frames`, `no-canvas-clipping`, and
`equipment-in-safe-frame` in the public Forge Skill/reference text and require
the H3 safe-frame wording to stay within the H3 multimodal field guidance.

- [x] **Step 5: Run the focused RED suite and record the baseline**

Run:

```powershell
python -m unittest tests.test_video_contract tests.test_video_review tests.test_video_quality tests.test_skill_contracts
```

The new assertions failed before implementation (`VideoCanvasPolicy` was
missing, the metrics and diagnostic accepted no containment arguments, the
quality report had no containment gate/field, and the Skill text had none of
the new contract terms). The tests were kept strict and were not weakened.

### Task 2: Extend the request and quality-report contracts

**Files:**
- Modify: `src/game_visual_forge/contracts/video.py`
- Modify: `src/game_visual_forge/contracts/video_quality.py`
- Modify: `src/game_visual_forge/contracts/__init__.py`
- Modify: `tests/test_video_contract.py`
- Read: `docs/superpowers/specs/2026-09-14-forge-video-to-sprite-frame-containment-design.md`

**Interfaces:**
- `VideoCanvasPolicy`: `strict` or `report-only`.
- `VideoSpriteRequest.canvas_policy`: defaults to strict.
- `VideoSpriteRequest.safe_frame_margin`: normalized float, defaults to 0.05.
- `VideoQualityReport.canvas_containment`: additive JSON object, default `{}`.

- [x] **Step 1: Implement enum and request validation**

Add `VideoCanvasPolicy`, validate its type and require
`0 < safe_frame_margin < 0.5` for strict requests (`[0, 0.5)` for
report-only), and preserve schema version 1. Include both fields in
`to_dict`/`from_dict`.

- [x] **Step 2: Export the new enum**

Expose `VideoCanvasPolicy` through `game_visual_forge.contracts` and its
`__all__` list without changing existing exports.

- [x] **Step 3: Add the additive quality-report field**

Append `canvas_containment` with a default factory, emit it in `to_dict`, and
accept missing data in `from_dict` so older reports remain readable.

- [x] **Step 4: Run contract tests**

Run:

```powershell
python -m unittest tests.test_video_contract
```

### Task 3: Compute containment evidence and preserve source-edge proof

**Files:**
- Modify: `src/game_visual_forge/processing/video_review.py`
- Modify: `src/game_visual_forge/processing/video_sprite.py`
- Modify: `src/game_visual_forge/cli/video.py`
- Modify: `tests/test_video_review.py`
- Modify: `tests/test_video_processing.py`

**Interfaces:**
- `calculate_safe_frame_bounds(width, height, margin)` returns half-open
  integer bounds.
- `calculate_temporal_metrics` accepts safe margin, source-edge frame indexes,
  and foreground-evaluable state while retaining old defaults.
- `TemporalMetrics` exposes safe bounds, swept bounds, edge-contact indexes,
  out-of-safe-frame indexes, source-edge indexes, minimum margin, and
  containment status/evaluability.
- Anchor diagnostics draw the safe rectangle and swept bounds when supplied.

- [x] **Step 1: Add visible-alpha and safe-frame helpers**

Use alpha >= 8 for foreground bounds and calculate union, edge contacts,
out-of-safe-frame indexes, and normalized minimum margin. Keep old temporal
metrics and `clipping_risk` behavior available.

- [x] **Step 2: Extend temporal metrics compatibly**

Add optional keyword arguments and defaulted dataclass fields. Add a
`safe-frame-violation` attention reason only when containment is required; add
`canvas-containment-unavailable` for opaque preserved backgrounds.

- [x] **Step 3: Record pre-trim source bounds**

In `process_video_sprite`, inspect cleaned alpha bounds before `trim_alpha`,
record `pretrim_source_bounds` and `source_edge_contact_frames` in timing, and
retain existing `source_bounds`/reference fields. Do not recrop or silently
repair an edge contact.

- [x] **Step 4: Draw diagnostics and pass timing evidence**

Extend `create_anchor_diagnostic` and `run_video_record_review` to draw the
safe rectangle and swept bounds from the request/report timing data.

- [x] **Step 5: Run processing/review tests**

Run:

```powershell
python -m unittest tests.test_video_processing tests.test_video_review
```

### Task 4: Enforce the deterministic quality gate and report all densities

**Files:**
- Modify: `src/game_visual_forge/quality/video.py`
- Modify: `src/game_visual_forge/processing/video_sprite.py`
- Modify: `tests/test_video_quality.py`

**Interfaces:**
- `assess_video_outputs` adds a `canvas-containment` QualityCheck.
- Strict/evaluable violations are `FAILED`; report-only violations are
  `NEEDS_ATTENTION`; preserved backgrounds are explicitly unevaluable.
- `VideoQualityReport.canvas_containment` contains policy, margin, safe bounds,
  per-frame and swept bounds, minimum margin, per-density evidence,
  source-edge frames, and status.
- Asset manifests include the policy and margin for downstream provenance.

- [x] **Step 1: Load timing evidence and evaluate each density**

Compute canonical temporal metrics from the highest density and containment
metrics from every requested density. Aggregate failed density names and keep
source-edge evidence from the pre-trim timing record.

- [x] **Step 2: Add the hard check before deriving deterministic status**

Append `canvas-containment` before computing the deterministic status. Never
let an approved review turn a failed deterministic check into a publishable
report.

- [x] **Step 3: Preserve review and manifest behavior**

Carry `canvas_containment` through reviewed reports and add policy/margin to
manifest metadata. Keep publication atomic and existing hash validation intact.

- [x] **Step 4: Run the quality tests**

Run:

```powershell
python -m unittest tests.test_video_quality
```

### Task 5: Update Forge and H3 documentation contracts

**Files:**
- Modify: `skills/forge-video-to-sprite/SKILL.md`
- Modify: `skills/forge-video-to-sprite/references/processing-and-quality.md`
- Modify: `skills/forge-video-to-sprite/references/h3-character-quality-profile.md`
- Modify: `skills/forge-video-to-sprite/references/provider-workflow.md`
- Modify: `tests/test_skill_contracts.py`

**Interfaces:**
- Public Skill instructs strict safe-frame containment for game Sprite output.
- Processing reference defines report fields and the deterministic gate.
- H3 profile adds the safe-frame/swept-weapon language inside
  `integrated_multimodal_description` without changing H3 labels/order.

- [x] **Step 1: Document request and report fields**

Specify `canvas_policy`, `safe_frame_margin`, safe-frame coordinates,
`frame_bounds`, `swept_bounds`, `minimum_margin`, `edge_contact_frames`,
`out_of_safe_frame_frames`, and `source_edge_contact_frames`.

- [x] **Step 2: Add prompt constraints and review checks**

Require the complete character and defining equipment, including the farthest
attack sweep, to remain in-frame with a locked camera; prohibit cropping,
out-of-frame weapon tips, blur, smear, defocus, and ghosting. Require manual
`no-canvas-clipping` and `equipment-in-safe-frame` checks.

- [x] **Step 3: Run Skill validation and tests**

Run:

```powershell
python -m unittest tests.test_skill_contracts
python C:/Users/QJX/.codex/skills/.system/skill-creator/scripts/validate_skill.py skills/forge-video-to-sprite
```

### Task 6: Full verification and delivery audit

**Files:**
- Read: all changed files above
- Preserve: unrelated dirty files

- [x] **Step 1: Run the complete repository test suite**

Run:

```powershell
python -m unittest discover -s tests -t .
```

- [x] **Step 2: Inspect the diff and status**

Run:

```powershell
git diff --check
git status --short
git diff --stat
```

Confirm only the planned files changed plus the pre-existing unrelated test
modification; do not stage or revert anything.

- [x] **Step 3: Report the outcome**

Summarize the new fields, the strict/report-only behavior, RED/GREEN test
evidence, documentation changes, and any remaining manual visual-review
requirements. Mention that no ComfyUI workflow, model, asset, or C-drive
download was touched.
