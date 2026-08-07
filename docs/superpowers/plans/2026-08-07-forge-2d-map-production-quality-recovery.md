# Forge 2D Map Production Quality Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the rejected all-Tile village workflow with a guarded hybrid Tilemap/object pipeline, record the old run as rejected, and produce a new user-approved playable village in Unity.

**Architecture:** Keep repeatable terrain in Tilemaps and represent complete buildings and props as independently generated object assets with footprints, collision cells, doorway anchors, and Unity Prefabs. Add explicit rejection records, conditional road/bridge traversal policies, and two hash-bound user approval gates; publication and Unity import refuse rejected or unapproved runs.

**Tech Stack:** Python 3.11+, dataclasses, Pillow, `unittest`, Game Visual Forge CLI, built-in `image_gen`, Unity 2022.3, C# Editor API, Unity MCP.

## Global Constraints

- The approved design is `docs/superpowers/specs/2026-08-07-forge-2d-map-production-quality-recovery-design.md`; implementation must match it exactly.
- Preserve all existing dirty working-tree changes. Record `git status --short` before every staged commit; stage exact paths or separable hunks only.
- Use `apply_patch` for source edits. Do not use reset, checkout, recursive delete, or broad cleanup commands.
- Keep `outputs/spring-creek-village-20260803` as immutable visual failure evidence except for new rejection metadata and its job-state transition.
- Deactivate the rejected Unity scene root; do not delete its GameObject, Prefabs, textures, Tiles, or reports.
- Do not reuse any atlas, object image, placement, preview, approval, or screenshot from the rejected run in the replacement run.
- Buildings are complete object assets. Hybrid requests must reject building façades, doorway Tiles, and complete-building fragments in repeatable terrain atlases.
- Road connectivity is user-selected: `required`, declared `partial`, or `none`.
- Water is non-walkable. Bridge connectivity and minimum corridor width apply only when a bridge is declared `traversable=true`.
- The only user visual approval gates are `style-sample` and `assembled-map`. Agent visual judgment cannot create or imply either approval.
- Any artifact or placement hash change invalidates its approval.
- Do not install or upgrade Unity packages. Work only in the active `I:/UnityProject/2DMirrorDemo` scene.
- Generated files under `outputs/` remain ignored and must not be forced into Git.

---

## Task 1: Add terminal rejected job state and rejection records

**Files:**

- Create: `src/game_visual_forge/contracts/rejection.py`
- Modify: `src/game_visual_forge/contracts/job.py`
- Modify: `src/game_visual_forge/contracts/__init__.py`
- Modify: `src/game_visual_forge/jobs/transitions.py`
- Modify: `src/game_visual_forge/cli/tilemap.py`
- Modify: `src/game_visual_forge/cli/main.py`
- Test: `tests/test_job_state.py`
- Create: `tests/test_tilemap_rejection.py`

**Interfaces:**

- Produces `RejectedArtifact(path: str, sha256: str)` and `JobRejectionRecord(schema_version, run_id, asset_id, reason_codes, user_reason, rejected_at, artifacts)`.
- Produces `run_tilemap_reject(state_path, run_root, out_path, reason_codes, user_reason, now) -> dict[str, Any]`.
- Adds terminal `JobStatus.REJECTED` and permits every non-rejected state, including `COMPLETED`, to transition to it.

- [ ] **Step 1: Write rejection contract and transition tests**

```python
def test_completed_job_can_be_rejected_but_not_resumed(self) -> None:
    completed = replace(self.make_state(), status=JobStatus.COMPLETED)
    rejected = transition_job(completed, JobStatus.REJECTED, now="2026-08-07T03:00:00Z")
    self.assertEqual(rejected.status, JobStatus.REJECTED)
    with self.assertRaisesRegex(ValueError, "illegal transition"):
        transition_job(rejected, JobStatus.READY, now="2026-08-07T03:01:00Z")

def test_rejection_record_round_trips_and_rejects_unsafe_paths(self) -> None:
    record = JobRejectionRecord(
        1, "spring-creek-village-20260803", "spring-creek-village",
        ("unusable-visual-composition",),
        "Buildings were repeated façade mosaics rather than usable objects.",
        "2026-08-07T03:00:00Z",
        (RejectedArtifact("final/tilemap-preview.png", "a" * 64),),
    )
    self.assertEqual(JobRejectionRecord.from_dict(record.to_dict()), record)
    with self.assertRaises(ValueError):
        RejectedArtifact("../escape.png", "a" * 64)
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `python -m unittest tests.test_job_state tests.test_tilemap_rejection -v`

Expected: FAIL because `REJECTED`, `RejectedArtifact`, and `JobRejectionRecord` do not exist.

- [ ] **Step 3: Implement immutable rejection contracts**

```python
@dataclass(frozen=True)
class RejectedArtifact:
    path: str
    sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", normalize_repo_relative_path(self.path, field_name="rejected artifact path"))
        _require_sha256(self.sha256, "sha256")

@dataclass(frozen=True)
class JobRejectionRecord:
    schema_version: int
    run_id: str
    asset_id: str
    reason_codes: tuple[str, ...]
    user_reason: str
    rejected_at: str
    artifacts: tuple[RejectedArtifact, ...]
```

Add `REJECTED = "rejected"` to `JobStatus`. In `LEGAL_TRANSITIONS`, add `JobStatus.REJECTED` to every non-rejected state's target set and add `JobStatus.REJECTED: set()`.

- [ ] **Step 4: Write a failing CLI rejection test**

```python
def test_reject_hashes_final_tree_and_changes_completed_state(self) -> None:
    result = run_tilemap_reject(
        state_path, run_root, run_root / "rejection.json",
        ("unusable-visual-composition",), "User rejected the assembled map.",
        "2026-08-07T03:00:00Z",
    )
    self.assertEqual(result["status"], "rejected")
    self.assertEqual(load_job(state_path).status, JobStatus.REJECTED)
    record = JobRejectionRecord.from_dict(load_json(run_root / "rejection.json"))
    self.assertEqual({item.path for item in record.artifacts}, {"final/tilemap-preview.png", "final/unity-tilemap.json"})
