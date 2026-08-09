# Forge Video to Sprite P0 + P1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a zero-network existing-video-to-Sprite pipeline plus explicitly selected, recoverable MiniMax Hailuo and Jimeng API/official-CLI generation routes.

**Architecture:** Keep immutable source-video ingest and local FFmpeg/Pillow processing provider-neutral. Put MiniMax and Jimeng behind the existing sanitized JSON subprocess boundary, persist a video-specific model snapshot and generation attempt before paid transport, and feed every downloaded video into the same P0 pipeline. Reuse shared background cleanup, delivery normalization, job state, generic manifest records, and atomic publication only where their contracts remain valid.

**Tech Stack:** Python 3.11+, standard-library dataclasses/HTTP/HMAC/subprocess, FFmpeg/FFprobe, optional Pillow/rembg/PyMatting, `unittest`, official MiniMax `mmx` CLI, official Jimeng `dreamina` CLI.

## Global Constraints

- Work test-first. Every production change follows a focused failing test, the smallest implementation that passes it, then the stated regression command.
- Automated tests must use fake HTTP transports, fake provider executables, or local synthetic media. They must never create a live provider task or incur cost.
- Never install FFmpeg, provider CLIs, Python extras, models, or credentials automatically.
- Never select or switch provider/backend automatically. `api` and `cli` task IDs remain backend-specific.
- Never retry a paid submit automatically. An indeterminate transport outcome becomes `submission_unknown`; query and download never call submit.
- Persist no secrets, authorization headers, Base64 media, signed URLs, or raw provider response bodies. Subprocess calls use argument arrays and `shell=False`.
- Contract paths are normalized repository-relative POSIX paths. Reject absolute paths, traversal, duplicates, and writes outside declared roots.
- Preserve the current generic `dry-run` command and all map/sprite behavior.
- The root README files receive concise capability and installation notes only; the operational workflow belongs in the Skill and its references.
- The public repository continues to expose exactly `forge-2d-map`, `forge-2d-sprite`, and `forge-video-to-sprite`.
- Do not stage the pre-existing adaptive-river-crossing evidence changes or `tests/test_tilemap_manifest_integrity.py`; they are outside this implementation.

## File and Responsibility Map

| Area | Files | Responsibility and produced interface |
| --- | --- | --- |
| Video request/media contracts | `src/game_visual_forge/contracts/video.py`, `contracts/__init__.py` | `VideoSpriteRequest`, source choice, immutable source record, per-frame records, processing result |
| Provider contracts | `src/game_visual_forge/contracts/video_provider.py`, `contracts/provider.py`, `contracts/__init__.py` | backend/model catalog/profile, paid binding, generation attempt, `MODELS` command |
| Review contract | `src/game_visual_forge/contracts/video_review.py`, `contracts/__init__.py` | hash-bound final motion review and validation |
| Routing | `src/game_visual_forge/routing/video.py`, `routing/__init__.py` | deterministic existing/MiniMax/Jimeng decision; no backend fallback |
| Media tools | `src/game_visual_forge/processing/video_probe.py` | tool discovery, ffprobe parse, trim validation, immutable ingest |
| Sampling | `src/game_visual_forge/processing/video_frames.py` | loop-aware timestamps, highest-density extraction, lower-density derivation |
| Local processing | `src/game_visual_forge/processing/video_sprite.py`, `processing/__init__.py` | cleanup, trim, stable anchor/canvas, frames/strips/sheets/GIF/timing |
| Review artifacts | `src/game_visual_forge/processing/video_review.py` | contact sheet, motion-difference and anchor/bounds diagnostics |
| Quality/publish | `src/game_visual_forge/quality/video.py`, `quality/__init__.py` | blocking checks, temporal metrics, review gating, manifest, atomic publish |
| MiniMax adapter | `src/game_visual_forge/providers/minimax_video.py`, `skills/forge-video-to-sprite/scripts/providers/minimax.py` | API/`mmx` capabilities, models, preflight, estimate, prepare, submit/query/download |
| Jimeng adapter | `src/game_visual_forge/providers/jimeng_video.py`, `skills/forge-video-to-sprite/scripts/providers/jimeng.py` | signed API/`dreamina` operations with backend separation |
| Provider orchestration | `src/game_visual_forge/providers/video.py`, `providers/__init__.py` | sanitized subprocess calls, atomic attempt store, one-shot confirmation and recovery |
| Unified CLI | `src/game_visual_forge/cli/video.py`, `cli/main.py` | nested `video sprite` and `video provider` commands |
| Skill/docs | `skills/forge-video-to-sprite/SKILL.md`, references, metadata, READMEs/install guides | three-gate standard workflow and manual dependency/provider setup |
| Tests | `tests/test_video_*.py`, provider tests, fake tools, clean workflow | zero-cost contract, unit, adapter, integration and repository regression coverage |

## Specification Coverage

| Approved design area | Implemented and verified by |
| --- | --- |
| Existing Video P0 | Tasks 1 and 4–8 define immutable media, variable-frame-rate sampling, processing, review, quality, and publication; Tasks 12 and 14 prove the clean workflow. |
| MiniMax Hailuo and Jimeng P1 | Tasks 2, 9, 10, 11, and 12 cover API/CLI adapters, paid binding, recovery, and shared P0 handoff. |
| No Automatic Backend Switching | Tasks 3, 10, 11, and 12 preserve explicit provider/backend selection and backend-specific task identity. |
| Model Synchronization | Tasks 2 and 9 cover live snapshots, MiniMax-H3, profiled models, and visible but blocked unprofiled models. |
| Task State and Recovery | Tasks 2 and 11 cover persisted submitting state, one-shot confirmation, `submission_unknown`, query-only recovery, and atomic download. |
| Final Visual Review | Tasks 7, 8, and 12 bind all presented motion evidence and require current approval before publication. |
| Security and Dependencies | Global constraints plus Tasks 4, 9–11, 13, and 14 cover path safety, redaction, manual installation, optional extras, and zero-cost tests. |

