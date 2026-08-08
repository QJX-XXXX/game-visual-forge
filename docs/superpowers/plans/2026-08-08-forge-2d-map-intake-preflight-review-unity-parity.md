# Forge 2D Map Intake, Preflight, Review, and Unity Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden `forge-2d-map` so incomplete briefs cannot start, continuity-critical maps route correctly, candidate assets are checked and selectively regenerated before ingest, final user review is consolidated, and Unity placement must match the approved map.

**Architecture:** Add four focused Python boundaries: intake assessment, architecture routing, preassembly review, and assembled review rendering. Bind each transition with canonical JSON and SHA-256 values, keep the existing two user approval gates, and add a Unity scene acceptance validator after import-and-place. Preserve archived request compatibility by making the new intake/preassembly fields optional in deserialization but mandatory when a new two-gate plan contains `intake`.

**Tech Stack:** Python 3.11 dataclasses/enums/JSON, Pillow through the existing optional image dependency, `unittest`, Unity 2022.3 C# Editor APIs, NUnit, Unity Tilemap package.

## Global Constraints

- The repository owns exactly `forge-2d-map`, `forge-2d-sprite`, and `forge-video-to-sprite` under `skills/`.
- Modify only the map workflow and shared code directly required by it.
- Keep exactly two mandatory user approval gates: `style-sample` and `assembled-map`.
- Requirements confirmation and preassembly agent review must not become additional user approval artifacts.
- Preserve legacy request parsing and archived bundle import.
- A changed request or candidate asset must invalidate every dependent hash-bound decision.
- A terminal `rejection.json` remains immutable and blocks validation, publication, and Unity import.
- Native or local automatic regeneration is allowed only inside the confirmed layout, source, cost, art direction, and delivery boundaries.
- Do not stage, rewrite, or commit unrelated dirty worktree files.
- Use new focused test modules where current tracked tests already contain unrelated edits.
- Use test-first implementation for every task; the completed village run is the observed baseline failure for the Skill behavior changes.

---

## File Structure

### New Python modules

- `src/game_visual_forge/contracts/tilemap_intake.py`: grouped intake values, canonical confirmation summary, question groups, and assessment state.
- `src/game_visual_forge/routing/tilemap_architecture.py`: deterministic profile selection and architecture decision serialization.
- `src/game_visual_forge/contracts/tilemap_asset_review.py`: candidate/report/review records and hash validation.
- `src/game_visual_forge/processing/tilemap_asset_preflight.py`: deterministic candidate checks, critical crops, and review sheet rendering.
- `src/game_visual_forge/processing/tilemap_review_sheet.py`: final assembled approval contact sheet rendering.
- `tests/tilemap_workflow_fixtures.py`: complete and incomplete request payload builders used only by the new workflow tests.
- `tests/test_tilemap_intake.py`: intake assessment and plan hard-gate tests.
- `tests/test_tilemap_architecture_routing.py`: profile routing and execution-plan action tests.
- `tests/test_tilemap_asset_preflight.py`: candidate validation, review hashing, and ingest gate tests.
- `tests/test_tilemap_review_sheet.py`: review sheet and assembled approval role tests.
- `tests/test_forge_skill_scope.py`: positive three-Skill repository scope and map Skill workflow contract.

### New Unity files

- `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapSceneAcceptanceValidator.cs`: post-placement hierarchy, transform, bounds, collider, doorway, terrain, and bridge validation.
- `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapSceneAcceptanceValidator.cs.meta`: Unity metadata generated after compilation.

### Modified boundaries

- `src/game_visual_forge/contracts/tilemap.py`: optional intake field and cross-field validation.
- `src/game_visual_forge/contracts/tilemap_sources.py`: preassembly review/report hash binding on new source sets.
- `src/game_visual_forge/contracts/approval.py`: assembled `review-sheet` role.
- `src/game_visual_forge/contracts/__init__.py`: public exports for new contracts.
- `src/game_visual_forge/cli/main.py`: new preflight/review commands and arguments.
- `src/game_visual_forge/cli/planning.py`: architecture-specific actions.
- `src/game_visual_forge/cli/tilemap.py`: plan assessment, preflight, review recording, and ingest enforcement.
- `src/game_visual_forge/processing/tilemap.py`: assembled review sheet artifact and processing result field.
- `src/game_visual_forge/quality/tilemap.py`: publication hash checks for new workflow artifacts.
- `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleContracts.cs`: review-sheet and scene-acceptance report fields plus collision JSON records.
- `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapApprovalValidator.cs`: seven-role assembled approval validation.
- `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleImporter.cs`: invoke scene acceptance only after import-and-place.
- `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapImportReportWriter.cs`: write scene acceptance status/path.
- `integrations/unity/com.game-visual-forge.tilemap/Tests/Editor/TilemapBundleImporterEditModeTests.cs`: scene acceptance regression tests.
- `skills/forge-2d-map/SKILL.md`: grouped intake, routing, targeted regeneration, consolidated review, and Unity completion workflow.
- `skills/forge-2d-map/agents/openai.yaml`: interface wording aligned with the revised Skill.

---

### Task 1: Grouped intake contract and canonical confirmation