```

- [ ] **Step 5: Implement `run_tilemap_reject` and expose `map tile reject`**

```python
def run_tilemap_reject(state_path, run_root, out_path, reason_codes, user_reason, now):
    state = load_job(state_path)
    artifacts = tuple(
        RejectedArtifact(path.relative_to(run_root).as_posix(), sha256_file(path))
        for path in sorted((run_root / "final").rglob("*")) if path.is_file()
    )
    record = JobRejectionRecord(1, run_root.name, state.asset_id, tuple(reason_codes), user_reason, now, artifacts)
    dump_json(out_path, record.to_dict())
    save_job(state_path, transition_job(state, JobStatus.REJECTED, now=now, error_code="USER_REJECTED"))
    return {"schema_version": 1, "status": "rejected", "rejection_path": str(out_path)}
```

Parser arguments are `--state`, `--run-root`, `--out`, repeated `--reason-code`, `--reason`, and `--now`.

- [ ] **Step 6: Run rejection and legacy job tests**

Run: `python -m unittest tests.test_job_state tests.test_tilemap_rejection tests.test_cli_dry_run -v`

Expected: PASS; all previous job transitions remain valid.

- [ ] **Step 7: Commit reviewed rejection files only**

```powershell
git status --short
git add -p -- src/game_visual_forge/contracts/job.py src/game_visual_forge/contracts/__init__.py src/game_visual_forge/jobs/transitions.py src/game_visual_forge/cli/tilemap.py src/game_visual_forge/cli/main.py tests/test_job_state.py
git add -- src/game_visual_forge/contracts/rejection.py tests/test_tilemap_rejection.py
git diff --cached --check
git diff --cached --name-only
git commit -m "feat: record rejected forge runs"
```

If a dirty-file hunk cannot be separated safely, leave it unstaged and record that fact; never include unrelated bridge or README changes to satisfy this step.

## Task 2: Define hybrid terrain/object map contracts

**Files:**

- Create: `src/game_visual_forge/contracts/tilemap_objects.py`
- Modify: `src/game_visual_forge/contracts/tilemap.py`
- Modify: `src/game_visual_forge/contracts/tilemap_sources.py`
- Modify: `src/game_visual_forge/contracts/__init__.py`
- Create: `tests/test_tilemap_object_contract.py`
- Modify: `tests/test_tilemap_contract.py`
- Modify: `tests/test_tilemap_sources.py`

**Interfaces:**

- Produces `GridCell`, `GridRect`, `TileObjectKind`, `EntranceConnectionTarget`, `TileObjectAssetDefinition`, `TileObjectPlacement`, and `TileObjectEntrance`.
- Produces `RoadConnectivityPolicy`, `RoadConnectionRequirement`, and `TileMapApprovalWorkflow`.
- Extends `BridgeConnectivityRule` with `traversable: bool` and `minimum_traversal_width: int | None`.
- Extends `TileMapSourceSet` with `objects: tuple[TileObjectSourceRecord, ...]` and parser `parse_object_asset_argument(value) -> tuple[str, Path]`.

- [ ] **Step 1: Write failing object contract tests**

```python
def test_complete_building_object_round_trips(self) -> None:
    asset = TileObjectAssetDefinition(
        "inn", TileObjectKind.BUILDING, "prompt", 192, 160, 32,
        16, 16, GridRect(0, 0, 6, 5),
        tuple(GridCell(x, y) for y in range(5) for x in range(6) if (x, y) != (3, 4)),
        GridCell(3, 4), 1, 0,
    )
    placement = TileObjectPlacement("inn-instance", "inn", 3, 2, 100)
    entrance = TileObjectEntrance("inn-entrance", "inn-instance", EntranceConnectionTarget.ROAD, "interiors/inn", "entry")
    self.assertEqual(TileObjectAssetDefinition.from_dict(asset.to_dict()), asset)
    self.assertEqual(TileObjectPlacement.from_dict(placement.to_dict()), placement)
    self.assertEqual(TileObjectEntrance.from_dict(entrance.to_dict()), entrance)

def test_building_requires_doorway_outside_collision(self) -> None:
    with self.assertRaisesRegex(ValueError, "doorway"):
        make_object_asset(kind=TileObjectKind.BUILDING, doorway=GridCell(2, 3), collision_cells=(GridCell(2, 3),))
```

`max_instances=1` and `max_adjacent=0` are the final two positional values in the first example.

- [ ] **Step 2: Implement focused object types in a new module**

```python
class TileObjectKind(StrEnum):
    BUILDING = "building"
    PROP = "prop"

class EntranceConnectionTarget(StrEnum):
    WALKABLE = "walkable"
    ROAD = "road"

class RoadConnectivityPolicy(StrEnum):
    REQUIRED = "required"
    PARTIAL = "partial"
    NONE = "none"

class TileMapApprovalWorkflow(StrEnum):
    LEGACY_VISUAL = "legacy_visual"
    TWO_GATE = "two_gate"

@dataclass(frozen=True)
class GridCell:
    x: int
    y: int

@dataclass(frozen=True)
class GridRect:
    x: int
    y: int
    width: int
    height: int

@dataclass(frozen=True)
class RoadConnectionRequirement:
    rule_id: str
    start: GridCell
    end: GridCell

@dataclass(frozen=True)
class TileObjectAssetDefinition:
    asset_id: str
    kind: TileObjectKind
    prompt: str
    pixel_width: int
    pixel_height: int
    pixels_per_unit: int
    anchor_x: int
    anchor_y: int
    footprint: GridRect
    collision_cells: tuple[GridCell, ...]
    doorway_cell: GridCell | None
    max_instances: int
    max_adjacent: int

@dataclass(frozen=True)
class TileObjectPlacement:
    instance_id: str
    asset_id: str
    x: int
    y: int
    sorting_order: int

@dataclass(frozen=True)
class TileObjectEntrance:
    entrance_id: str
    instance_id: str
    connection_target: EntranceConnectionTarget
    target_scene_id: str
    target_spawn_id: str
```

`TileObjectPlacement.x/y` is the top-left map-grid origin of the asset footprint. Validate all slugs, non-negative cells, positive rectangle/dimensions, anchor bounds, footprint-relative collision cells, building doorway presence, doorway exclusion from collision, unique cells, and non-negative repeat limits. `RoadConnectionRequirement` endpoints use top-left map coordinates.

- [ ] **Step 3: Add road policy and conditional bridge tests**

```python
def test_road_policy_requires_only_declared_data(self) -> None:
    self.assertEqual(make_request(road_connectivity_policy=RoadConnectivityPolicy.NONE).road_connection_requirements, ())
    with self.assertRaisesRegex(ValueError, "partial"):
        make_request(road_connectivity_policy=RoadConnectivityPolicy.PARTIAL, road_connection_requirements=())