---

### Task 1: Define the video request, source, frame, and processing contracts

**Files:**
- Create: `src/game_visual_forge/contracts/video.py`
- Modify: `src/game_visual_forge/contracts/__init__.py`
- Test: `tests/test_video_contract.py`

**Interfaces:** Consumes JSON request/source metadata. Produces `VideoSpriteRequest`, `VideoSourceDecision`, `VideoSourceRecord`, `VideoFrameRecord`, and `VideoProcessingResult` with round-trip `to_dict`/`from_dict` methods.

- [ ] Write failing tests for normalized request fields, default `frame_counts=(24,)`, unique sorted densities, loop/trim validation, generation-mode reference requirements, repository-relative paths, SHA-256 fields, and serialization round trips.

```python
class VideoContractTests(unittest.TestCase):
    def test_request_normalizes_frame_counts_and_defaults(self) -> None:
        request = VideoSpriteRequest.from_dict(valid_request(frame_counts=[24, 8, 24, 16]))
        self.assertEqual(request.frame_counts, (8, 16, 24))
        self.assertEqual(request.background_mode, VideoBackgroundMode.REMBG)

    def test_loop_interval_is_half_open_and_trim_must_increase(self) -> None:
        with self.assertRaisesRegex(ValueError, "clip_end_seconds"):
            VideoSpriteRequest.from_dict(valid_request(clip_start_seconds=2.0, clip_end_seconds=2.0))

    def test_contract_paths_reject_absolute_and_parent_segments(self) -> None:
        for value in ("C:/secret/video.mp4", "../video.mp4", "/tmp/video.mp4"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                VideoSpriteRequest.from_dict(valid_request(existing_video_path=value))
```

- [ ] Run `python -m unittest tests.test_video_contract -v` and verify failure is an import error for `game_visual_forge.contracts.video`.

- [ ] Implement enums and frozen dataclasses with explicit validation. Use these exact enum values and request limits.

```python
class VideoSourcePreference(StrEnum):
    EXISTING_FILE = "existing-file"
    MINIMAX = "minimax"
    JIMENG = "jimeng"

class VideoGenerationMode(StrEnum):
    T2V = "t2v"
    I2V_FIRST = "i2v-first"
    I2V_FIRST_TAIL = "i2v-first-tail"
    REFERENCE_TO_VIDEO = "reference-to-video"

class VideoBackgroundMode(StrEnum):
    PRESERVE = "preserve"
    CHROMA = "chroma"
    REMBG = "rembg"

class VideoProcessingMode(StrEnum):
    PIXEL = "pixel"
    HD = "hd"

MAX_FRAME_COUNT = 240
```

`VideoSpriteRequest` must carry `schema_version`, `asset_id`, `action_name`, `prompt`, `output_dir`, `source_preference`, optional existing video/provider backend/region/model, generation mode/reference paths, loop and trim fields, frame counts, output switches, background/chroma/rembg settings, processing mode, canvas size, anchor, fit scale, and target-engine notes. `VideoSourceRecord` must record path/hash/container/codecs/dimensions/rotation/duration/rates/VFR/frame count/audio/provider provenance/request fingerprint. `VideoProcessingResult` must list density-keyed frame sets and every generated artifact, timing, cleanup, alignment, diagnostics, and `needs_attention` reasons.

- [ ] Export the public types from `contracts/__init__.py`, rerun `python -m unittest tests.test_video_contract -v`, then run `python -m unittest tests.test_sprite_contract tests.test_map_contract -q`.

- [ ] Commit only these files.

```powershell
git add src/game_visual_forge/contracts/video.py src/game_visual_forge/contracts/__init__.py tests/test_video_contract.py
git commit -m "feat: add video sprite contracts"
```

---

### Task 2: Define model catalogs, attempts, and paid-confirmation binding

**Files:**
- Create: `src/game_visual_forge/contracts/video_provider.py`
- Modify: `src/game_visual_forge/contracts/provider.py`
- Modify: `src/game_visual_forge/contracts/__init__.py`
- Test: `tests/test_video_provider_contract.py`

**Interfaces:** Consumes discovered provider evidence and cost estimates. Produces hash-stable model snapshots, compatible profiles, one-shot `VideoPaidConfirmation`, and backend-bound `VideoGenerationAttempt` state.

- [ ] Write failing tests covering `ExternalProvider.MINIMAX`, `ProviderCommand.MODELS`, snapshot canonical hash, `discovered-unprofiled`, MiniMax-H3 profile data, secret-field rejection, unverified-estimate acknowledgement, changed snapshot invalidation, one-shot consumption, and legal attempt transitions.