**Files:**
- Create: `src/game_visual_forge/contracts/tilemap_intake.py`
- Create: `tests/tilemap_workflow_fixtures.py`
- Create: `tests/test_tilemap_intake.py`
- Modify: `src/game_visual_forge/contracts/tilemap.py`
- Modify: `src/game_visual_forge/contracts/__init__.py`

**Interfaces:**
- Produces: `LayoutStrategy`, `TileMapImportMode`, `TileMapIntakeStatus`, `TileMapQuestionGroup`, `TileMapIntake`, `TileMapIntakeAssessment`.
- Produces: `assess_tilemap_intake(payload: dict[str, Any]) -> TileMapIntakeAssessment`.
- Produces: `canonical_tilemap_confirmation_summary(intake: TileMapIntake) -> str`.
- Produces: `tilemap_confirmation_sha256(intake: TileMapIntake) -> str`.
- Modifies: `TileMapRequest.intake: TileMapIntake | None` with round-trip serialization.
- Compatibility: `TileMapRequest.from_dict` accepts archived payloads without `intake`; new plan enforcement is Task 2.

- [ ] **Step 1: Add failing intake tests**

Create `tests/tilemap_workflow_fixtures.py` with a builder that returns a full coherent-foundation request payload and accepts `intake_overrides`:

```python
def build_workflow_request_payload(*, intake_overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload = build_existing_complete_tilemap_payload()
    payload["approval_workflow"] = "two_gate"
    payload["intake"] = {
        "schema_version": 1,
        "gameplay_actions": ["walk", "collide", "enter-buildings"],
        "walkability_required": True,
        "collision_required": True,
        "enterable_buildings_required": True,
        "triggers_required": True,
        "perspective": "top-down",
        "map_scale": "medium",
        "art_style": "modern-pixel",
        "mood": "spring-sunny-cozy",
        "water_policy": "blocked",
        "bridge_policy": "horizontal-traversable",
        "continuity_features": ["watercourse", "bridge", "paths", "building-pads"],
        "object_identities": ["inn", "shop", "player-home"],
        "entrance_policy": "bottom-center-open",
        "engine_target": "Unity_Tilemap",
        "project_id": "2DMirrorDemo",
        "scene_path": "Assets/Scenes/SampleScene.unity",
        "import_mode": "import_and_place",
        "source_preference": "agent-native",
        "native_generation_allowed": True,
        "paid_provider_allowed": False,
        "targeted_regeneration_allowed": True,
        "layout_strategy": "fixed_authored",
        "requirements_confirmed": False,
        "confirmed_summary_sha256": None,
    }
    payload["intake"].update(intake_overrides or {})
    return payload
```

Add tests proving:

```python
class TileMapIntakeTests(unittest.TestCase):
    def test_missing_fields_are_grouped_once_in_stable_order(self) -> None:
        payload = build_workflow_request_payload(intake_overrides={"art_style": "", "mood": "", "scene_path": ""})
        assessment = assess_tilemap_intake(payload)
        self.assertEqual(assessment.status, TileMapIntakeStatus.NEEDS_USER_INPUT)
        self.assertEqual([item.question_group_id for item in assessment.question_groups], ["visual", "delivery"])

    def test_complete_unconfirmed_intake_returns_one_summary(self) -> None:
        assessment = assess_tilemap_intake(build_workflow_request_payload())
        self.assertEqual(assessment.status, TileMapIntakeStatus.NEEDS_USER_CONFIRMATION)
        self.assertIn("Player", assessment.confirmation_summary)
        self.assertEqual(len(assessment.confirmation_sha256), 64)

    def test_changed_intake_invalidates_confirmation_hash(self) -> None:
        payload = build_workflow_request_payload()
        first = assess_tilemap_intake(payload)
        payload["intake"].update(requirements_confirmed=True, confirmed_summary_sha256=first.confirmation_sha256)
        self.assertEqual(assess_tilemap_intake(payload).status, TileMapIntakeStatus.CONFIRMED)
        payload["intake"]["art_style"] = "hand-painted"
        self.assertEqual(assess_tilemap_intake(payload).status, TileMapIntakeStatus.NEEDS_USER_CONFIRMATION)
```

- [ ] **Step 2: Run the intake tests and confirm RED**

Run:

```powershell
python -m unittest tests.test_tilemap_intake -v
```

Expected: import failure for `game_visual_forge.contracts.tilemap_intake`.

- [ ] **Step 3: Implement intake types and assessment**

Implement immutable records in `tilemap_intake.py`. Use an ordered definition instead of ad-hoc prompts:

```python
QUESTION_GROUP_FIELDS = {
    "gameplay": ("gameplay_actions", "walkability_required", "collision_required", "enterable_buildings_required", "triggers_required"),
    "visual": ("perspective", "map_scale", "art_style", "mood"),
    "topology": ("water_policy", "bridge_policy", "continuity_features"),
    "objects": ("object_identities", "entrance_policy"),
    "delivery": ("engine_target", "project_id", "scene_path", "import_mode"),
    "source": ("source_preference", "native_generation_allowed", "paid_provider_allowed", "targeted_regeneration_allowed"),
}
```

Canonicalize the summary with explicit ordered lines and hash UTF-8 bytes with `hashlib.sha256`. Treat `False` as answered and only `None`, empty strings, and empty required tuples as missing. If complete but the stored hash does not match, return `NEEDS_USER_CONFIRMATION` even when `requirements_confirmed` is true.

