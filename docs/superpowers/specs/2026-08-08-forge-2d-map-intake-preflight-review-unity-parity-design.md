# Forge 2D Map Intake, Preflight, Review, and Unity Parity Design

## Purpose

Strengthen `forge-2d-map` so that an incomplete brief cannot start generation, fixed high-continuity maps select the correct visual architecture before asset production, defective critical assets cannot enter assembly, user review is consolidated, and a successful Unity import is not accepted unless the placed scene matches the approved composition.

This design implements the agreed P0 and P1 recovery work from the completed spring-creek village run.

## Repository Scope

The repository owns exactly these Skill directories:

- `skills/forge-2d-map`
- `skills/forge-2d-sprite`
- `skills/forge-video-to-sprite`

This change modifies only the map workflow and shared code required by that workflow. It does not add another Skill, introduce a cross-Skill dependency, or rename the existing three Skills.

## Goals

1. Add a Skill-level and CLI-level intake gate before planning or generation.
2. Consolidate identical or related questions into one user confirmation request.
3. Route fixed, continuity-critical maps to `coherent_foundation` before image generation.
4. Add a non-user preassembly asset review that supports targeted regeneration without creating another user approval gate.
5. Produce one user-facing assembled review sheet while retaining hashes for all underlying runtime artifacts.
6. Validate Unity object placement, collision alignment, scene uniqueness, and saved-scene state after import.
7. Preserve rejected-run immutability, paid-provider confirmation, existing approval hashes, and legacy import compatibility.

## Non-Goals

- Building a general autonomous image-generation scheduler.
- Changing the two mandatory user approval gates.
- Generating building interiors, character art, NPCs, or animation assets.
- Replacing deterministic checks with agent visual judgment.
- Reworking unrelated sprite or video workflows.
- Cleaning or committing unrelated existing worktree changes.

## Workflow Overview

The revised two-gate workflow is:

1. Assess the grouped intake.
2. Ask once for all missing or unresolved requirement groups.
3. Present one compact requirements summary for confirmation.
4. Plan and record the architecture decision.
5. Obtain the style sample and record the existing user style approval.
6. Generate candidate foundation/atlas and object assets.
7. Run preassembly asset checks and record an agent preassembly review.
8. Regenerate only rejected candidate assets and rerun preassembly checks until accepted.
9. Ingest the accepted, hash-bound source set.
10. Process the runtime bundle and generate one assembled review sheet.
11. Record the existing user assembled-map approval, including the review sheet hash.
12. Validate and publish the bundle.
13. Import or import-and-place in Unity.
14. Run Unity scene acceptance, save the scene, run tests, and capture an orthographic top-down screenshot.

Only steps 5 and 11 are mandatory user approval gates. Step 3 is the normal initial requirements confirmation and does not create a third approval artifact.

## Grouped Intake Contract

### `TileMapIntake`

Add a structured intake object to new two-gate `TileMapRequest` documents. It contains six groups:

1. `gameplay`
   - intended player actions
   - walkability requirement
   - collision requirement
   - enterable-building requirement
   - interaction or trigger requirement
2. `visual`
   - perspective
   - map scale
   - art style
   - season, weather, and mood
3. `topology`
   - road connectivity policy
   - water presence and collision policy
   - bridge presence, orientation, and traversal requirement
   - continuity-critical terrain features
4. `objects`
   - required building and prop identities
   - instance counts
   - entrance policy
   - independent-object requirements
5. `delivery`
   - engine target
   - project path or project identifier
   - scene path when placing
   - import mode: `assets_only` or `import_and_place`
6. `source`
   - source preference
   - native generation permission
   - paid-provider constraints
   - targeted automatic regeneration permission

The intake also contains:

- `requirements_confirmed: bool`
- `confirmed_summary_sha256: str | null`
- `layout_strategy: fixed_authored | reusable_tiles | procedural`

The summary hash is computed from a canonical, user-facing requirements summary. When `requirements_confirmed` is true, the hash is mandatory and must match the canonical summary derived from the request. Changing an intake value invalidates confirmation without adding a separate approval file.

### Intake assessment results

`map tile plan` must inspect the raw request payload before constructing `TileMapRequest` and return exactly one of:

- `needs_user_input`
  - includes `question_groups`
  - writes no execution plan or job state
- `needs_user_confirmation`
  - includes `confirmation_summary` and its SHA-256
  - writes no execution plan or job state
- `planned`
  - writes the normalized request, architecture decision, execution plan, and job state

Malformed technical fields remain errors. Missing or unconfirmed user-facing intake fields are workflow states, not stack traces.

### Question consolidation

Every question has a stable `question_group_id`. Questions with the same group or the same effect on the request are merged. The returned payload contains one ordered list covering all unresolved groups, with:

- a plain-language question
- the recommended default
- the consequence of accepting that default
- the request fields it resolves

The Skill instructs the agent to present all returned groups in one compact message. It must not ask one question per field or repeat a resolved question. A follow-up question is allowed only when the user's answer introduces a new contradiction or changes layout, cost, source, or delivery scope.

### Compatibility

Legacy visual requests remain parseable. New `two_gate` requests require `intake`. Legacy requests do not gain a fabricated confirmation and keep their existing behavior.

## Architecture Decision

Add `TileMapArchitectureDecision`, emitted as `architecture-decision.json`, containing:

- `request_fingerprint`
- `layout_strategy`
- `selected_profile`
- `continuity_reasons`
- `requires_complete_foundation`
- `requires_independent_objects`

Routing rules are deterministic:

- `fixed_authored` plus a continuous watercourse, traversable bridge, complex road/path network, or building pads selects `coherent_foundation`.
- `reusable_tiles` or `procedural` selects `demand_driven` unless an explicit compatible project contract requires a legacy profile.
- Complete buildings, meaningful props, doors, and runtime-controlled subjects remain independent objects under both profiles.
- A request/profile mismatch blocks planning with a message that identifies the conflicting inputs and recommended profile.

The execution plan uses profile-specific actions. A coherent foundation plan says `obtain-coherent-foundation-and-objects`; it must not describe the source as independently generated repeatable terrain pages.

## Preassembly Asset Review

### Commands and artifacts

Add a pre-ingest command that accepts the request, architecture decision, candidate atlas/foundation paths, and candidate object paths. It emits:

- `critical-assets-report.json`
- `critical-assets-review-sheet.png`
- bridge or continuity focus crops when declared
- one object focus crop per declared critical object

Add an agent review command that records `preassembly-review.json` with:

- `reviewer: agent`
- `status: accepted | rejected`
- candidate file paths and SHA-256 values
- per-asset results
- stable reason codes
- human-readable reasons
- review timestamp

This record is not a user approval and cannot satisfy either user gate.

### Deterministic checks

The preassembly report checks at least:

- exact source dimensions and readable image data
- required prompt metadata
- foundation-only restrictions
- transparent object alpha
- object pixel size versus footprint and pixels per unit
- object edge touching and abnormal opaque rectangular backgrounds
- doorway location within the declared footprint
- placement footprint within map bounds
- bridge span, orientation, approach cells, water blockers, and traversal corridor
- source IDs, ordering, and request fingerprint consistency

Visual continuity remains an explicit agent inspection of the generated review sheet. Deterministic status and agent visual status are recorded separately.

### Targeted regeneration loop

If preassembly review rejects an asset:

- do not create a terminal run rejection
- do not ingest or assemble the rejected candidate set
- regenerate only listed failed assets
- rerun the preassembly command
- invalidate prior review automatically when any candidate hash changes

The agent may perform this loop without another user question only when the confirmed layout, art direction, source authorization, provider cost boundary, and delivery target remain unchanged. Any change to those values returns to grouped user confirmation.

`map tile ingest` requires an accepted, hash-matching preassembly review for new two-gate requests. Legacy requests remain compatible.

## Assembled Review Sheet

Processing emits `assembled-review-sheet.png` with clearly separated panels:

1. clean final composition
2. declared gameplay crop at gameplay scale
3. collision preview with legend
4. one bridge/continuity crop when applicable
5. building entrance crops for every enterable building

The clean runtime preview remains a separate unannotated artifact. The review sheet is for QA and approval only.

The assembled approval roles become:

- `review-sheet`
- `tilemap-preview`
- `gameplay-crop`
- `tilemap-placement`
- `tilemap-objects`
- `tilemap-collision`
- `asset-set`

Python publication and Unity import validate the exact role order and every hash. The user-facing Skill flow shows the review sheet plus a short summary instead of presenting a long unlabeled file list.

## Unity Scene Acceptance

### Import-time validation

Keep approval, rejection, foundation, and manifest preflight before Unity asset or scene mutation. After import-and-place, run a deterministic scene acceptance validator that checks:

- exactly one scene root linked to the generated map prefab
- expected Tilemap layer, Tile, and object counts
- generated resource GUID stability on repeat import
- object local positions equal the center of declared top-left footprints
- Sprite bounds remain within the declared footprint and map bounds
- collider centers and sizes match declared collision cells
- doorway cells have no blocking building collider
- water cells remain blocked except declared traversable bridge cells
- scene path equals the requested target

Write `Reports/unity-scene-acceptance.json` and expose its status in the Unity import report.

### Completion workflow

For import-and-place, the Skill requires:

1. wait for compilation and asset refresh
2. read and clear stale console entries before the final verification run
3. import once, then verify before retrying
4. run scene acceptance
5. save the scene and confirm `isDirty=false`
6. run all package EditMode and PlayMode tests
7. confirm zero new console errors
8. capture an orthographic top-down Scene view framed to the map root
9. compare the screenshot against the approved composition

An import report with no scene acceptance evidence is insufficient to claim completion.

## Skill Documentation

Revise `skills/forge-2d-map/SKILL.md` to make the positive workflow executable and concise:

- begin with the grouped intake gate
- explain when coherent foundation is mandatory
- include the preassembly regeneration loop
- identify exactly two user approval gates
- show the user-facing review sheet at assembled approval
- require Unity scene acceptance before completion
- include a coherent-foundation CLI example

Keep detailed schemas and long command examples in one-level reference files if the main Skill approaches 500 lines. Keep `agents/openai.yaml` aligned with the revised Skill.

## Failure Handling

- Missing intake: structured `needs_user_input`; no job created.
- Unconfirmed intake: structured `needs_user_confirmation`; no job created.
- Architecture conflict: plan blocked; no source generation.
- Candidate asset deterministic failure: preassembly rejected; targeted regeneration allowed.
- Candidate asset visual failure: preassembly rejected with reason codes; targeted regeneration allowed.
- Candidate hash change: old preassembly review invalid.
- Missing user approval or hash mismatch: publication and Unity import blocked.
- Terminal `rejection.json`: validation, publication, and Unity import blocked permanently for that run.
- Unity scene acceptance failure: scene remains unaccepted; completion cannot be reported.

## Test Strategy

Prefer new focused Python test modules to avoid overlapping unrelated dirty files:

- `tests/test_tilemap_intake.py`
- `tests/test_tilemap_architecture_routing.py`
- `tests/test_tilemap_asset_preflight.py`
- `tests/test_tilemap_review_sheet.py`

Extend existing approval, manifest, Unity integration, and Skill contract tests only where their public contracts change.

Tests cover:

- grouped missing-field output and stable ordering
- confirmation summary hashing and invalidation
- no plan/job files before confirmation
- deterministic architecture selection and conflict rejection
- preassembly report contents and image outputs
- accepted review hash matching
- targeted candidate replacement invalidating review
- ingest refusal without accepted review
- assembled review role order and hash enforcement
- Unity object, Sprite, collider, doorway, water, and bridge parity
- repeat import uniqueness and GUID stability
- Skill wording for grouped intake, two user gates, targeted regeneration, and Unity acceptance
- repository Skill directory set remains the intended three directories

Run the complete Python suite and both Unity test modes before completion.

## Expected File Impact

Likely new modules:

- `src/game_visual_forge/contracts/tilemap_intake.py`
- `src/game_visual_forge/routing/tilemap_architecture.py`
- `src/game_visual_forge/processing/tilemap_asset_preflight.py`
- `src/game_visual_forge/processing/tilemap_review_sheet.py`
- focused Python tests listed above
- Unity scene acceptance validator and its EditMode tests

Likely modified modules:

- `src/game_visual_forge/contracts/tilemap.py`
- `src/game_visual_forge/contracts/approval.py`
- `src/game_visual_forge/contracts/__init__.py`
- `src/game_visual_forge/cli/main.py`
- `src/game_visual_forge/cli/planning.py`
- `src/game_visual_forge/cli/tilemap.py`
- `src/game_visual_forge/processing/tilemap.py`
- `src/game_visual_forge/quality/tilemap.py`
- Unity bundle contracts, approval validator, importer, and report writer
- `skills/forge-2d-map/SKILL.md`
- `skills/forge-2d-map/agents/openai.yaml`

## Acceptance Criteria

The implementation is complete when:

1. A two-gate request with incomplete intake cannot create a plan or Job state.
2. All unresolved requirement groups are returned together without duplicate questions.
3. A changed confirmed requirement invalidates its summary hash.
4. A fixed village with a river, bridge, paths, and building pads routes to `coherent_foundation`.
5. Reusable or procedural terrain routes to `demand_driven`.
6. Rejected candidate assets cannot be ingested and can be replaced without terminally rejecting the run.
7. Changed candidate hashes invalidate preassembly acceptance.
8. The user reviews one assembled review sheet while all runtime artifacts remain hash-bound.
9. Publication and Unity import still require exactly two user approvals.
10. Unity scene acceptance detects shifted objects, misaligned colliders, blocked doorways, duplicate roots, and invalid water/bridge collision.
11. The saved target scene is clean, Unity tests pass, and the final top-down screenshot matches the approved composition.
12. The full Python test suite and Unity EditMode/PlayMode suites pass without new console errors.