```python
def test_confirmation_binds_backend_snapshot_and_reference_hashes(self) -> None:
    confirmation = VideoPaidConfirmation.create(
        attempt_id="attempt-1", provider=ExternalProvider.MINIMAX,
        backend=VideoProviderBackend.API, region="global",
        model="MiniMax-H3", model_snapshot_sha256="a" * 64,
        mode=VideoGenerationMode.I2V_FIRST, parameters={"duration": 6},
        reference_sha256=("b" * 64,), quantity=1,
        estimate=unverified_estimate(), estimate_acknowledged=True,
        request_fingerprint="c" * 64, confirmed_at="2026-08-09T00:00:00Z")
    with self.assertRaisesRegex(ValueError, "binding"):
        confirmation.assert_authorizes(**bound_values(model_snapshot_sha256="d" * 64))
```

- [ ] Run `python -m unittest tests.test_video_provider_contract -v` and verify the missing types fail.

- [ ] Add `MINIMAX = "minimax"` without removing existing provider enum values, and `MODELS = "models"` without changing existing command values.

- [ ] Implement:

```python
class VideoProviderBackend(StrEnum):
    API = "api"
    CLI = "cli"

class VideoModelSupport(StrEnum):
    PROFILED = "profiled"
    DISCOVERED_UNPROFILED = "discovered-unprofiled"
    HISTORICAL = "historical"

class VideoAttemptStatus(StrEnum):
    PREPARED = "prepared"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    DOWNLOADED = "downloaded"
    SUBMISSION_UNKNOWN = "submission_unknown"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

`VideoModelProfile` must include provider/model/endpoint generation/endpoint/supported modes/reference roles/duration/resolution/aspect constraints/audio/backend support/profile revision. `VideoModelCatalogSnapshot.create` canonicalizes sanitized discovery inputs and computes its own SHA-256. `VideoPaidConfirmation` must bind every approved field named in the design, require `estimate_acknowledged=True` when `verified=False`, and expose `authorize_attempt(now="2026-08-09T00:00:00Z")` exactly once. `VideoGenerationAttempt` must store sanitized non-secret parameters, task/file IDs, status, downloaded path/hash, timestamps, and error code; transition validation must forbid changing provider/backend/model/snapshot after preparation.

- [ ] Run the focused test and generic paid/provider regressions: `python -m unittest tests.test_video_provider_contract tests.test_paid_confirmation tests.test_provider_cli -v`.

- [ ] Commit.

```powershell
git add src/game_visual_forge/contracts/video_provider.py src/game_visual_forge/contracts/provider.py src/game_visual_forge/contracts/__init__.py tests/test_video_provider_contract.py
git commit -m "feat: add video provider state contracts"
```

---

### Task 3: Add deterministic video routing and planning

**Files:**
- Create: `src/game_visual_forge/routing/video.py`
- Modify: `src/game_visual_forge/routing/__init__.py`
- Create: `src/game_visual_forge/cli/video.py`
- Test: `tests/test_video_routing.py`
- Test: `tests/test_video_plan.py`

**Interfaces:** Consumes `VideoSpriteRequest`, explicit selection, and optional preflight. Produces `VideoSourceDecision` and an `ExecutionPlan`; does not invoke providers or FFmpeg.

- [ ] Write tests proving existing file never requests paid confirmation, generated routes require an explicit provider/backend, available credentials only report capability, mismatched selection is rejected, and the plan contains the three approved gates.

```python
def test_detection_never_selects_backend(self) -> None:
    decision = route_video(request(source_preference=None), available_backends={
        ExternalProvider.MINIMAX: (VideoProviderBackend.API, VideoProviderBackend.CLI)
    })
    self.assertTrue(decision.requires_user_selection)
    self.assertIsNone(decision.backend)

def test_existing_video_skips_provider_steps(self) -> None:
    plan = build_video_execution_plan(existing_request(), now="2026-08-09T00:00:00Z")
    self.assertNotIn("paid-submit-confirmation", [step.name for step in plan.steps])
```

- [ ] Run both focused modules and verify missing routing/CLI symbols fail.

- [ ] Implement `route_video` as a pure function and `build_video_execution_plan` with the consolidated creative/delivery gate, optional paid gate, and final motion review gate. Persist no state and perform no preflight in these functions.

- [ ] Run `python -m unittest tests.test_video_routing tests.test_video_plan tests.test_sprite_routing -v`.

- [ ] Commit.

```powershell
git add src/game_visual_forge/routing/video.py src/game_visual_forge/routing/__init__.py src/game_visual_forge/cli/video.py tests/test_video_routing.py tests/test_video_plan.py
git commit -m "feat: plan and route video sprite work"
```

---

### Task 4: Discover FFmpeg tools, probe media, and ingest immutable video

**Files:**
- Create: `src/game_visual_forge/processing/video_probe.py`
- Modify: `src/game_visual_forge/processing/__init__.py`
- Create: `tests/fixtures/fake_ffprobe.py`
- Test: `tests/test_video_probe.py`

**Interfaces:** Consumes explicit tool paths/environment/PATH and a repository-local source path. Produces `VideoToolchain`, parsed probe metadata, and a hash-bound `VideoSourceRecord`; never mutates the source.

- [ ] Write tests for precedence `explicit > env > PATH > documented Windows locations`, paired ffmpeg/ffprobe validation, rotation metadata, VFR detection, missing stream, invalid dimensions/duration, undecodable input, trim range rejection, audio presence, and unchanged source hash.

```python
def test_probe_normalizes_rotation_and_detects_vfr(self) -> None:
    metadata = parse_ffprobe_json(load_fixture("ffprobe-vfr-rotated.json"))
    self.assertEqual((metadata.display_width, metadata.display_height), (720, 1280))
    self.assertEqual(metadata.display_rotation, 90)
    self.assertTrue(metadata.variable_frame_rate)