Add `intake` serialization to `TileMapRequest` without changing archived requests that omit it. Validate only direct contradictions at contract construction:

```python
if self.intake is not None and self.intake.engine_target != self.engine_target.value:
    raise ValueError("intake engine_target must match engine_target")
```

- [ ] **Step 4: Run focused intake and contract tests**

Run:

```powershell
python -m unittest tests.test_tilemap_intake tests.test_coherent_foundation_tilemap -v
```

Expected: PASS.

- [ ] **Step 5: Commit the intake contract**

```powershell
git add src/game_visual_forge/contracts/tilemap_intake.py src/game_visual_forge/contracts/tilemap.py src/game_visual_forge/contracts/__init__.py tests/tilemap_workflow_fixtures.py tests/test_tilemap_intake.py
git commit -m "feat: add grouped tilemap intake contract"
```

---

### Task 2: Plan hard gate and architecture routing

**Files:**
- Create: `src/game_visual_forge/routing/tilemap_architecture.py`
- Create: `tests/test_tilemap_architecture_routing.py`
- Modify: `src/game_visual_forge/routing/__init__.py`
- Modify: `src/game_visual_forge/cli/planning.py`
- Modify: `src/game_visual_forge/cli/tilemap.py`
- Modify: `tests/test_tilemap_intake.py`

**Interfaces:**
- Consumes: `TileMapIntake`, `TileMapRequest`, `TileSetProfile`.
- Produces: `TileMapArchitectureDecision` with `to_dict` and `from_dict`.
- Produces: `select_tilemap_architecture(request: TileMapRequest, request_fingerprint: str) -> TileMapArchitectureDecision`.
- Changes: `build_tilemap_execution_plan(request, architecture)` requires the decision.
- Changes: `run_tilemap_plan` may return `needs_user_input`, `needs_user_confirmation`, or `planned`.

- [ ] **Step 1: Add failing plan and routing tests**

Add to `tests/test_tilemap_intake.py`:

```python
def test_plan_writes_nothing_before_intake_confirmation(self) -> None:
    request_path = self.write_request(build_workflow_request_payload())
    result = run_tilemap_plan(request_path, self.out_dir, "2026-08-08T00:00:00Z")
    self.assertEqual(result["status"], "needs_user_confirmation")
    self.assertFalse((self.out_dir / "execution-plan.json").exists())
    self.assertFalse((self.out_dir / "job-state.json").exists())
```

Create routing tests:

```python
def test_fixed_continuity_map_selects_coherent_foundation(self) -> None:
    request = confirmed_request(layout_strategy="fixed_authored", continuity_features=("watercourse", "bridge"))
    decision = select_tilemap_architecture(request, fingerprint_request(request.to_dict()))
    self.assertEqual(decision.selected_profile, TileSetProfile.COHERENT_FOUNDATION)
    self.assertTrue(decision.requires_complete_foundation)

def test_reusable_map_selects_demand_driven(self) -> None:
    request = confirmed_request(layout_strategy="reusable_tiles", continuity_features=())
    decision = select_tilemap_architecture(request, fingerprint_request(request.to_dict()))
    self.assertEqual(decision.selected_profile, TileSetProfile.DEMAND_DRIVEN)

def test_profile_conflict_blocks_plan(self) -> None:
    request = confirmed_request(layout_strategy="fixed_authored", profile="demand_driven")
    with self.assertRaisesRegex(ValueError, "architecture requires coherent_foundation"):
        select_tilemap_architecture(request, fingerprint_request(request.to_dict()))
```

- [ ] **Step 2: Run the new tests and confirm RED**

```powershell
python -m unittest tests.test_tilemap_intake tests.test_tilemap_architecture_routing -v
```

Expected: missing architecture module and current plan creating files before confirmation.

- [ ] **Step 3: Implement deterministic architecture routing**

Use these continuity triggers for `fixed_authored`:

```python
COHERENT_FEATURES = frozenset({"watercourse", "bridge", "complex-paths", "paths", "building-pads"})
requires_coherent = intake.layout_strategy is LayoutStrategy.FIXED_AUTHORED and bool(COHERENT_FEATURES.intersection(intake.continuity_features))
selected = TileSetProfile.COHERENT_FOUNDATION if requires_coherent else TileSetProfile.DEMAND_DRIVEN
```

Reject a declared profile that differs from `selected`. Populate `continuity_reasons` in the order provided by the intake, filtered to the triggering set.

Update execution-plan source actions:

```python
if architecture.selected_profile is TileSetProfile.COHERENT_FOUNDATION:
    obtain_action = "obtain-coherent-foundation-and-objects"
else:
    obtain_action = "obtain-demand-driven-tiles-and-objects"
```

- [ ] **Step 4: Implement the `plan` state machine**

In `run_tilemap_plan`, load raw JSON first and call `assess_tilemap_intake`. Return grouped question dictionaries or the confirmation summary without resolving `out_dir` or writing files. Only after `CONFIRMED`:

```python
request = TileMapRequest.from_dict(payload)
fingerprint = fingerprint_request(request.to_dict())
architecture = select_tilemap_architecture(request, fingerprint)
dump_json(out_dir / "architecture-decision.json", architecture.to_dict())
dump_json(out_dir / "execution-plan.json", build_tilemap_execution_plan(request, architecture).to_dict())
```

For archived requests without `intake`, retain current planning behavior only when `approval_workflow != "two_gate"`. A new two-gate plan without intake returns `needs_user_input` with all six question groups.

- [ ] **Step 5: Run focused planning tests**

```powershell
python -m unittest tests.test_tilemap_intake tests.test_tilemap_architecture_routing tests.test_execution_plan -v
```

Expected: PASS.

- [ ] **Step 6: Commit the plan gate and router**

```powershell
git add src/game_visual_forge/routing/tilemap_architecture.py src/game_visual_forge/routing/__init__.py src/game_visual_forge/cli/planning.py src/game_visual_forge/cli/tilemap.py tests/test_tilemap_intake.py tests/test_tilemap_architecture_routing.py
git commit -m "feat: gate tilemap planning on confirmed intake"
```

---

### Task 3: Critical candidate preassembly report and agent review

**Files:**
- Create: `src/game_visual_forge/contracts/tilemap_asset_review.py`
- Create: `src/game_visual_forge/processing/tilemap_asset_preflight.py`
- Create: `tests/test_tilemap_asset_preflight.py`
- Modify: `src/game_visual_forge/contracts/__init__.py`
- Modify: `src/game_visual_forge/processing/__init__.py`

**Interfaces:**
- Produces: `CandidateAssetKind`, `PreassemblyReviewStatus`, `CandidateAsset`, `CriticalAssetCheck`, `TilemapCriticalAssetReport`, `PreassemblyAssetDecision`, `TilemapPreassemblyReview`.
- Produces: `preflight_tilemap_assets(repo_root, request, architecture, candidates, out_dir) -> TilemapCriticalAssetReport`.
- Produces: `record_preassembly_review(report, decisions, reviewed_at) -> TilemapPreassemblyReview`.
- Produces: `validate_preassembly_review(report, review) -> None`.

- [ ] **Step 1: Add failing candidate and review tests**

Use temporary PNGs created with Pillow. Cover exact dimensions, alpha, abnormal opaque backgrounds, placement bounds, bridge crop output, accepted review, rejected review, and hash invalidation:

```python
def test_changed_candidate_invalidates_accepted_review(self) -> None:
    report = self.preflight_valid_candidates()
    review = record_preassembly_review(report, self.accept_all(report), self.now)
    self.foundation.save(self.foundation_path)
    changed = self.preflight_valid_candidates()
    with self.assertRaisesRegex(ValueError, "candidate hashes"):
        validate_preassembly_review(changed, review)

def test_object_with_opaque_rectangular_background_fails(self) -> None:
    self.write_object(alpha=255, opaque_border=True)
    report = self.preflight()
    check = next(item for item in report.checks if item.check_id == "object-opaque-background")
    self.assertEqual(check.status, "failed")
```

Assert output files:

```python
self.assertTrue((self.out_dir / "critical-assets-report.json").is_file())
self.assertTrue((self.out_dir / "critical-assets-review-sheet.png").is_file())
self.assertTrue((self.out_dir / "focus" / "bridge-east-west-bridge.png").is_file())
```

- [ ] **Step 2: Run preassembly tests and confirm RED**

```powershell
python -m unittest tests.test_tilemap_asset_preflight -v
```

Expected: imports fail for the new contract and processing modules.

- [ ] **Step 3: Implement hash-bound records**

Store repo-relative normalized paths and 64-character lowercase SHA-256 values. Keep deterministic and visual status separate:

```python
@dataclass(frozen=True)
class TilemapCriticalAssetReport:
    schema_version: int
    request_fingerprint: str
    architecture_sha256: str
    candidates: tuple[CandidateAsset, ...]
    checks: tuple[CriticalAssetCheck, ...]
    deterministic_status: QualityStatus
    visual_status: QualityStatus
    review_sheet_path: str
    focus_paths: tuple[str, ...]
```

An agent review can be `accepted` only when deterministic status is `passed`, every candidate has an explicit accepted decision, and no decision is rejected. `validate_preassembly_review` compares request fingerprint, architecture hash, ordered candidate IDs, paths, and hashes.

- [ ] **Step 4: Implement deterministic checks and review sheet**

Use existing image helpers for loading. Add checks with stable IDs:

- `candidate-dimensions`
- `foundation-prompt`
- `foundation-visual-review-required`
- `object-alpha`
- `object-footprint-size`
- `object-edge-touch`
- `object-opaque-background`
- `object-doorway`
- `object-placement-bounds`
- `bridge-topology`
- `bridge-visual-review-required`

Render a neutral contact sheet with the foundation/atlas, bridge crops, and object images. Draw labels in the sheet margins only; never modify candidate pixels. Set `visual_status=needs_visual_review` until the agent review command accepts the sheet.

- [ ] **Step 5: Run focused contract and rendering tests**

```powershell
python -m unittest tests.test_tilemap_asset_preflight tests.test_tilemap_object_contract tests.test_tilemap_object_quality -v
```

Expected: PASS.

- [ ] **Step 6: Commit preassembly contracts and processing**