def test_non_traversable_bridge_ignores_width(self) -> None:
    rule = BridgeConnectivityRule("ford-view", BridgeOrientation.HORIZONTAL, "ground", 2, 2, 4, 2, traversable=False, minimum_traversal_width=None)
    self.assertFalse(rule.traversable)

def test_traversable_bridge_requires_positive_width(self) -> None:
    with self.assertRaisesRegex(ValueError, "minimum_traversal_width"):
        BridgeConnectivityRule("bridge", BridgeOrientation.HORIZONTAL, "ground", 2, 2, 4, 2, traversable=True, minimum_traversal_width=0)
```

- [ ] **Step 4: Extend `TileMapRequest` while preserving legacy payloads**

Add fields with backward-compatible defaults:

```python
road_connectivity_policy: RoadConnectivityPolicy = RoadConnectivityPolicy.NONE
road_layer_ids: tuple[str, ...] = ()
road_connection_requirements: tuple[RoadConnectionRequirement, ...] = ()
object_assets: tuple[TileObjectAssetDefinition, ...] = ()
object_placements: tuple[TileObjectPlacement, ...] = ()
object_entrances: tuple[TileObjectEntrance, ...] = ()
approval_workflow: TileMapApprovalWorkflow = TileMapApprovalWorkflow.LEGACY_VISUAL
gameplay_crop: GridRect | None = None
```

Add `TileSetProfile.DEMAND_DRIVEN = "demand_driven"`. Demand-driven pages may use 1-4 columns and 1-4 rows and `max_tile_count` may be any positive value not exceeding total declared atlas capacity. For `TWO_GATE` requests, reject `TileSemanticRole.PROP` and `DOORWAY` in terrain Tiles, require a gameplay crop, and require all building entrances to use object contracts. Missing new keys continue to parse as the legacy model.

- [ ] **Step 5: Extend source-set ingestion contracts**

```python
@dataclass(frozen=True)
class TileObjectSourceRecord:
    asset_id: str
    image: RawImageRecord

@dataclass(frozen=True)
class TileMapSourceSet:
    schema_version: int
    pages: tuple[TileAtlasSourceRecord, ...]
    objects: tuple[TileObjectSourceRecord, ...] = ()
```

`load_tilemap_source_set` requires object source IDs to exactly match request object-asset IDs in request order and all page/object fingerprints to be identical.

- [ ] **Step 6: Run contract and source tests**

Run: `python -m unittest tests.test_tilemap_object_contract tests.test_tilemap_contract tests.test_tilemap_sources -v`

Expected: PASS, including all legacy request/source fixtures.

- [ ] **Step 7: Commit the isolated hybrid contracts**

```powershell
git add -- src/game_visual_forge/contracts/tilemap_objects.py tests/test_tilemap_object_contract.py
git add -p -- src/game_visual_forge/contracts/tilemap.py src/game_visual_forge/contracts/tilemap_sources.py src/game_visual_forge/contracts/__init__.py tests/test_tilemap_contract.py tests/test_tilemap_sources.py
git diff --cached --check
git commit -m "feat: model hybrid tilemap objects"
```

## Task 3: Ingest object images and compose runtime-asset previews

**Files:**

- Create: `src/game_visual_forge/processing/tilemap_objects.py`
- Modify: `src/game_visual_forge/cli/tilemap.py`
- Modify: `src/game_visual_forge/cli/main.py`
- Modify: `src/game_visual_forge/processing/tilemap.py`
- Modify: `tests/test_tilemap_processing.py`
- Create: `tests/test_tilemap_object_processing.py`

**Interfaces:**

- Consumes Task 2 object definitions and source records.
- Produces `validate_object_image`, `compose_object_layer`, `build_object_manifest`, and `build_collision_manifest`.
- Extends `TileMapProcessingResult` with `objects_path`, `collision_path`, `asset_set_path`, `gameplay_crop_path`, and `collision_preview_path`.

- [ ] **Step 1: Write failing ingest and preview tests**

```python
def test_ingest_requires_every_declared_object_once(self) -> None:
    with self.assertRaisesRegex(ValueError, "object asset arguments"):
        run_tilemap_ingest(request_path, decision_path, None, atlas_args, ["inn=inn.png"], root, out, state, NOW)

def test_process_composes_complete_building_over_terrain(self) -> None:
    result = process_tilemap(root, hybrid_request(), hybrid_source_set(root), root / "outputs/map/final")
    self.assertEqual(result.objects_path, "tilemap-objects.json")
    self.assertEqual(result.collision_path, "tilemap-collision.json")
    self.assertEqual(result.asset_set_path, "asset-set.json")
    self.assertEqual(result.gameplay_crop_path, "tilemap-gameplay-crop.png")
    self.assertEqual(result.collision_preview_path, "tilemap-collision-preview.png")
    with Image.open(root / result.staging_dir / result.preview_path) as image:
        self.assertEqual(image.getpixel((building_center_x, building_center_y)), BUILDING_COLOR)
```

- [ ] **Step 2: Add repeated `--object-asset asset-id=path` ingestion**

Extend the CLI signature:

```python
def run_tilemap_ingest(
    request_path, decision_path, image_path, atlas_page_arguments,
    object_asset_arguments, repo_root, out_path, state_path, now,
) -> dict[str, Any]:
```

Ingest every object image with the request fingerprint and emit `TileMapSourceSet(1, pages, objects)`. Legacy calls pass an empty list.

- [ ] **Step 3: Implement object-image validation and preview composition**

```python
def validate_object_image(image, definition):
    if image.size != (definition.pixel_width, definition.pixel_height):
        raise ForgeError(ErrorCode.INVALID_REQUEST, "object image dimensions do not match definition", recoverable=True)
    alpha = image.getchannel("A")
    if alpha.getextrema() == (255, 255):
        raise ForgeError(ErrorCode.INVALID_REQUEST, "object image must contain transparency", recoverable=True)

def compose_object_layer(preview, object_images, request):
    for placement in sorted(request.object_placements, key=lambda item: item.sorting_order):
        definition = definitions[placement.asset_id]
        x = placement.x * request.tile_width - definition.anchor_x
        y = placement.y * request.tile_height - definition.anchor_y
        preview.alpha_composite(object_images[placement.asset_id], (x, y))