def test_ingest_does_not_reencode_source(self) -> None:
    before = sha256_file(source)
    record = ingest_video(root, source, request_fingerprint="a" * 64, toolchain=fake_tools)
    self.assertEqual(record.sha256, before)
    self.assertEqual(sha256_file(source), before)
```

- [ ] Run `python -m unittest tests.test_video_probe -v` and verify import failure.

- [ ] Implement tool discovery with `shutil.which`, dedicated `GAME_VISUAL_FORGE_FFMPEG` and `GAME_VISUAL_FORGE_FFPROBE` environment variables, and explicit documented Windows candidates. Execute `ffprobe -v error -show_streams -show_format -of json inputs/source.mp4` as an argument array with `shell=False`; convert rational rates safely and validate the selected interval.

- [ ] Run focused tests plus the existing shared-processing regression: `python -m unittest tests.test_sprite_processing -q`.

- [ ] Commit.

```powershell
git add src/game_visual_forge/processing/video_probe.py src/game_visual_forge/processing/__init__.py tests/fixtures/fake_ffprobe.py tests/test_video_probe.py
git commit -m "feat: probe and ingest source video"
```

---

### Task 5: Implement timestamp sampling and deterministic frame extraction

**Files:**
- Create: `src/game_visual_forge/processing/video_frames.py`
- Create: `tests/fixtures/fake_ffmpeg.py`
- Test: `tests/test_video_sampling.py`

**Interfaces:** Consumes validated source metadata, interval, loop flag, and requested densities. Produces the highest-density raw sequence once, derived lower-density index maps, and timestamp/source-index records.

- [ ] Write pure timestamp tests for loop `[start,end)`, non-loop endpoint inclusion, a one-frame request, 8/16/24/48 density derivation, non-zero trims, and decimal stability.

```python
def test_loop_excludes_duplicate_endpoint(self) -> None:
    self.assertEqual(sample_timestamps(1.0, 2.0, 4, loop=True), (1.0, 1.25, 1.5, 1.75))

def test_non_loop_includes_both_endpoints(self) -> None:
    self.assertEqual(sample_timestamps(1.0, 2.0, 3, loop=False), (1.0, 1.5, 2.0))

def test_lower_densities_are_indices_into_highest_timeline(self) -> None:
    plan = build_sampling_plan(0.0, 2.0, (8, 16, 24, 48), loop=True)
    self.assertEqual(plan.extract_count, 48)
    self.assertEqual(len(plan.indices_by_count[8]), 8)
    self.assertTrue(set(plan.indices_by_count[24]).issubset(range(48)))
```

- [ ] Add fake-FFmpeg tests that assert argument arrays include presentation-timestamp selection and rotation normalization, output names are ordered, and extraction failure leaves no accepted raw-frame record.

- [ ] Run `python -m unittest tests.test_video_sampling -v` and verify failure.

- [ ] Implement `sample_timestamps`, `derive_density_indices`, `build_sampling_plan`, and `extract_highest_density`. Use `Decimal` for plan construction and explicit per-timestamp `-ss` extraction to make timestamps auditable; record the exact command-independent timestamp in `VideoFrameRecord`. Lower densities copy/link already-extracted frames in deterministic source order and never invoke FFmpeg again.

- [ ] Run `python -m unittest tests.test_video_sampling -v`.

- [ ] Commit.

```powershell
git add src/game_visual_forge/processing/video_frames.py tests/fixtures/fake_ffmpeg.py tests/test_video_sampling.py
git commit -m "feat: sample and extract video frames"
```

---

### Task 6: Clean, align, normalize, and export every requested density

**Files:**
- Create: `src/game_visual_forge/processing/video_sprite.py`
- Modify: `src/game_visual_forge/processing/__init__.py`
- Modify: `src/game_visual_forge/processing/export.py`
- Test: `tests/test_video_processing.py`

**Interfaces:** Consumes raw density sequences plus request settings. Produces clean and delivery frames, strips, sheets, GIF, frame timing, and `VideoProcessingResult` in staging.

- [ ] Write Pillow-gated tests for preserve/chroma/rembg modes, explicit chroma requirement, rembg CUDA-to-CPU order, permitted chroma fallback, failure without valid fallback, transparent trimming, stable bottom-center anchor, one canvas/scale across frames, nearest pixel resize, high-quality HD resize, and frame/strip/sheet/GIF ordering.

```python
def test_rembg_failure_without_chroma_marks_attention(self) -> None:
    result = process_video_sprite(root, request(background_mode="rembg", chroma_color=None), source, sampling, remover=failing_remover)
    self.assertTrue(result.needs_attention)
    self.assertIn("background-removal-failed", result.attention_reasons)
    self.assertEqual(result.delivery_frames, {})

def test_all_frames_share_canvas_and_bottom_center_anchor(self) -> None:
    result = process_video_sprite(root, hd_request(canvas=(96, 96)), source, sampling)
    sizes = {Image.open(root / path).size for paths in result.delivery_frames.values() for path in paths}
    self.assertEqual(sizes, {(96, 96)})