```powershell
git add src/game_visual_forge/contracts/tilemap_asset_review.py src/game_visual_forge/contracts/__init__.py src/game_visual_forge/processing/tilemap_asset_preflight.py src/game_visual_forge/processing/__init__.py tests/test_tilemap_asset_preflight.py
git commit -m "feat: add tilemap candidate asset preflight"
```

---

### Task 4: Preflight CLI, targeted review loop, and ingest enforcement

**Files:**
- Modify: `src/game_visual_forge/cli/main.py`
- Modify: `src/game_visual_forge/cli/tilemap.py`
- Modify: `src/game_visual_forge/contracts/tilemap_sources.py`
- Modify: `tests/test_tilemap_asset_preflight.py`
- Modify: `tests/test_tilemap_sources.py`

**Interfaces:**
- Produces CLI: `map tile preflight-assets`.
- Produces CLI: `map tile record-asset-review`.
- Adds: `run_tilemap_preflight_assets(...) -> dict[str, Any]`.
- Adds: `run_tilemap_record_asset_review(report_path, decisions_path, out_path, now) -> dict[str, Any]`.
- Changes: `run_tilemap_ingest(..., preassembly_review_path: Path | None = None, critical_assets_report_path: Path | None = None)`.
- Changes: `TileMapSourceSet.preassembly_review_path`, `preassembly_review_sha256`, `critical_assets_report_path`, and `critical_assets_report_sha256` as optional compatibility fields.

- [ ] **Step 1: Add failing CLI lifecycle tests**

Test launcher help and behavior:

```python
def test_two_gate_ingest_requires_accepted_preassembly_review(self) -> None:
    with self.assertRaisesRegex(ValueError, "accepted preassembly review"):
        run_tilemap_ingest(
            self.request_path, self.decision_path, None, self.atlas_args,
            self.repo_root, self.source_set_path, self.state_path, self.now,
            self.object_args, self.style_approval_path,
        )

def test_rejected_review_does_not_terminally_reject_job(self) -> None:
    result = run_tilemap_record_asset_review(self.report_path, self.rejected_decisions_path, self.review_path, self.now)
    self.assertEqual(result["status"], "rejected")
    self.assertNotEqual(load_job(self.state_path).status, JobStatus.REJECTED)
```

Test accepted review output is bound into `TileMapSourceSet`, and replacing one candidate makes ingest reject the old review.

- [ ] **Step 2: Run CLI lifecycle tests and confirm RED**

```powershell
python -m unittest tests.test_tilemap_asset_preflight tests.test_tilemap_sources -v
```

Expected: missing commands, missing source-set fields, and ingest currently accepting unreviewed candidates.

- [ ] **Step 3: Add parsers and command dispatch**

Add parsers under `map tile`:

```text
preflight-assets --request --architecture --atlas-page ... --object-asset ... --repo-root --out-dir
record-asset-review --report --decisions --out --now
```

`decisions` is a JSON object:

```json
{
  "schema_version": 1,
  "assets": [
    {"asset_id": "foundation", "status": "accepted", "reason_code": "visual-pass", "reason": "Continuous banks and bridge approaches"}
  ]
}
```

Do not add provider submission or image generation to these commands.

- [ ] **Step 4: Enforce accepted review during ingest**

For requests with `intake is not None`, require both report and review. Load the same candidate paths given to ingest, recompute hashes, and call `validate_preassembly_review`. Copy the report/review to stable run-relative paths before writing the source set.

Keep archived requests compatible:

```python
if request.intake is not None:
    if preassembly_review_path is None or critical_assets_report_path is None:
        raise ValueError("new two-gate tilemap ingest requires an accepted preassembly review")
    validate_preassembly_review(report, review)
```

Never transition the job to terminal rejection for an agent asset rejection. Only accepted review permits the existing `RUNNING` transition.

- [ ] **Step 5: Run CLI, source, and rejection tests**

```powershell
python -m unittest tests.test_tilemap_asset_preflight tests.test_tilemap_sources tests.test_tilemap_rejection -v
```

Expected: PASS.

- [ ] **Step 6: Commit CLI enforcement**

```powershell
git add src/game_visual_forge/cli/main.py src/game_visual_forge/cli/tilemap.py src/game_visual_forge/contracts/tilemap_sources.py tests/test_tilemap_asset_preflight.py tests/test_tilemap_sources.py
git commit -m "feat: require accepted assets before tilemap ingest"
```

---

### Task 5: Consolidated assembled review sheet and approval hash

**Files:**
- Create: `src/game_visual_forge/processing/tilemap_review_sheet.py`
- Create: `tests/test_tilemap_review_sheet.py`
- Modify: `src/game_visual_forge/processing/tilemap.py`
- Modify: `src/game_visual_forge/contracts/approval.py`
- Modify: `src/game_visual_forge/quality/tilemap.py`
- Modify: `src/game_visual_forge/cli/tilemap.py`
- Modify: `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapApprovalValidator.cs`

**Interfaces:**
- Produces: `render_assembled_review_sheet(staging: Path, request: TileMapRequest, result_paths: Mapping[str, str]) -> str` returning `assembled-review-sheet.png`.
- Changes: `TileMapProcessingResult.review_sheet_path: str`.
- Changes: `ASSEMBLED_APPROVAL_ROLES` to seven ordered roles with `review-sheet` first.
- Changes: Python and Unity exact-role validation.