```

`build_object_manifest` writes asset definitions, copied paths `objects/<asset-id>.png`, and placements. `build_collision_manifest` writes top-left grid blockers, entrances derived from placement origin plus asset doorway, road policy, and bridge policy.

- [ ] **Step 4: Emit asset-set hashes and gameplay crop**

`asset-set.json` contains sorted SHA-256 records for every terrain atlas and object image. Crop the final runtime-composed preview with `request.gameplay_crop` and save `tilemap-gameplay-crop.png`; do not resize it. Render `tilemap-collision-preview.png` as separate QA evidence using translucent blockers, walkable cells, road requirements, entrances, and traversable-bridge corridors over a copy of the runtime preview; never bake the overlay into `tilemap-preview.png`.

The Unity manifest adds:

```json
{
  "objects": "tilemap-objects.json",
  "collision": "tilemap-collision.json",
  "asset_set": "asset-set.json",
  "gameplay_crop": "tilemap-gameplay-crop.png",
  "collision_preview": "tilemap-collision-preview.png"
}
```

- [ ] **Step 5: Run processing tests**

Run: `python -m unittest tests.test_tilemap_processing tests.test_tilemap_object_processing -v`

Expected: PASS; previews are demonstrably assembled from copied runtime object images.

- [ ] **Step 6: Commit processing changes**

```powershell
git add -- src/game_visual_forge/processing/tilemap_objects.py tests/test_tilemap_object_processing.py
git add -p -- src/game_visual_forge/cli/tilemap.py src/game_visual_forge/cli/main.py src/game_visual_forge/processing/tilemap.py tests/test_tilemap_processing.py
git diff --cached --check
git commit -m "feat: process hybrid tilemap assets"
```

## Task 4: Enforce object, road, water, and conditional bridge quality

**Files:**

- Create: `src/game_visual_forge/quality/tilemap_objects.py`
- Modify: `src/game_visual_forge/processing/tilemap_quality.py`
- Modify: `src/game_visual_forge/quality/tilemap.py`
- Create: `tests/test_tilemap_object_quality.py`
- Modify: `tests/test_tilemap_quality_metrics.py`
- Modify: `tests/test_tilemap_manifest_integrity.py`

**Interfaces:**

- Produces `ObjectQualityMetrics` and `analyze_object_quality(request, object_images) -> ObjectQualityMetrics`.
- Produces `analyze_traversal_quality(request) -> TraversalQualityMetrics`.
- Quality checks are `object-alpha`, `building-silhouette`, `object-overlap`, `object-density`, `entrance-reachability`, `road-connectivity`, `water-collision`, and `bridge-traversal`.

- [ ] **Step 1: Write failing layout-quality tests**

```python
def test_overlapping_building_footprints_fail(self) -> None:
    metrics = analyze_object_quality(overlapping_request(), object_images())
    self.assertEqual(metrics.overlapping_instances, (("inn-instance", "shop-instance"),))

def test_entrance_must_reach_requested_target(self) -> None:
    metrics = analyze_traversal_quality(blocked_entrance_request())
    self.assertEqual(metrics.unreachable_entrance_ids, ("inn-entrance",))

def test_none_road_policy_does_not_require_global_connection(self) -> None:
    metrics = analyze_traversal_quality(disconnected_roads(RoadConnectivityPolicy.NONE))
    self.assertEqual(metrics.invalid_road_connections, ())

def test_partial_road_policy_checks_only_declared_pairs(self) -> None:
    metrics = analyze_traversal_quality(disconnected_roads(RoadConnectivityPolicy.PARTIAL))
    self.assertEqual(metrics.invalid_road_connections, ("west-to-plaza",))
```

- [ ] **Step 2: Implement object geometry and alpha checks**

For each building, compute alpha connected components using 4-neighbor traversal. Require the largest component to contain at least 90% of non-transparent pixels. Record all size mismatches, missing transparency, low primary-component ratios, exact duplicate building hashes, overlapping footprints/collision cells, over-limit instance counts, and adjacent repeat runs exceeding `max_adjacent`.

```python
primary_ratio = max(component_sizes, default=0) / max(1, sum(component_sizes))
if definition.kind is TileObjectKind.BUILDING and primary_ratio < 0.90:
    disconnected_building_ids.add(definition.asset_id)
```

- [ ] **Step 3: Implement walkability and policy-aware BFS**

Build a top-left boolean walkability grid from Tile collider roles and object collision cells. WATER cells are blocked. Object doorway cells are cleared after collision composition.

```python
if request.road_connectivity_policy is RoadConnectivityPolicy.REQUIRED:
    invalid_roads = () if one_component(all_road_cells) else ("all-primary-roads",)
elif request.road_connectivity_policy is RoadConnectivityPolicy.PARTIAL:
    invalid_roads = tuple(rule.rule_id for rule in request.road_connection_requirements if not reachable(rule.start, rule.end, road_cells))
else:
    invalid_roads = ()
```

Entrance reachability uses the entrance's `connection_target`: ROAD searches for any declared road cell; WALKABLE requires at least one reachable non-colliding neighbor.

- [ ] **Step 4: Make bridge validation conditional and width-aware**

Skip every bridge traversal check for `traversable=false`. For a horizontal traversable bridge, count contiguous parallel BRIDGE rows spanning the declared start/end; for a vertical bridge, count contiguous parallel columns. Require at least `minimum_traversal_width`. Check non-colliding deck cells, road approaches, and reachability between approaches.

```python
for rule in request.bridge_connectivity_rules:
    if not rule.traversable:
        continue
    width = contiguous_parallel_bridge_width(rule, request)
    if width < rule.minimum_traversal_width:
        failures.append(InvalidBridgeConnectivity(..., failure_kind="minimum-width"))