```

- [ ] Run `python -m unittest tests.test_video_processing -v` and verify failure.

- [ ] Implement orchestration using `remove_background`, `trim_alpha`, `align_bottom_center`, and delivery normalization. Generalize export helpers only by accepting an ordered sequence plus explicit rows/columns/frame duration; keep the current sprite signatures backward compatible.

- [ ] Write `frame-timing.json` with density, delivery index, source timestamp, source index when known, duration, loop semantics, and frame hash. Keep raw frames in staging evidence and include only requested runtime output types in `VideoProcessingResult`.

- [ ] Run `python -m unittest tests.test_video_processing tests.test_sprite_processing -v`.

- [ ] Commit.

```powershell
git add src/game_visual_forge/processing/video_sprite.py src/game_visual_forge/processing/__init__.py src/game_visual_forge/processing/export.py tests/test_video_processing.py
git commit -m "feat: process video into sprite outputs"
```

---

### Task 7: Generate motion-review evidence and temporal metrics

**Files:**
- Create: `src/game_visual_forge/processing/video_review.py`
- Create: `src/game_visual_forge/contracts/video_review.py`
- Modify: `src/game_visual_forge/contracts/__init__.py`
- Test: `tests/test_video_review.py`

**Interfaces:** Consumes source, timing, clean/delivery frames, and generated runtime outputs. Produces timestamped contact sheet, motion-difference image, anchor/bounds diagnostic, temporal metric records, and a hash-bound `VideoMotionReview`.

- [ ] Write tests for visible timestamps on the contact sheet, non-empty motion difference, anchor diagnostic dimensions, exact/near duplicate rate, static intervals, motion coverage, bounds/area variation, anchor jitter, first/last loop difference, alpha coverage, clipping risk, and current-artifact review validation.

```python
def test_review_becomes_stale_when_preview_changes(self) -> None:
    review = record_video_motion_review(bundle, approved=True, reviewed_at=NOW)
    (root / bundle.preview_gif).write_bytes(b"changed")
    with self.assertRaisesRegex(ValueError, "hash"):
        validate_video_motion_review(root, review, bundle)

def test_static_hold_is_attention_not_deterministic_failure(self) -> None:
    metrics = calculate_temporal_metrics(repeated_frames)
    self.assertGreater(metrics.exact_duplicate_rate, 0.5)
    self.assertIn("static-interval", metrics.attention_reasons)
```

- [ ] Run `python -m unittest tests.test_video_review -v` and verify failure.

- [ ] Implement review images with Pillow and deterministic pixel metrics. Record both source anchors and normalized anchors. `VideoMotionReview` binds request/source/quality/contact sheet/GIF/diagnostics/strips/sheets hashes and includes identity, appearance, action, direction, timing, anatomy, camera, drift, cleanup, loop, text/watermark, and duplicate review checks.

- [ ] Run focused tests.

- [ ] Commit.

```powershell
git add src/game_visual_forge/processing/video_review.py src/game_visual_forge/contracts/video_review.py src/game_visual_forge/contracts/__init__.py tests/test_video_review.py
git commit -m "feat: add video motion review evidence"
```

---

### Task 8: Gate publication with video quality and manifest integrity

**Files:**
- Create: `src/game_visual_forge/quality/video.py`
- Modify: `src/game_visual_forge/quality/__init__.py`
- Test: `tests/test_video_quality.py`

**Interfaces:** Consumes request/source/optional provider attempt/processing result and, in the publication phase, the review. Produces a pre-review `VideoQualityReport`, then revalidates that exact report and current artifacts to produce the generic `AssetManifest` and atomic publication decision.

- [ ] Write tests for every blocking condition: request/source/attempt/snapshot/artifact hash mismatch; missing/corrupt/unordered/out-of-range/wrong-count frames; wrong strip/sheet dimensions; empty/out-of-canvas content; fully opaque output when transparency requested; manifest role/path/hash mismatch; missing/stale/rejected final review.

```python
def test_temporal_warning_does_not_replace_hard_failure(self) -> None:
    report = validate_video_outputs(bundle_with_static_hold())
    self.assertEqual(report.deterministic_status, QualityStatus.PASSED)
    self.assertEqual(report.temporal_status, QualityStatus.NEEDS_ATTENTION)

def test_publish_requires_current_approved_review(self) -> None:
    report, manifest = build_validated_video_bundle(stale_review=True)
    self.assertFalse(publish_video_outputs(staging, final, report, manifest))
    self.assertFalse(final.exists())
```

- [ ] Run `python -m unittest tests.test_video_quality -v` and verify failure.

- [ ] Implement `assess_video_outputs` to create the automated pre-review `VideoQualityReport` immediately after processing. Implement `validate_reviewed_video_outputs` to recompute deterministic checks and metrics, require byte-for-byte-equivalent current evidence plus an approved hash-bound review, and then build the manifest. `VideoQualityReport` is a versioned video-specific contract containing generic deterministic/visual checks plus structured temporal metrics/status. Build manifest artifact roles for source provenance, timing, requested runtime outputs, preview evidence, processing result, quality report, and review. Validate every staged hash immediately before publishing through a temporary sibling directory and atomic replace.

- [ ] Run `python -m unittest tests.test_video_quality tests.test_sprite_quality tests.test_tilemap_manifest_integrity -v`.

- [ ] Commit.

```powershell
git add src/game_visual_forge/quality/video.py src/game_visual_forge/quality/__init__.py tests/test_video_quality.py
git commit -m "feat: validate and publish video sprite bundles"
```

---

### Task 9: Implement the MiniMax Hailuo API and `mmx` compatibility adapter

**Files:**
- Create: `src/game_visual_forge/providers/minimax_video.py`
- Create: `skills/forge-video-to-sprite/scripts/providers/minimax.py`
- Test: `tests/test_minimax_video_provider.py`

**Interfaces:** Reads sanitized JSON on stdin and environment credentials/local CLI state. Writes one versioned sanitized JSON object for `capabilities`, `models`, `preflight`, `estimate`, `prepare`, `submit`, `query`, or `download`.

- [ ] Write fake-transport tests for China/global base URLs, API-key absence, `/v1/models` snapshot, MiniMax-H3 `/v2/video_generation` content-array payload, profiled legacy model visibility only when discovered, unknown `discovered-unprofiled` blocking on API, `mmx` version/help/auth discovery, and CLI no-charge model validation.

```python
def test_h3_uses_v2_content_array(self) -> None:
    request = build_minimax_submit_payload(model="MiniMax-H3", mode="i2v-first", prompt="walk", first_frame_url="memory://prepared/first")
    self.assertEqual(request.endpoint, "/v2/video_generation")
    self.assertEqual(request.body["model"], "MiniMax-H3")
    self.assertIsInstance(request.body["content"], list)