- [ ] **Step 1: Add failing rendering and approval tests**

Create tests that process a small hybrid fixture and assert:

```python
self.assertEqual(result.review_sheet_path, "assembled-review-sheet.png")
sheet = Image.open(staging / result.review_sheet_path)
self.assertGreater(sheet.width, preview.width)
self.assertGreater(sheet.height, preview.height)
```

Test exact approval ordering:

```python
self.assertEqual(
    ASSEMBLED_APPROVAL_ROLES,
    ("review-sheet", "tilemap-preview", "gameplay-crop", "tilemap-placement", "tilemap-objects", "tilemap-collision", "asset-set"),
)
```

Test missing or changed review sheet hash blocks `run_tilemap_validate`.

- [ ] **Step 2: Run review-sheet tests and confirm RED**

```powershell
python -m unittest tests.test_tilemap_review_sheet -v
```

Expected: missing module/field and six-role approval tuple.

- [ ] **Step 3: Render the assembled sheet**

Use fixed panels derived from request dimensions, not hard-coded village sizes. Include:

- final preview
- gameplay crop
- collision preview
- each traversable bridge crop, padded by one cell and clipped to map bounds
- each object entrance crop, padded by one cell and clipped to map bounds

Render labels and collision legend in margins. Save RGBA PNG. Do not replace `tilemap-preview.png`.

- [ ] **Step 4: Bind the new role through validation and Unity preflight**

Update Python role tuples and expected hashes. Update `TilemapApprovalValidator.cs` expected assembled roles to:

```csharp
new[] { "review-sheet", "tilemap-preview", "gameplay-crop", "tilemap-placement", "tilemap-objects", "tilemap-collision", "asset-set" }
```

Ensure the Unity manifest contains and hashes the new artifact through the existing assembled approval record; do not add a third approval field.

- [ ] **Step 5: Run processing, approval, manifest, and focused Unity tests**

```powershell
python -m unittest tests.test_tilemap_review_sheet tests.test_tilemap_approvals tests.test_tilemap_manifest_integrity tests.test_unity_tilemap_integration -v
```

Then refresh Unity and run EditMode tests. Expected: Python PASS and Unity EditMode PASS with the updated fixture roles.

- [ ] **Step 6: Commit consolidated review**

```powershell
git add src/game_visual_forge/processing/tilemap_review_sheet.py src/game_visual_forge/processing/tilemap.py src/game_visual_forge/contracts/approval.py src/game_visual_forge/quality/tilemap.py src/game_visual_forge/cli/tilemap.py tests/test_tilemap_review_sheet.py integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapApprovalValidator.cs
git commit -m "feat: add assembled tilemap review sheet"
```

---

### Task 6: Unity post-placement scene acceptance

**Files:**
- Create: `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapSceneAcceptanceValidator.cs`
- Create after Unity refresh: `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapSceneAcceptanceValidator.cs.meta`
- Modify: `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleContracts.cs`
- Modify: `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleImporter.cs`
- Modify: `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapImportReportWriter.cs`
- Modify: `integrations/unity/com.game-visual-forge.tilemap/Tests/Editor/TilemapBundleImporterEditModeTests.cs`

**Interfaces:**
- Produces: `SceneAcceptanceResult` with `status`, `scene_path`, `root_count`, `tile_count`, `object_count`, `checks`, and `report_path`.
- Produces: `TilemapSceneAcceptanceValidator.ValidateAndWrite(...) -> SceneAcceptanceResult`.
- Changes: `ImportResult.scene_acceptance_report`, `ImportResult.scene_acceptance_status`.
- Changes: `UnityImportReport.scene_acceptance_report`, `UnityImportReport.scene_acceptance_status`.

- [ ] **Step 1: Add failing Unity EditMode acceptance tests**

Extend the fixture to contain one building with a doorway, terrain blockers, and a traversable bridge. Add tests:

```csharp
[Test]
public void ImportAndPlaceWritesPassingSceneAcceptanceReport()
{
    var result = TilemapBundleImporter.ImportBundle(CreateAcceptanceBundleFixture(), ImportMode.ImportAndPlace);
    Assert.That(result.scene_acceptance_status, Is.EqualTo("passed"));
    Assert.That(AssetDatabase.LoadAssetAtPath<TextAsset>(result.scene_acceptance_report), Is.Not.Null);
}

[Test]
public void SceneAcceptanceRejectsShiftedBuildingAndMisalignedCollider()
{
    var fixture = ImportAcceptanceFixture();
    fixture.Building.transform.localPosition += Vector3.left;
    Assert.Throws<InvalidOperationException>(() => fixture.Validate());
}

[Test]
public void SceneAcceptanceRejectsDuplicateRootAndBlockedDoorway()
{
    var fixture = ImportAcceptanceFixture();
    PrefabUtility.InstantiatePrefab(fixture.Prefab);
    fixture.AddDoorwayCollider();
    Assert.Throws<InvalidOperationException>(() => fixture.Validate());
}

[Test]
public void RepeatImportReplacesOwnedRootAndPreservesGeneratedGuids()
{
    var bundle = CreateAcceptanceBundleFixture();
    var first = TilemapBundleImporter.ImportBundle(bundle, ImportMode.ImportAndPlace);
    var prefabGuid = AssetDatabase.AssetPathToGUID(first.prefab_path);

    var second = TilemapBundleImporter.ImportBundle(bundle, ImportMode.ImportAndPlace);

    Assert.That(FindOwnedSceneRoots(bundle.request_id), Has.Count.EqualTo(1));
    Assert.That(AssetDatabase.AssetPathToGUID(second.prefab_path), Is.EqualTo(prefabGuid));
    Assert.That(second.scene_acceptance_status, Is.EqualTo("passed"));
}
```