```

- [ ] **Step 5: Wire checks into publication quality**

Hybrid requests fail deterministically for any object, overlap, density, entrance, water, road-policy, or traversable-bridge failure. Add object/collision/asset-set/gameplay-crop artifacts to `_paths`, hash validation, and `asset-manifest.json` roles.

- [ ] **Step 6: Run focused quality and integrity tests**

Run: `python -m unittest tests.test_tilemap_object_quality tests.test_tilemap_quality_metrics tests.test_tilemap_manifest_integrity -v`

Expected: PASS; legacy bridge behavior remains traversable with width 1.

- [ ] **Step 7: Commit quality gates**

```powershell
git add -- src/game_visual_forge/quality/tilemap_objects.py tests/test_tilemap_object_quality.py
git add -p -- src/game_visual_forge/processing/tilemap_quality.py src/game_visual_forge/quality/tilemap.py tests/test_tilemap_quality_metrics.py tests/test_tilemap_manifest_integrity.py
git diff --cached --check
git commit -m "feat: gate playable hybrid tilemaps"
```

## Task 5: Replace self-authored visual review with two hash-bound user approvals

**Files:**

- Create: `src/game_visual_forge/contracts/approval.py`
- Modify: `src/game_visual_forge/contracts/__init__.py`
- Modify: `src/game_visual_forge/quality/tilemap.py`
- Modify: `src/game_visual_forge/cli/tilemap.py`
- Modify: `src/game_visual_forge/cli/main.py`
- Create: `tests/test_tilemap_approvals.py`
- Modify: `tests/test_tilemap_manifest_integrity.py`

**Interfaces:**

- Produces `TilemapApprovalGate`, `ApprovalStatus`, `ApprovalArtifact`, and `UserApprovalRecord`.
- Produces `record_user_approval(gate, artifact_paths, repo_root, approved_at) -> UserApprovalRecord`.
- Produces `validate_user_approval(record, gate, expected_hashes) -> None`.
- Adds CLI `map tile record-approval` and new validate arguments `--style-approval`, `--assembled-approval`.

- [ ] **Step 1: Write failing approval contract tests**

```python
def test_user_approval_round_trips(self) -> None:
    record = UserApprovalRecord(
        1, TilemapApprovalGate.STYLE_SAMPLE, ApprovalStatus.APPROVED,
        "user", "2026-08-07T04:00:00Z",
        (ApprovalArtifact("style-sample", "source/style-sample.png", "a" * 64),),
    )
    self.assertEqual(UserApprovalRecord.from_dict(record.to_dict()), record)

def test_agent_reviewer_is_rejected(self) -> None:
    with self.assertRaisesRegex(ValueError, "reviewer"):
        replace(valid_approval(), reviewer="agent")

def test_changed_preview_invalidates_assembled_approval(self) -> None:
    with self.assertRaisesRegex(ValueError, "hash"):
        validate_user_approval(assembled_approval(), TilemapApprovalGate.ASSEMBLED_MAP, {"tilemap-preview": "b" * 64})
```

- [ ] **Step 2: Implement the approval types and hash validator**

```python
class TilemapApprovalGate(StrEnum):
    STYLE_SAMPLE = "style-sample"
    ASSEMBLED_MAP = "assembled-map"

class ApprovalStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"

@dataclass(frozen=True)
class UserApprovalRecord:
    schema_version: int
    gate: TilemapApprovalGate
    status: ApprovalStatus
    reviewer: str
    approved_at: str
    artifacts: tuple[ApprovalArtifact, ...]
```

Require `reviewer == "user"`, unique exact artifact roles, UTC timestamps, safe paths, and SHA-256 values.

- [ ] **Step 3: Add `record-approval` CLI tests and implementation**

CLI usage:

```powershell
python skills/forge-2d-map/scripts/run.py map tile record-approval --gate style-sample --artifact style-sample=outputs/new/source/style-sample.png --artifact art-direction=outputs/new/source/art-direction.json --out outputs/new/source/style-approval.json --now 2026-08-07T04:00:00Z
```

`--artifact` accepts `role=path`, computes the current hash, writes an approved record with reviewer `user`, and refuses duplicate roles. This command may be run only after an explicit user approval response; the Skill enforces that conversational precondition.

- [ ] **Step 4: Require exact gate artifacts for hybrid validation**

Style approval roles are exactly `style-sample` and `art-direction`. Assembled approval roles are exactly:

```python
ASSEMBLED_APPROVAL_ROLES = (
    "tilemap-preview", "gameplay-crop", "tilemap-placement",
    "tilemap-objects", "tilemap-collision", "asset-set",
)
```

For `TWO_GATE`, reject `--visual-review`, require both approval paths, rehash every artifact, copy the records into staging, add their hashes to `unity-tilemap.json`, and mark the quality report visual status passed only when both records validate. Legacy requests retain the existing visual-review path.

- [ ] **Step 5: Require style approval before hybrid ingest**

Add `--style-approval` to `map tile ingest` and a matching optional parameter to `run_tilemap_ingest`. For `TWO_GATE`, it is required: load the record, require the `style-sample` gate and exact two roles, rehash both referenced files relative to the repository, and append the approval record path to `JobState.artifact_paths`. Legacy requests reject the flag to avoid ambiguous mixed workflows.

```python
if request.approval_workflow is TileMapApprovalWorkflow.TWO_GATE:
    if style_approval_path is None:
        raise ValueError("two-gate tilemap ingest requires --style-approval")
    validate_user_approval_files(load_json(style_approval_path), TilemapApprovalGate.STYLE_SAMPLE, repo_root)
```

- [ ] **Step 6: Block rejected runs before validation**

At the start of `run_tilemap_validate`, resolve the run root from `final_dir.parent`; if `run_root/rejection.json` exists, raise `ValueError("rejected tilemap runs cannot be validated or published")` before writing any staging report.

- [ ] **Step 7: Run approval/publication tests**

Run: `python -m unittest tests.test_tilemap_approvals tests.test_tilemap_manifest_integrity -v`

Expected: missing, stale, agent-authored, rejected, extra-role, and hash-mismatched approvals all block publication; exact approvals publish.

- [ ] **Step 8: Commit approval changes**

```powershell
git add -- src/game_visual_forge/contracts/approval.py tests/test_tilemap_approvals.py
git add -p -- src/game_visual_forge/contracts/__init__.py src/game_visual_forge/quality/tilemap.py src/game_visual_forge/cli/tilemap.py src/game_visual_forge/cli/main.py tests/test_tilemap_manifest_integrity.py
git diff --cached --check
git commit -m "feat: require user-approved tilemap artifacts"
```

## Task 6: Import hybrid objects and enforce approvals in Unity

**Files:**

- Modify: `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleContracts.cs`
- Modify: `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleImporter.cs`
- Create: `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapObjectImporter.cs`
- Create: `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapApprovalValidator.cs`
- Modify: `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapImportReportWriter.cs`
- Modify: `integrations/unity/com.game-visual-forge.tilemap/Tests/Editor/TilemapBundleImporterEditModeTests.cs`
- Modify: `tests/test_unity_tilemap_integration.py`

**Interfaces:**

- `TilemapApprovalValidator.RequireApprovedBundle(string manifestPath, BundleManifest manifest)` throws before importing rejected/unapproved bundles.
- `TilemapObjectImporter.ImportObjects(string bundleRoot, string generatedRoot, ObjectManifest manifest, int mapHeight, float cellWidth, float cellHeight)` returns object Prefab paths and a populated `Buildings`/`Props` hierarchy.
- Import results/reports expose approval, object-manifest, collision, and object-prefab asset paths.

- [ ] **Step 1: Add failing static and Editor tests**

```csharp
[Test]
public void ImportAndPlaceCreatesBuildingAndPropRoots()
{
    var result = TilemapBundleImporter.ImportBundle(CreateApprovedHybridFixture(), ImportMode.ImportAndPlace);
    var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(result.tilemap_prefab);
    Assert.That(prefab.transform.Find("Buildings"), Is.Not.Null);
    Assert.That(prefab.transform.Find("Props"), Is.Not.Null);
    Assert.That(prefab.transform.Find("Buildings/inn-instance"), Is.Not.Null);
    Assert.That(prefab.transform.Find("Buildings/inn-instance").GetComponentInChildren<BoxCollider2D>(), Is.Not.Null);
}

