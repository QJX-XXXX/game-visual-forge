# Spring Creek Village Coherent Foundation Tilemap Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce and import one coherent 16×12, 48px Unity Tilemap village whose terrain is sliced from a single 768×576 foundation image while buildings, collision, and entrances remain independent runtime objects.

**Architecture:** Add a `coherent_foundation` TileSet profile whose single atlas page is the complete foundation image and whose 192 unique Tiles map one-to-one to map cells. Processing round-trips the page through Tile slicing, proves pixel identity before overlaying separate building sprites, and publishes foundation provenance alongside the existing hybrid bundle. The final run uses built-in image generation for the foundation and six buildings, then imports the approved bundle into `2DMirrorDemo`.

**Tech Stack:** Python 3.12, Pillow, `unittest`, JSON contracts, Unity Editor C#, Unity Tilemap, MCP for Unity, built-in image generation.

## Global Constraints

- Foundation canvas is exactly 768×576 pixels.
- Grid is exactly 16×12 cells of 48×48 pixels.
- The foundation contains grass, flowers, paths, creek, riverbanks, bridge, and empty building pads only.
- Six buildings remain separate transparent Sprite/Prefab objects.
- Water is blocked except for the declared east-west bridge route, which is at least one Tile wide.
- Global road connectivity is not required; only declared bridge and entrance approaches are validated.
- All new visible art uses built-in image generation.
- Runs v2, v3, and v4 remain rejected and cannot be published or imported.

---

### Task 1: Coherent Foundation Request Contract

**Files:**
- Modify: `src/game_visual_forge/contracts/tilemap.py`
- Modify: `src/game_visual_forge/contracts/__init__.py`
- Test: `tests/test_tilemap_contract.py`

**Interfaces:**
- Consumes: existing `TileMapRequest`, `TileSetProfile`, `AtlasPageDefinition`, `TileDefinition`, and `TileLayer`.
- Produces: `TileSetProfile.COHERENT_FOUNDATION` and `TileMapRequest.foundation_prompt_path: str | None`.

- [ ] **Step 1: Write failing contract tests**

Add tests that construct a 2×2 coherent request and assert it accepts one 2×2 atlas, four uniquely addressed Tiles, and matching layer cells. Add negative tests for a missing prompt path, atlas dimensions that differ from the map, duplicate/misplaced Tile cells, and a layer cell that does not reference the Tile at the same grid coordinate.

- [ ] **Step 2: Run the focused tests**

Run: `python -m unittest tests.test_tilemap_contract -v`

Expected: failures mentioning the missing `COHERENT_FOUNDATION` enum member or unsupported request field.

- [ ] **Step 3: Implement the contract**

Add the enum value and normalized optional prompt path. For the coherent profile require exactly one page, `page.columns == map_width`, `page.rows == map_height`, `max_tile_count == map_width * map_height`, one Tile per atlas cell, and a single terrain layer whose cell at `(x, y)` references the Tile declared at atlas cell `(x, y)`.

- [ ] **Step 4: Run the focused tests**

Run: `python -m unittest tests.test_tilemap_contract -v`

Expected: all contract tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/game_visual_forge/contracts/tilemap.py src/game_visual_forge/contracts/__init__.py tests/test_tilemap_contract.py
git commit -m "feat: add coherent foundation tilemap contract"
```

### Task 2: Foundation Round-Trip Processing

**Files:**
- Modify: `src/game_visual_forge/processing/tilemap.py`
- Modify: `src/game_visual_forge/processing/tilemap_quality.py`
- Test: `tests/test_tilemap_processing.py`
- Test: `tests/test_tilemap_quality_metrics.py`

**Interfaces:**
- Consumes: a coherent request and its single 768×576 atlas source.
- Produces: `foundation.png`, `foundation.prompt.txt`, `foundation-recomposition.png`, and a pixel-identity result in `tilemap-quality-metrics.json`.

- [ ] **Step 1: Write failing processing tests**

Create a synthetic 2×2 image with four different colored quadrants, process it as a coherent foundation, and assert the foundation copy and recomposition have identical dimensions and SHA-256 hashes. Assert the prompt is copied from the request path and that seam attention is not raised when the round trip is pixel-identical.

- [ ] **Step 2: Run the focused tests**

Run: `python -m unittest tests.test_tilemap_processing tests.test_tilemap_quality_metrics -v`

Expected: failures because foundation artifacts and identity metrics do not yet exist.

- [ ] **Step 3: Implement round-trip artifacts**

Copy the atlas source to `foundation.png`, copy the declared prompt to `foundation.prompt.txt`, save the terrain-only composed preview to `foundation-recomposition.png`, and compare the two RGBA images byte-for-byte. For coherent profiles, set seam attention from the identity result rather than the generic repeated-Tile edge score.

- [ ] **Step 4: Run focused tests**

Run: `python -m unittest tests.test_tilemap_processing tests.test_tilemap_quality_metrics -v`

Expected: all focused tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/game_visual_forge/processing/tilemap.py src/game_visual_forge/processing/tilemap_quality.py tests/test_tilemap_processing.py tests/test_tilemap_quality_metrics.py
git commit -m "feat: round-trip coherent foundation tilemaps"
```