- [ ] **Step 2: Refresh Unity and confirm RED**

Refresh scripts, wait until the editor is ready, then run package EditMode tests. Expected: compile failure because the validator/result fields do not exist.

- [ ] **Step 3: Add collision and acceptance contracts**

Add JSON records matching current emitted files:

```csharp
[Serializable] internal sealed class CollisionManifest
{
    public int schema_version;
    public BlockedCell[] blocked_cells;
    public TerrainBlockedCell[] terrain_blocked_cells;
    public CollisionEntrance[] entrances;
    public BridgeRuleData[] bridge_connectivity_rules;
}
```

Use top-left grid coordinates from collision/object manifests and bottom-left Unity cell coordinates from placement data explicitly. Reuse `TilemapObjectImporter.ResolvePlacementLocalPosition` and `ResolveCollisionCellLocalPosition`; do not duplicate their formulas.

- [ ] **Step 4: Implement validation and report writing**

Validate:

- one prefab-linked scene root
- expected Tile and object counts
- every object transform
- Sprite bounds inside expected world footprint/map bounds with `0.001f` tolerance
- every declared building collider center/size
- no collider for each entrance cell
- each terrain blocked cell references a collidable Tile
- each traversable bridge cell is absent from terrain blockers

Write JSON to `${generated_root}/Reports/unity-scene-acceptance.json`, import it synchronously, and store the path/status in both reports. Run only for `ImportAndPlace`; `AssetsOnly` writes status `not_run` and no acceptance path.

- [ ] **Step 5: Run full Unity tests**

Run all package EditMode tests, then all PlayMode tests. Expected: all pass, zero new console errors.

- [ ] **Step 6: Commit Unity acceptance**

```powershell
git add integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapSceneAcceptanceValidator.cs integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapSceneAcceptanceValidator.cs.meta integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleContracts.cs integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleImporter.cs integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapImportReportWriter.cs integrations/unity/com.game-visual-forge.tilemap/Tests/Editor/TilemapBundleImporterEditModeTests.cs
git commit -m "feat: validate placed Unity tilemap scenes"
```

---

### Task 7: Rewrite the map Skill around the enforced workflow

**Files:**
- Create: `tests/test_forge_skill_scope.py`
- Modify: `skills/forge-2d-map/SKILL.md`
- Modify: `skills/forge-2d-map/agents/openai.yaml`

**Interfaces:**
- Consumes: CLI commands and artifact names from Tasks 1-6.
- Produces: a self-contained positive recipe for future agents.
- Produces: positive repository contract asserting the intended three Skill directories.

- [ ] **Step 1: Add failing Skill behavior tests**

The real baseline failure already demonstrated that an agent can skip intake and generate immediately. Encode the required correction as deterministic Skill contracts:

```python
class ForgeSkillScopeTests(unittest.TestCase):
    def test_repository_contains_exactly_the_three_owned_skills(self) -> None:
        actual = {path.name for path in (ROOT / "skills").iterdir() if path.is_dir()}
        self.assertEqual(actual, {"forge-2d-map", "forge-2d-sprite", "forge-video-to-sprite"})

    def test_map_skill_requires_grouped_intake_before_generation(self) -> None:
        skill = self.skill_text()
        for required in ("needs_user_input", "needs_user_confirmation", "question_group_id", "requirements_confirmed"):
            self.assertIn(required, skill)

    def test_map_skill_keeps_two_user_gates_and_agent_asset_review(self) -> None:
        skill = self.skill_text()
        for required in ("style-sample", "assembled-map", "preassembly-review.json", "reviewer: agent", "assembled-review-sheet.png"):
            self.assertIn(required, skill)

    def test_map_skill_requires_unity_scene_acceptance(self) -> None:
        skill = self.skill_text()
        for required in ("unity-scene-acceptance.json", "isDirty=false", "orthographic top-down", "EditMode", "PlayMode"):
            self.assertIn(required, skill)
```

- [ ] **Step 2: Run Skill tests and confirm RED**

```powershell
python -m unittest tests.test_forge_skill_scope -v
```

Expected: missing workflow phrases and artifacts.

- [ ] **Step 3: Rewrite `SKILL.md` as a concise positive recipe**

Order the body as:

1. standalone scope and runtime-map principle
2. grouped intake gate and one-message question rule
3. architecture routing table
4. two user gates
5. style approval to candidate generation
6. preassembly agent review and targeted regeneration loop
7. ingest/process/assembled review sheet
8. publication/rejection rules
9. Unity import and scene acceptance completion checklist
10. coherent-foundation CLI example