def test_unknown_api_model_is_visible_but_not_submittable(self) -> None:
    snapshot = discover_models(fake_http(models=["MiniMax-H3", "MiniMax-Future"]))
    self.assertEqual(snapshot.model("MiniMax-Future").support, VideoModelSupport.DISCOVERED_UNPROFILED)
    with self.assertRaisesRegex(ValueError, "unprofiled"):
        prepare_api_submission(snapshot, model="MiniMax-Future")
```

- [ ] Run `python -m unittest tests.test_minimax_video_provider -v` and verify failure.

- [ ] Implement a dependency-injected standard-library HTTP transport. Read the API key only at request time, redact raised errors, discard transient signed URLs after download, and include adapter/CLI versions and refresh time in snapshots. The initial profile registry must include MiniMax-H3; older profiles are offered only when live discovery returns them.

- [ ] Implement the launcher as the same repository-root bootstrap pattern as `scripts/run.py`, then call `minimax_video.main()`; it must not contain credentials or provider logic.

- [ ] Run focused tests and `python skills/forge-video-to-sprite/scripts/providers/minimax.py capabilities` with a sanitized test payload piped through the test harness, not live credentials.

- [ ] Commit.

```powershell
git add src/game_visual_forge/providers/minimax_video.py skills/forge-video-to-sprite/scripts/providers/minimax.py tests/test_minimax_video_provider.py
git commit -m "feat: add minimax video adapter"
```

---

### Task 10: Implement Jimeng signed API and `dreamina` compatibility adapter

**Files:**
- Create: `src/game_visual_forge/providers/jimeng_video.py`
- Create: `skills/forge-video-to-sprite/scripts/providers/jimeng.py`
- Test: `tests/test_jimeng_video_provider.py`

**Interfaces:** Implements the same adapter command contract as Task 9 while keeping Jimeng API and CLI authentication/task recovery isolated.

- [ ] Write official-example-vector tests for canonical request/HMAC signing, missing AK/SK, product/capability snapshot, sanitized estimate, submit/query/download mappings, `dreamina` version/help/OAuth capability, and cross-backend task rejection.

```python
def test_api_signature_matches_fixed_vector(self) -> None:
    signed = sign_volcengine_request(method="POST", url=FIXED_URL, headers=FIXED_HEADERS,
                                    body=FIXED_BODY, access_key="AKIDEXAMPLE",
                                    secret_key="secret", now=FIXED_TIME)
    self.assertEqual(signed.authorization, FIXED_EXPECTED_AUTHORIZATION)

def test_cli_cannot_query_api_attempt(self) -> None:
    attempt = attempt_record(provider="jimeng", backend="api", external_task_id="api-1")
    with self.assertRaisesRegex(ValueError, "backend"):
        query_cli_attempt(attempt, fake_dreamina)
```

- [ ] Run `python -m unittest tests.test_jimeng_video_provider -v` and verify failure.

- [ ] Implement local canonical signing with `hashlib`/`hmac`, credential lookup from dedicated environment names, official REST request construction, sanitized responses, and transient download handling. CLI execution must use argument arrays, existing login state, and no automatic install/update/login.

- [ ] Add the thin launcher and run focused tests.

- [ ] Commit.

```powershell
git add src/game_visual_forge/providers/jimeng_video.py skills/forge-video-to-sprite/scripts/providers/jimeng.py tests/test_jimeng_video_provider.py
git commit -m "feat: add jimeng video adapter"
```

---

### Task 11: Orchestrate one-shot provider submission and recovery

**Files:**
- Create: `src/game_visual_forge/providers/video.py`
- Modify: `src/game_visual_forge/providers/__init__.py`
- Modify: `src/game_visual_forge/providers/cli.py`
- Create: `tests/fixtures/fake_video_provider.py`
- Test: `tests/test_video_provider_orchestration.py`

**Interfaces:** Consumes adapter executable, request, snapshot, estimate, confirmation, and attempt path. Atomically persists attempts and confirmation, invokes exactly one submit, and exposes query/download-only recovery.

- [ ] Write tests asserting fixed operation order, confirmation consumption before transport, one submit invocation, timeout/invalid JSON/no definitive receipt to `submission_unknown`, no resubmit from unknown/failed state, query-only recovery, backend preservation, atomic non-empty download/hash, and secret/signed-URL rejection.

```python
def test_submit_persists_before_single_transport_call(self) -> None:
    receipt = submit_video_attempt(paths, confirmation, fake_provider)
    events = read_events(fake_provider.event_log)
    self.assertEqual(events.count("submit"), 1)
    persisted = VideoGenerationAttempt.from_dict(load_json(paths.attempt))
    self.assertEqual(persisted.status, VideoAttemptStatus.SUBMITTED)
    self.assertIsNotNone(load_json(paths.confirmation)["consumed_at"])