[Test]
public void ImportRejectsRejectedOrUnapprovedBundle()
{
    Assert.Throws<InvalidOperationException>(() => TilemapBundleImporter.ImportBundle(CreateRejectedHybridFixture()));
    Assert.Throws<InvalidOperationException>(() => TilemapBundleImporter.ImportBundle(CreateUnapprovedHybridFixture()));
}
```

- [ ] **Step 2: Extend C# manifest DTOs**

Add serializable DTOs for `ObjectManifest`, object assets, object placements, footprint/collision cells, and approval fields:

```csharp
internal sealed class BundleManifest
{
    // existing fields
    public string objects;
    public string collision;
    public string asset_set;
    public string style_approval;
    public string style_approval_sha256;
    public string assembled_approval;
    public string assembled_approval_sha256;
}
```

- [ ] **Step 3: Implement approval/rejection preflight**

```csharp
internal static void RequireApprovedBundle(string manifestPath, BundleManifest manifest)
{
    var bundle = Path.GetDirectoryName(manifestPath);
    var runRoot = Directory.GetParent(bundle)?.FullName;
    if (runRoot != null && File.Exists(Path.Combine(runRoot, "rejection.json")))
        throw new InvalidOperationException("Rejected Game Visual Forge bundles cannot be imported.");
    RequireHash(bundle, manifest.style_approval, manifest.style_approval_sha256);
    RequireHash(bundle, manifest.assembled_approval, manifest.assembled_approval_sha256);
}
```

Call this before creating folders, copying assets, or modifying the scene.

- [ ] **Step 4: Implement object Sprite/Prefab import**

For each object asset, copy the PNG with `.meta` preservation, configure `TextureImporter` as single Sprite, point filtering, declared PPU, and normalized pivot derived from top-left `anchor_x/anchor_y`. Create or update one object Prefab with `SpriteRenderer`; create collider child objects for declared collision cells. Build `Buildings` and `Props` under the map Prefab and place instances using request grid coordinates converted once to Unity bottom-left coordinates.

```csharp
var pivot = new Vector2(asset.anchor_x / (float)asset.pixel_width, 1f - asset.anchor_y / (float)asset.pixel_height);
importer.spritePivot = pivot;
instance.transform.localPosition = new Vector3(placement.x * cellWidth, (mapHeight - placement.y) * cellHeight, 0f);
```

- [ ] **Step 5: Report hybrid resources and preserve idempotency**

Include object textures, object Prefabs, object/collision TextAssets, and approval TextAssets in GUID snapshots. Repeat import must return `had_existing_assets=true`, `resource_guids_stable=true`, `scene_action=updated`, and exactly one scene root.

- [ ] **Step 6: Run static and Unity Editor tests**

Run: `python -m unittest tests.test_unity_tilemap_integration -v`

Then through Unity MCP run EditMode tests filtered to `GameVisualForge.Unity.Tests.TilemapBundleImporterEditModeTests`.

Expected: Python static tests pass; all selected Unity tests pass; Console has no importer/compiler errors.

- [ ] **Step 7: Commit Unity integration**

```powershell
git add -- integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapObjectImporter.cs integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapApprovalValidator.cs
git add -p -- integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleContracts.cs integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleImporter.cs integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapImportReportWriter.cs integrations/unity/com.game-visual-forge.tilemap/Tests/Editor/TilemapBundleImporterEditModeTests.cs tests/test_unity_tilemap_integration.py
git diff --cached --check
git commit -m "feat: import approved hybrid tilemaps"
```

## Task 7: Rewrite the Forge 2D Map Skill around the guarded hybrid workflow

**Files:**

- Modify: `skills/forge-2d-map/SKILL.md`
- Modify: `skills/forge-2d-map/agents/openai.yaml`
- Modify: `tests/test_skill_contracts.py`

**Interfaces:**

- The Skill selects hybrid Tilemap/object delivery for playable villages with complete buildings.
- The Skill asks road policy and conditional bridge width explicitly.
- The Skill stops at the two user approval gates and never writes approval before explicit user confirmation.

- [ ] **Step 1: Write failing Skill contract assertions**

```python
def test_map_skill_requires_hybrid_objects_and_two_user_gates(self) -> None:
    text = MAP_SKILL.read_text(encoding="utf-8")
    for required in (
        "complete buildings must be object assets",
        "road_connectivity_policy",
        "only when `traversable=true`",
        "style-sample",
        "assembled-map",
        "reviewer: user",
        "do not create an approval record from agent judgment",
        "actual runtime assets",
    ):
        self.assertIn(required, text)
```

- [ ] **Step 2: Rewrite the core Skill workflow concisely**

Keep the body below 500 lines. Preserve source routing, paid confirmation, tile-size, and Unity requirements. Replace fixed 16/32/48 guidance with demand-driven terrain capacity. Add low-freedom instructions:

```markdown
- For playable maps with complete buildings, complete buildings must be object assets; never place façade fragments, doors, roofs, or whole-building crops in repeatable terrain atlas slots.
- Ask for `road_connectivity_policy`; do not assume all roads connect.
- Validate bridge reachability and width only when `traversable=true`.
- Stop after the `style-sample` artifact and wait for explicit user approval.
- Stop after the runtime-composed `assembled-map` preview and gameplay crop and wait again.
- Serialize `reviewer: user` only after that explicit response; do not create an approval record from agent judgment.
```

- [ ] **Step 3: Refresh UI metadata**

Set:

```yaml
interface:
  display_name: "Forge 2D Map"
  short_description: "Build approval-gated playable 2D maps"
  default_prompt: "Use $forge-2d-map to design and validate a playable hybrid 2D map, stopping for user approval at the style sample and assembled map."