### Task 3: Quality and Manifest Enforcement

**Files:**
- Modify: `src/game_visual_forge/quality/tilemap.py`
- Modify: `src/game_visual_forge/contracts/manifest.py`
- Test: `tests/test_tilemap_manifest_integrity.py`
- Test: `tests/test_tilemap_processing.py`

**Interfaces:**
- Consumes: foundation artifacts and the processing identity result.
- Produces: deterministic `foundation-recomposition` quality check plus manifest roles `foundation`, `foundation-prompt`, and `foundation-recomposition`.

- [ ] **Step 1: Write failing quality tests**

Assert validation passes for a pixel-identical recomposition and fails when one pixel is changed after slicing. Assert all three foundation artifacts appear in the asset manifest with hashes.

- [ ] **Step 2: Run the focused tests**

Run: `python -m unittest tests.test_tilemap_manifest_integrity tests.test_tilemap_processing -v`

Expected: failures for missing quality check and manifest roles.

- [ ] **Step 3: Implement enforcement**

Add the foundation artifacts to readable-path checks and manifest output roles. Emit `foundation-recomposition=failed` when dimensions or RGBA bytes differ, and refuse publication through the existing deterministic failure path.

- [ ] **Step 4: Run focused and full Python tests**

Run: `python -m unittest tests.test_tilemap_manifest_integrity tests.test_tilemap_processing -v`