def test_timeout_becomes_unknown_and_cannot_resubmit(self) -> None:
    result = submit_video_attempt(paths, confirmation, timeout_provider)
    self.assertEqual(result.status, VideoAttemptStatus.SUBMISSION_UNKNOWN)
    with self.assertRaisesRegex(ForgeError, "query"):
        submit_video_attempt(paths, confirmation, fake_provider)
```

- [ ] Run `python -m unittest tests.test_video_provider_orchestration -v` and verify failure.

- [ ] Extend the safe boundary for `MODELS` while keeping `SUBMIT` protected. Implement atomic JSON writes using a sibling temporary file plus `Path.replace`, and download using a temporary media file, non-zero size/probe validation, SHA-256, then atomic replace. Never serialize adapter stdout beyond parsed allowlisted fields.

- [ ] Run `python -m unittest tests.test_video_provider_orchestration tests.test_provider_cli tests.test_job_state -v`.

- [ ] Commit.

```powershell
git add src/game_visual_forge/providers/video.py src/game_visual_forge/providers/__init__.py src/game_visual_forge/providers/cli.py tests/fixtures/fake_video_provider.py tests/test_video_provider_orchestration.py
git commit -m "feat: orchestrate recoverable video generation"
```

---

### Task 12: Wire the complete `video` CLI and clean local workflow

**Files:**
- Modify: `src/game_visual_forge/cli/video.py`
- Modify: `src/game_visual_forge/cli/main.py`
- Test: `tests/test_video_cli.py`
- Test: `tests/test_video_clean_workflow.py`

**Interfaces:** Exposes the approved command surface and machine-readable output. Connects state transitions, contracts, adapters, processing, review, validation, and publication.

- [ ] Add parser/dispatch tests for exactly:

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

- [ ] Add a clean existing-video integration test using fake FFmpeg/FFprobe that runs plan → route → ingest → process → record-review → validate, then asserts completed job state, final manifest/hash integrity, every requested density, and zero provider events.

- [ ] Add a fake generated-video integration test that runs models → preflight → estimate → confirmation fixture → submit → query → download → the same ingest/process/review/validate path, then asserts one submit and no backend switching.

- [ ] Run `python -m unittest tests.test_video_cli tests.test_video_clean_workflow -v` and verify parser/dispatch failures.

- [ ] Implement nested argparse groups and runners with these required file boundaries: `provider models/preflight/estimate` write sanitized snapshot/preflight/estimate JSON; `provider submit` reads request, snapshot, estimate, explicit confirmation, and attempt paths; `provider query/download` read only the saved attempt and adapter path; `sprite ingest` reads request/decision plus either `--video` or `--attempt`; `sprite process` writes processing outputs, review evidence, and the automated pre-review quality report; `sprite record-review` reads that report and every displayed artifact before writing the approval; `sprite validate` recomputes checks and verifies the bound review before publication. Successful stdout is one schema-versioned JSON object; `ForgeError` output remains sanitized.

- [ ] Run focused tests plus `python -m unittest tests.test_cli_dry_run tests.test_skill_contracts -v` to prove top-level compatibility.

- [ ] Commit.

```powershell
git add src/game_visual_forge/cli/video.py src/game_visual_forge/cli/main.py tests/test_video_cli.py tests/test_video_clean_workflow.py
git commit -m "feat: expose complete video sprite workflow"
```

---

### Task 13: Rewrite the Skill and document manual setup concisely

**Files:**
- Rewrite: `skills/forge-video-to-sprite/SKILL.md`
- Create: `skills/forge-video-to-sprite/references/provider-workflow.md`
- Create: `skills/forge-video-to-sprite/references/processing-and-quality.md`
- Modify: `skills/forge-video-to-sprite/agents/openai.yaml`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `install/codex/README.md`
- Modify: `install/claude/README.md`
- Modify: `tests/test_skill_contracts.py`
- Modify: `tests/test_repository_contract.py`

**Interfaces:** Teaches installed agents when and how to run the complete workflow, which questions can be consolidated, how paid actions are gated, and what users install/configure manually.

- [ ] Update contract tests first. Require the three gates, existing/MiniMax/Jimeng sources, API/CLI backend separation, `MiniMax-H3`, live snapshot/unprofiled behavior, FFmpeg discovery, 8/16/24/48 sampling, cleanup modes, review evidence, `submission_unknown`, and every CLI command. Forbid references to unrelated repositories/Skills and forbid claiming MCP as the core path.

- [ ] Add README tests requiring concise English/Chinese FFmpeg, `mmx`, `dreamina`, API credential, local-only and optional cleanup notes while retaining the 180-line cap and repository-local test command.

- [ ] Run `python -m unittest tests.test_skill_contracts tests.test_repository_contract -v` and verify documentation assertions fail.

- [ ] Rewrite `SKILL.md` in imperative form and keep it below 500 lines. Structure it around: intake extraction → one consolidated creative/delivery confirmation → explicit route/backend → model/preflight/estimate → paid confirmation only for generation → one-shot task/recovery → local processing → final motion review → validation/publication. State that provider/model/backend/price changes invalidate confirmation and that local revisions reuse the same video.

- [ ] Put provider command examples and credential/CLI setup in `provider-workflow.md`; put FFmpeg discovery, sampling semantics, outputs, metrics, and hard/visual gates in `processing-and-quality.md`. Link both references directly from `SKILL.md`, avoid duplicating their details in the body, and add a table of contents to any reference that exceeds 100 lines. Keep the root README descriptions brief and link to the Skill.

- [ ] Regenerate metadata deterministically after reading the final Skill; do not hand-edit it. Keep `scripts/run.py` unchanged unless its help test exposes a real issue.

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\generate_openai_yaml.py" skills/forge-video-to-sprite `
  --interface 'display_name=Forge Video to Sprite' `
  --interface 'short_description=Convert video into validated 2D Sprite animation' `
  --interface 'default_prompt=Use $forge-video-to-sprite to convert or generate a video and deliver a validated Sprite animation.'