```

- [ ] **Step 4: Validate the Skill and its tests**

Run:

```powershell
python C:/Users/QJX/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/forge-2d-map
python -m unittest tests.test_skill_contracts -v
```

Expected: validation and all Skill contract tests pass.

- [ ] **Step 5: Commit only Skill files**

```powershell
git add -p -- skills/forge-2d-map/SKILL.md skills/forge-2d-map/agents/openai.yaml tests/test_skill_contracts.py
git diff --cached --check
git commit -m "fix: gate playable map visual quality"
```

## Task 8: Mark the rejected run and deactivate its Unity instance

**Files:**

- Create ignored: `outputs/spring-creek-village-20260803/rejection.json`
- Modify ignored: `outputs/spring-creek-village-20260803/job/job-state.json`
- Modify: active Unity scene in `I:/UnityProject/2DMirrorDemo`
- Create ignored: `outputs/spring-creek-village-20260803/unity/rejected-scene.png`

**Interfaces:**

- Uses Task 1 `map tile reject`.
- Unity scene retains but deactivates `spring-creek-village-tilemap`.

- [ ] **Step 1: Record rejection with the user's actual reason**

```powershell
python skills/forge-2d-map/scripts/run.py map tile reject --state outputs/spring-creek-village-20260803/job/job-state.json --run-root outputs/spring-creek-village-20260803 --out outputs/spring-creek-village-20260803/rejection.json --reason-code unusable-visual-composition --reason "Generated buildings became repeated façade mosaics; scale, roads, river transitions, plaza, and object repetition made the map unusable." --now 2026-08-07T05:00:00Z
```

Assert state is `rejected`, every final file is hashed, and the original final quality report hash still matches its pre-rejection value.

- [ ] **Step 2: Read Unity state and deactivate without deletion**

Using Unity MCP, verify the active project is `I:/UnityProject/2DMirrorDemo`, find the root named `spring-creek-village-tilemap`, and execute:

```csharp
var root = UnityEngine.SceneManagement.SceneManager.GetActiveScene()
    .GetRootGameObjects().FirstOrDefault(item => item.name == "spring-creek-village-tilemap");