Run: `python -m unittest discover -s tests`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/game_visual_forge/quality/tilemap.py src/game_visual_forge/contracts/manifest.py tests/test_tilemap_manifest_integrity.py tests/test_tilemap_processing.py
git commit -m "feat: validate coherent foundation provenance"
```

### Task 4: Skill and Unity Import Contract

**Files:**
- Modify: `skills/forge-2d-map/SKILL.md`
- Modify: `skills/forge-2d-map/agents/openai.yaml`
- Modify: `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleContracts.cs`
- Modify: `integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleImporter.cs`
- Test: `tests/test_skill_contracts.py`
- Test: `tests/test_unity_tilemap_integration.py`

**Interfaces:**
- Consumes: Unity manifest fields for foundation artifacts and a coherent 16×12 atlas.
- Produces: documented recovery workflow and Unity preflight/report fields proving the foundation and recomposition hashes were imported.

- [ ] **Step 1: Write failing repository tests**

Assert the map skill documents coherent foundation generation, unique slicing, pixel-identical recomposition, and immutable rejected runs. Assert Unity contracts expose foundation and recomposition fields and the importer validates their files before scene mutation.

- [ ] **Step 2: Run the focused tests**

Run: `python -m unittest tests.test_skill_contracts tests.test_unity_tilemap_integration -v`

Expected: failures for missing coherent-foundation text and Unity fields.

- [ ] **Step 3: Update skill and Unity importer**

Document when to use coherent foundation Tiles and add manifest/preflight fields. Preserve the existing approval validator and object importer ordering: rejection and approval validation first, foundation validation second, Unity asset creation third, scene mutation last.

- [ ] **Step 4: Run focused tests and compile Unity**

Run: `python -m unittest tests.test_skill_contracts tests.test_unity_tilemap_integration -v`

Refresh the package in `2DMirrorDemo` and query Unity console errors. Expected: no new C# compilation errors.

- [ ] **Step 5: Commit**

```powershell
git add skills/forge-2d-map/SKILL.md skills/forge-2d-map/agents/openai.yaml integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleContracts.cs integrations/unity/com.game-visual-forge.tilemap/Editor/TilemapBundleImporter.cs tests/test_skill_contracts.py tests/test_unity_tilemap_integration.py
git commit -m "feat: integrate coherent foundation tilemaps"
```

### Task 5: Generate and Validate the Final Village Run

**Files:**
- Create: `outputs/spring-creek-village-final-20260807/source/foundation.prompt.txt`
- Create: `outputs/spring-creek-village-final-20260807/source/foundation.png`
- Create: `outputs/spring-creek-village-final-20260807/source/build_request.py`
- Create: `outputs/spring-creek-village-final-20260807/source/style-approval.json`
- Create: `outputs/spring-creek-village-final-20260807/raw/objects/*.png`
- Create: `outputs/spring-creek-village-final-20260807/raw/source-set.json`

**Interfaces:**
- Consumes: the approved style sample and coherent-foundation pipeline.
- Produces: a staged bundle ready for assembled-map review.

- [ ] **Step 1: Generate the foundation**

Use built-in image generation with the approved style reference and a manually written prompt requiring a foundation-only 768×576 layout, north-south creek, east-west bridge, six empty building pads, continuous paths, no buildings, no tall props, no text, and no UI. Save the exact prompt beside the image.

- [ ] **Step 2: Inspect and normalize**

Reject internally if the generated foundation contains buildings, broken banks, a malformed bridge, or hard rectangular pads. Crop and resize only; do not draw replacement art. Save the accepted image at exactly 768×576.

- [ ] **Step 3: Generate six buildings**

Use the visible accepted foundation and style sample as references. Generate one inn, one shop, one player home, and three distinct villager homes as transparent assets sized to their declared 48px footprints. Remove backgrounds and validate alpha.

- [ ] **Step 4: Build, ingest, and process**

Generate 192 unique Tile definitions and matching placement cells, semantic water/bridge/road roles, six object definitions, placements, collision cells, and entrance hooks. Run `plan`, `route`, `ingest`, and `process` into a new immutable run root.

- [ ] **Step 5: Run internal validation**

Require pixel-identical foundation recomposition, bridge traversal, blocked water, alpha, non-overlap, doorway reachability, artifact readability, and manifest hashes. Inspect the assembled, gameplay crop, collision, and foundation recomposition previews before requesting user approval.

### Task 6: Approval, Publication, and Unity Scene Import

**Files:**
- Create: `outputs/spring-creek-village-final-20260807/assembled-map-approval.json`
- Create: `outputs/spring-creek-village-final-20260807/final/*`
- Modify: `I:/UnityProject/2DMirrorDemo/Assets/Scenes/SampleScene.unity`

**Interfaces:**
- Consumes: user-approved assembled artifacts and the validated final bundle.
- Produces: a saved Unity scene with the coherent foundation Tilemap and six building objects.

- [ ] **Step 1: Obtain assembled-map approval**

Show `tilemap-preview.png`, `tilemap-gameplay-crop.png`, and `tilemap-collision-preview.png`. Record approval only after the user explicitly accepts the assembled result.

- [ ] **Step 2: Validate and publish**

Record the assembled approval with exact artifact hashes, run final validation, require `published=true`, and verify `map-quality-report.json` and `asset-manifest.json` report passed quality.

- [ ] **Step 3: Import into Unity**

Use Unity MCP to import the bundle, instantiate its Tilemap Prefab in `Assets/Scenes/SampleScene.unity`, attach `Buildings` and collision/entrance objects, disable rejected generated roots, and save the scene.

- [ ] **Step 4: Verify Unity**

Confirm the new root is active, rejected roots are inactive or absent, six building objects exist, bridge and water colliders match the manifests, and Unity reports no new compilation errors.

- [ ] **Step 5: Final regression**

Run: `python -m unittest discover -s tests`

Expected: all Python and static Unity integration tests pass. Provide links to the final preview, quality report, manifest, Unity report, and scene.