State the interaction shape positively:

```text
Present one compact requirements card containing every unresolved question group, its recommended default, and its impact. After the user answers, present one canonical summary. Do not generate until `map tile plan` returns `planned`.
```

Do not add narrative history from the village run. Keep the Skill operational and under 500 lines.

- [ ] **Step 4: Align agent metadata**

Use:

```yaml
interface:
  display_name: "Forge 2D Map"
  short_description: "Build reviewed playable 2D maps with Unity parity"
  default_prompt: "Use $forge-2d-map to collect and confirm one grouped map brief, select the correct terrain architecture, preflight critical assets, assemble a playable map, obtain the two required user approvals, and verify engine placement."
```

- [ ] **Step 5: Run Skill and launcher tests**

```powershell
python -m unittest tests.test_forge_skill_scope tests.test_skill_contracts -v
python skills/forge-2d-map/scripts/run.py map tile --help
```

Expected: PASS and help lists `preflight-assets` and `record-asset-review`.

- [ ] **Step 6: Commit Skill documentation**

```powershell
git add skills/forge-2d-map/SKILL.md skills/forge-2d-map/agents/openai.yaml tests/test_forge_skill_scope.py
git commit -m "docs: enforce reviewed forge 2d map workflow"
```

---

### Task 8: End-to-end regression, artifact audit, and completion evidence

**Files:**
- Modify only if a discovered integration defect requires it: files from Tasks 1-7.
- Do not modify README or existing readme evidence as part of this task.

**Interfaces:**
- Consumes every public contract and CLI command introduced above.
- Produces final test evidence and a clean set of task commits.

- [ ] **Step 1: Run the focused Python workflow suite**

```powershell
python -m unittest tests.test_tilemap_intake tests.test_tilemap_architecture_routing tests.test_tilemap_asset_preflight tests.test_tilemap_review_sheet tests.test_forge_skill_scope -v
```

Expected: PASS.

- [ ] **Step 2: Run the full Python suite**

```powershell
python -m unittest discover -s tests -v
```

Expected: all tests pass. If a failure comes from a pre-existing dirty test file, inspect the diff before editing and preserve the existing changes.

- [ ] **Step 3: Audit workflow artifacts with a temporary fixture run**

Use a temporary directory outside tracked paths. Exercise:

1. incomplete plan -> `needs_user_input`, no job
2. complete unconfirmed plan -> `needs_user_confirmation`, no job
3. confirmed plan -> architecture, execution plan, and job
4. preflight candidates -> report and critical review sheet
5. accepted agent review -> hash-bound record
6. ingest -> bound source set
7. process -> assembled review sheet
8. assembled approval -> seven exact roles
9. validation -> published final bundle

Assert every JSON file parses and every declared SHA-256 matches its file.

- [ ] **Step 4: Refresh Unity and run both test modes**

Clear stale console entries, refresh/compile, run all EditMode tests, then all PlayMode tests. Read the console afterward. Expected: every test passes and zero new errors.

- [ ] **Step 5: Import a validated fixture twice and inspect scene acceptance**

Use `ImportAndPlace` twice on the same temporary validated fixture. Capture the generated Prefab, Tile, Sprite, and material GUIDs after the first import, then verify after the second import:

- one target root
- every captured generated asset GUID is unchanged
- `unity-scene-acceptance.json` status `passed`
- import report references that acceptance report
- scene saved and `isDirty=false`
- orthographic top-down screenshot is visually aligned with the assembled preview

If either import fails, stop mutation and inspect the console/report before attempting another import.

- [ ] **Step 6: Audit repository scope and worktree**

```powershell
Get-ChildItem skills -Directory | Select-Object -ExpandProperty Name
git status --short
git log -8 --oneline
```

Expected: exactly the three intended Skill directories; task commits present; unrelated pre-existing changes remain unstaged and preserved.

- [ ] **Step 7: Commit only integration fixes if Step 2-5 required them**

Stage exact files, run `git diff --cached --check`, and commit:

```powershell
git commit -m "fix: close forge 2d map workflow regressions"
```

Skip this commit when no integration fix was necessary.

---

## Final Verification Checklist

- [ ] `map tile plan` produces no job artifacts for missing or unconfirmed intake.
- [ ] Missing questions are grouped and returned together.
- [ ] A changed intake invalidates its confirmation hash.
- [ ] Fixed continuity-critical layouts select `coherent_foundation`.
- [ ] Reusable/procedural layouts select `demand_driven`.
- [ ] Candidate assets cannot be ingested without accepted hash-matching agent review.
- [ ] Candidate rejection allows targeted replacement without terminal run rejection.
- [ ] The assembled review sheet is user-facing and hash-bound.
- [ ] Exactly two user approval gates remain.
- [ ] Unity detects transform, bounds, collider, doorway, duplicate-root, terrain, and bridge mismatches.
- [ ] Repeated Unity import preserves one owned scene root and stable generated asset GUIDs.
- [ ] Scene acceptance report is present for import-and-place.
- [ ] Saved scene is clean and the orthographic screenshot matches the approved composition.
- [ ] Full Python, Unity EditMode, and Unity PlayMode suites pass.
- [ ] Only the intended task files were committed.