```

- [ ] Run the focused tests.

- [ ] Commit.

```powershell
git add skills/forge-video-to-sprite/SKILL.md skills/forge-video-to-sprite/references/provider-workflow.md skills/forge-video-to-sprite/references/processing-and-quality.md skills/forge-video-to-sprite/agents/openai.yaml README.md README.zh-CN.md install/codex/README.md install/claude/README.md tests/test_skill_contracts.py tests/test_repository_contract.py
git commit -m "docs: complete video sprite skill workflow"
```

---

### Task 14: Add optional real-FFmpeg coverage and run the clean release gate

**Files:**
- Create: `tests/test_video_ffmpeg_integration.py`
- Modify: `tests/test_repository_contract.py`

**Interfaces:** Verifies the documented dependency surface and an actual synthetic MP4/MOV/WebM decode when FFmpeg is present, while remaining safely skippable when it is absent.

- [ ] Write a test that locates FFmpeg through the production discovery function, skips with an explicit reason if unavailable, creates a short synthetic color/motion clip in a temporary directory, probes it, extracts a small loop, and checks timestamps, rotation-normalized dimensions, and non-empty PNG outputs. Parameterize MP4/MOV/WebM only for encoders available in the discovered build.

```python
@unittest.skipUnless(discover_optional_real_toolchain() is not None, "FFmpeg/FFprobe not installed")
def test_real_ffmpeg_synthetic_video_round_trip(self) -> None:
    source = create_synthetic_motion_video(self.tempdir, duration=1.0, size=(64, 64))
    record = ingest_video(self.tempdir, source, "a" * 64, discover_optional_real_toolchain())
    frames = extract_highest_density(self.tempdir, record, sample_timestamps(0.0, 1.0, 8, loop=True))
    self.assertEqual(len(frames), 8)
    self.assertTrue(all((self.tempdir / frame.raw_path).stat().st_size > 0 for frame in frames))
```

- [ ] Add repository-contract assertions that the existing `image` extra includes Pillow, rembg/PyMatting remain optional extras, and the base dependencies contain neither provider SDKs nor FFmpeg packages.

- [ ] Run `python -m unittest tests.test_video_ffmpeg_integration tests.test_repository_contract -v`.

- [ ] Run the complete repository gate from the repository root:

```powershell
$env:PYTHONUTF8="1"
python -m unittest discover -s tests -q
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills/forge-2d-map
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills/forge-2d-sprite
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills/forge-video-to-sprite
```

Expected result: all unit tests pass; optional real-FFmpeg cases either pass or report a clear skip; all three Skill validations print success; `git status --short` shows only the intended implementation plus the previously deferred bridge-evidence work.

- [ ] After the implementation and validations pass, forward-test the installed Skill in a clean temporary clone with a fresh agent and no provider credentials. Give it only the Skill path and a generic existing-video request such as: `Use $forge-video-to-sprite to convert this short local walking video into 8- and 24-frame looping Sprite sheets with transparent HD output.` Review the raw transcript and artifacts for consolidated intake, zero provider calls, correct commands, review gating, and no leaked implementation hints. Delete only the temporary clone/artifacts after resolving their absolute paths and confirming they are outside the working repository.

- [ ] Inspect tracked text for forbidden scope and unresolved markers using repository-local searches, and inspect staged names before committing:

```powershell
python -m unittest tests.test_forge_skill_scope -v
rg -n "planning-only|即梦或万相" README.md README.zh-CN.md install skills src tests
git diff --check
git diff --cached --name-only
```

Expected result: the search prints no matches in the implementation; `git diff --check` is clean; the staged list does not contain adaptive-river-crossing evidence or `tests/test_tilemap_manifest_integrity.py`.

- [ ] Commit the integration gate.

```powershell
git add tests/test_video_ffmpeg_integration.py tests/test_repository_contract.py
git commit -m "test: verify real video processing integration"
```

## Final Verification and Handoff

- [ ] Re-run `python -m unittest discover -s tests -q` from `G:\GitProject\game-visual-forge`.
- [ ] Run all three `quick_validate.py` commands with `PYTHONUTF8=1`.
- [ ] Compare `git diff 4d766f2..HEAD --name-only` with the file map and confirm every approved P0/P1 area is represented.
- [ ] Confirm `git log --oneline` contains one focused commit per task and no deferred bridge-evidence file is committed.
- [ ] Present provider-live verification as a separate manual checklist; do not perform a paid submit merely to satisfy automated validation.