if (root != null) root.SetActive(false);
UnityEditor.SceneManagement.EditorSceneManager.SaveOpenScenes();
return root == null ? "not-found" : "deactivated";
```

- [ ] **Step 3: Verify rejection behavior and capture evidence**

Attempting to validate or import the rejected manifest must fail with the explicit rejected-run message. Confirm the scene contains one inactive old root and no active old root. Capture a Scene View screenshot and copy it to the ignored rejection evidence path.

## Task 9: Run full recovery regression and inline forward-test

**Files:**

- Modify only if failures expose scoped defects in Tasks 1-7.

**Interfaces:**

- Consumes the rejection, hybrid map, approval, quality, Unity, and Skill interfaces from Tasks 1-7.
- Produces a passing full-suite record and an isolated dry-run trace proving the revised Skill stops at the intended gates.

- [ ] **Step 1: Run the complete Python suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 2: Run repository integrity checks**

```powershell
git diff --check
git status --short
rg -n "TBD|TODO|agent.*approval|48 Tile|three 4x4" skills/forge-2d-map src/game_visual_forge tests
```

Expected: no new placeholder or bypass marker; any unrelated pre-existing dirty paths remain unstaged.

- [ ] **Step 3: Perform an isolated inline forward-test**

Because this session is not authorized to dispatch subagents, create a temporary request outside the repository that asks for a playable village with complete buildings, disconnected roads, and no bridge. Follow the revised Skill as written and verify that it:

- selects hybrid object assets;
- asks for road policy;
- does not apply bridge traversal checks;
- stops at style-sample approval;
- cannot reach publish without both exact user approvals.

Delete only the verified temporary directory created for this test; do not delete repository outputs.

- [ ] **Step 4: Run Unity package tests and inspect Console**

Through Unity MCP, run the package EditMode tests and relevant PlayMode tests. Require zero Game Visual Forge compiler/importer errors. Report unrelated MCP transport warnings separately.

## Task 10: Start a clean replacement run and stop at style approval

**Files:**

- Create ignored: `outputs/spring-creek-village-v2-20260807/source/art-direction.json`
- Create ignored: `outputs/spring-creek-village-v2-20260807/source/build_request.py`
- Create ignored: `outputs/spring-creek-village-v2-20260807/source/tilemap-request.json`
- Create ignored: `outputs/spring-creek-village-v2-20260807/source/style-sample.prompt.txt`
- Create ignored: `outputs/spring-creek-village-v2-20260807/source/style-sample.png`
- Create ignored: `outputs/spring-creek-village-v2-20260807/job/*`

**Interfaces:**

- Consumes the revised `forge-2d-map` Skill, hybrid request contracts, and `record-approval` CLI.
- Produces one immutable request fingerprint, `style-sample.png`, `art-direction.json`, and—only after explicit approval—`style-approval.json`.

- [ ] **Step 1: Ask the two remaining request-policy questions**

Ask one question at a time and record the user's exact decisions:

1. `road_connectivity_policy`: `required`, `partial`, or `none`.
2. Because the village has a traversable east-west bridge, `minimum_traversal_width`: recommended `1` cell unless the user requests wider.

Do not infer either value.

- [ ] **Step 2: Create the new art-direction manifest**

Use the already approved direction: medium top-down healing RPG village, modern pixel art, spring daylight, tender green grass, wildflowers, pale blue north-south creek, east-west wooden bridge, warm roofs, timber frames, pale plaster walls, six buildings with the agreed identity plan. Record hybrid object delivery, demand-driven terrain Tiles, selected road policy, and bridge width.

- [ ] **Step 3: Build the exact hybrid request, then plan and route**

Create `source/build_request.py` and the complete `tilemap-request.json` before any image generation. It must declare the 32x24 layout, demand-driven terrain definitions, six building definitions/placements/entrances, restrained prop definitions/placements, selected road policy, traversable bridge and selected width, gameplay crop, and `approval_workflow=two_gate`. Prompts may say “match the approved style sample at `source/style-sample.png`”; the path is stable even though the file is generated next. Run `map tile plan`, then `map tile route` with agent-native image capability. Require source type `agent-native`, no provider, no paid confirmation, and retain this request fingerprint through ingest, process, and validate.

- [ ] **Step 4: Generate the exact style sample**

Use built-in image generation with this prompt, saved verbatim:

```text
Small in-world gameplay-scale style sample for a top-down healing RPG village in modern pixel art. Spring sunny daylight, tender green grass with restrained tiny wildflowers, one natural pale-blue north-south creek, one readable east-west wooden footbridge, one complete modest rural cottage with timber frame, pale plaster walls and warm terracotta roof, and a short dirt path leading to its visible doorway. Coherent single scene at the intended game scale, clean silhouettes, moderate detail, consistent upper-left lighting, natural spacing, no repeated façade mosaic, no apartment block, no tileset sheet, no grid, no labels, no text, no UI, no watermark, no characters.
```

Inspect at original resolution. Internal retries may correct native generation defects while preserving the same design intent.

- [ ] **Step 5: Stop for the `style-sample` user gate**

Show the actual sample and art-direction summary. Do not generate terrain, buildings, or props until the user explicitly approves. After approval, run `record-approval` with roles `style-sample` and `art-direction`.

## Task 11: Generate new runtime assets and assemble the map

**Files:**

- Create ignored: `outputs/spring-creek-village-v2-20260807/raw/terrain-*`
- Create ignored: `outputs/spring-creek-village-v2-20260807/raw/objects/*`
- Create ignored: fingerprinted `outputs/.spring-creek-village-v2-20260807.tile-staging-*/*`

**Interfaces:**

- Consumes the unchanged planned request and style approval from Task 10.
- Produces the exact source set, processing result, runtime-composed preview, gameplay crop, collision overlay, and—only after explicit approval—`assembled-map-approval.json`.

- [ ] **Step 1: Generate a demand-driven terrain set from the visible approved sample**

Generate only the terrain needed by the chosen layout: grass base/variation, necessary path connections, creek center/banks, declared bridge deck/approaches, and farm terrain if retained. Reclassify any large or collision-critical subject as an object rather than filling atlas slots. Normalize accepted cells and assemble atlas pages deterministically without adding filler Tiles.

- [ ] **Step 2: Generate six complete transparent building assets**

Make the approved sample visible immediately before generation. Generate the inn, shop, player home, and three differentiated village homes as one-by-one assets on solid magenta or directly transparent backgrounds according to the image-generation processor. Each image contains one complete building only, at declared scale and anchor, with a visible doorway and no text.

- [ ] **Step 3: Generate restrained props**

Generate only gameplay-relevant trees, rocks, flower clusters, and fence segments required by the layout. Compact props may use small packs; large trees or long fence sections use one-by-one/strip strategies. Enforce each definition's repeat limits.

- [ ] **Step 4: Verify the planned request and run internal asset quality**

Load the already planned request and assert its fingerprint is unchanged. Confirm six unique building asset IDs and placements, six object entrances, object collision cells, selected road policy, traversable bridge and selected width, gameplay crop, demand-driven terrain pages, and `approval_workflow=two_gate`. Require no Tile with `PROP` or `DOORWAY` semantic role.

- [ ] **Step 5: Ingest and process**

Pass every atlas through repeated `--atlas-page` arguments, every building/prop through repeated `--object-asset` arguments, and the recorded style approval through `--style-approval`. Run process and inspect object, collision, asset-set, full preview, gameplay crop, collision overlay, seam, and usage artifacts. Fix any deterministic or internal visual rejection before continuing.

- [ ] **Step 6: Stop for the `assembled-map` user gate**

Show the full map preview, gameplay-scale crop, and separate collision/path overlay. Do not publish or import. If the user requests any change, regenerate/reprocess and show new hashes. Only after explicit approval record the six exact assembled artifact roles.

## Task 12: Publish, import, and accept the replacement

**Files:**

- Create ignored: `outputs/spring-creek-village-v2-20260807/final/*`
- Create/update: `I:/UnityProject/2DMirrorDemo/Assets/GameVisualForgeMaps/spring-creek-village-v2/**`
- Modify: active Unity scene in `I:/UnityProject/2DMirrorDemo`
- Create ignored: `outputs/spring-creek-village-v2-20260807/unity/*`

**Interfaces:**

- Consumes both user approvals and the validated staging artifacts from Tasks 10-11.
- Produces an atomically published final bundle, one active idempotent Unity scene root, a clean saved scene, and acceptance evidence.

- [ ] **Step 1: Validate with both exact user approvals and publish atomically**

Run `map tile validate` with `--style-approval` and `--assembled-approval`. Require deterministic status passed, visual/user-approval status passed, `published=true`, and job status completed.

- [ ] **Step 2: Import and place in the current Unity scene**

Use Unity MCP to call `ImportAndPlaceBundleForAutomation` with the new final manifest. Require terrain Tilemaps plus `Buildings`, `Props`, and `Metadata`; six complete building instances; six entrance records; correct water/bridge collision; and exactly one active replacement root. Keep the rejected root inactive.

- [ ] **Step 3: Save and capture acceptance evidence**

Save the active scene and verify `scene_dirty=false`. Capture a full Scene/Game View and a gameplay-scale view. Compare them with the approved hashes and visually inspect the Unity result.

- [ ] **Step 4: Repeat import and run final tests**

Repeat the same import. Require `had_existing_assets=true`, `resource_guids_stable=true`, `scene_action=updated`, no duplicate roots, and a clean saved scene. Run the full Python suite and filtered Unity package tests again.

- [ ] **Step 5: Final report**

Provide clickable paths to rejection evidence, new approvals, full preview, gameplay crop, collision manifest, object manifest, quality report, Unity manifest, Unity import report, and Unity screenshots. State road policy, conditional bridge width/result, six building/entrance count, active/inactive roots, repeat-import result, and any unrelated Unity warnings.

## Final coverage audit

- [ ] Map every section of the approved design to at least one completed task above.
- [ ] Confirm the rejected final report and assets were not modified or reused.
- [ ] Confirm complete buildings appear only in object manifests/Prefabs, never terrain atlas Tiles.
- [ ] Confirm road checks exactly follow the user's selected policy.
- [ ] Confirm bridge reachability/width checks run only for the declared traversable bridge.
- [ ] Confirm both approval records have `reviewer: user` and match current artifact hashes.
- [ ] Confirm any post-approval asset or placement change causes validation failure.
- [ ] Confirm the runtime preview and Unity scene use the same asset, placement, collision, and entrance data.
- [ ] Confirm the old scene root is inactive, the new root is uniquely active, and scene save is clean.
