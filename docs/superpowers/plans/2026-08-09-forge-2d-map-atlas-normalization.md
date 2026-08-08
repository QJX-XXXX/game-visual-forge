# Forge 2D Map Atlas Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hash-bound atlas-normalization stage that converts native-generated atlas pages into exact Tilemap contract dimensions before preflight, while preserving sources and excluding coherent foundations.

**Architecture:** Add versioned normalization contracts and one production processing module under `src/game_visual_forge`, expose it as `map tile normalize-atlases`, and propagate its report through preflight, ingest, staging, final manifest, and Skill instructions. The Skill invokes this explicit CLI stage automatically only for `agent-native`; non-native use requires an explicit CLI flag.

**Tech Stack:** Python 3.11+, Pillow, `unittest`, existing Game Visual Forge contracts/CLI/quality pipeline, Markdown Skill instructions.

## Global Constraints

- Support every legal `standard_16`, `adaptive_hd`, and `demand_driven` atlas page definition, including multiple and rectangular pages, custom Tile sizes, margin, and spacing.
- Reject `coherent_foundation`; never resize foundation pixels.
- Automatically normalize only `agent-native`; require `--allow-non-native` for every other routed source type.
- Preserve native source files, write derived PNGs, and bind request, decision, source, output, preflight, ingest, and manifest hashes.
- Use `point -> nearest` and `bilinear -> lanczos`; never infer resampling from free-form art style.
- Add no user approval gate and do not claim that geometric normalization repairs seams or incorrect artwork.
- Do not add or mention unrelated Skills. Keep the repository scope limited to `forge-2d-map`, `forge-2d-sprite`, and `forge-video-to-sprite`.
- Do not stage the pending bridge-connectivity sample JSON, prompt, README evidence reports, or sample-specific bridge test.

---

## File Structure

- `src/game_visual_forge/contracts/tilemap_atlas_normalization.py`: versioned page/report contracts and strict validation.
- `src/game_visual_forge/processing/tilemap_atlas_normalization.py`: deterministic page geometry, per-cell resize, output emission, and provenance validation.
- `src/game_visual_forge/cli/tilemap.py`: public normalization command, preflight evidence validation, ingest evidence copy, and source-set binding.
- `src/game_visual_forge/cli/main.py`: parser and command dispatch.
- `src/game_visual_forge/contracts/tilemap_asset_review.py`: optional normalization report path/hash in critical-asset evidence.
- `src/game_visual_forge/contracts/tilemap_sources.py`: optional normalization report path/hash in ingested source evidence.
- `src/game_visual_forge/processing/tilemap.py`: copy the accepted normalization report into staging and expose its artifact path.
- `src/game_visual_forge/quality/tilemap.py`: validate and publish normalization provenance.
- `skills/forge-2d-map/SKILL.md`: required native-generation command ordering and safety rules.
- `tests/test_tilemap_atlas_normalization_contract.py`: report contract tests.
- `tests/test_normalize_tile_atlas.py`: processing geometry tests, replacing the current standalone-script test.
- `tests/test_tilemap_atlas_normalization_cli.py`: CLI/source-policy tests.
- `tests/test_tilemap_asset_preflight.py`: normalization-to-preflight binding tests.
- `tests/test_tilemap_manifest_integrity.py`: ingest mutation and final-manifest evidence tests, excluding the pending sample-specific bridge test from staging.
- `tests/test_skill_contracts.py`: command exposure and Skill ordering assertions.

### Task 1: Versioned Normalization Contracts

**Files:**
- Create: `src/game_visual_forge/contracts/tilemap_atlas_normalization.py`
- Modify: `src/game_visual_forge/contracts/__init__.py`
- Test: `tests/test_tilemap_atlas_normalization_contract.py`

**Interfaces:**
- Produces: `AtlasNormalizationStatus`, `AtlasNormalizationPageRecord`, and `AtlasNormalizationReport` with `to_dict()` and `from_dict()`.
- Consumes: `MapSourceType` and repository-relative path rules already used by other contracts.

- [ ] **Step 1: Write failing round-trip and validation tests**

```python
class AtlasNormalizationContractTests(unittest.TestCase):
    def test_report_round_trip_preserves_page_order_and_hashes(self) -> None:
        page = AtlasNormalizationPageRecord(
            "page-01", AtlasNormalizationStatus.NORMALIZED,
            "runs/raw/page-01.png", "a" * 64, 1024, 1024,
            4, 4, 32, 32, 0, 0, "nearest",
            "runs/normalized/page-01.png", "b" * 64, 128, 128,
        )
        report = AtlasNormalizationReport(
            1, "c" * 64, MapSourceType.AGENT_NATIVE,
            AtlasNormalizationStatus.NORMALIZED, (page,),
        )
        self.assertEqual(AtlasNormalizationReport.from_dict(report.to_dict()), report)

    def test_report_rejects_duplicate_pages_and_bad_hashes(self) -> None:
        with self.assertRaises(ValueError):
            AtlasNormalizationReport(1, "bad", MapSourceType.AGENT_NATIVE,
                                     AtlasNormalizationStatus.NORMALIZED, ())
```

- [ ] **Step 2: Run the new contract tests and verify they fail because the module does not exist**

Run: `python -m unittest tests.test_tilemap_atlas_normalization_contract`

Expected: FAIL with an import error for `AtlasNormalizationReport`.

- [ ] **Step 3: Implement strict immutable contracts**

```python
class AtlasNormalizationStatus(StrEnum):
    NORMALIZED = "normalized"
    NOT_REQUIRED = "not_required"

@dataclass(frozen=True)
class AtlasNormalizationPageRecord:
    atlas_id: str
    status: AtlasNormalizationStatus
    source_path: str
    source_sha256: str
    source_width: int
    source_height: int
    columns: int
    rows: int
    tile_width: int
    tile_height: int
    margin: int
    spacing: int
    resampling: str
    output_path: str
    output_sha256: str
    output_width: int
    output_height: int

@dataclass(frozen=True)
class AtlasNormalizationReport:
    schema_version: int
    request_fingerprint: str
    source_type: MapSourceType
    status: AtlasNormalizationStatus
    pages: tuple[AtlasNormalizationPageRecord, ...]
```

Validate lowercase SHA-256 values, safe repository-relative paths, positive source/grid/Tile/output sizes, nonnegative margin/spacing, unique page IDs, nonempty pages, schema version 1, and overall status consistency. Export all three names from `contracts/__init__.py`.

- [ ] **Step 4: Run contract and existing contract suites**

Run: `python -m unittest tests.test_tilemap_atlas_normalization_contract tests.test_tilemap_contract tests.test_tilemap_asset_preflight`

Expected: PASS.

- [ ] **Step 5: Commit the contract slice with explicit paths**

```powershell
git add -- src/game_visual_forge/contracts/tilemap_atlas_normalization.py src/game_visual_forge/contracts/__init__.py tests/test_tilemap_atlas_normalization_contract.py
git diff --cached --check
git commit -m "feat(tilemap): define atlas normalization evidence"
```

### Task 2: Deterministic Multi-Page Normalization Engine

**Files:**
- Create: `src/game_visual_forge/processing/tilemap_atlas_normalization.py`
- Modify: `tests/test_normalize_tile_atlas.py`
- Remove: `skills/forge-2d-map/scripts/normalize_tile_atlas.py`

**Interfaces:**
- Consumes: `TileMapRequest`, `MapSourceDecision`, ordered `tuple[tuple[str, Path], ...]`, repository root, output directory, and `allow_non_native`.
- Produces: `normalize_tilemap_atlases(...) -> AtlasNormalizationReport` plus `validate_atlas_normalization_report(...) -> None`.

- [ ] **Step 1: Replace standalone-script tests with public processing tests**

Test these concrete cases with synthetic RGBA cells:

```python
report = normalize_tilemap_atlases(
    root,
    request,
    native_decision(request),
    (("page-01", source),),
    root / "normalized",
)
self.assertEqual(report.pages[0].output_width, 128)
self.assertEqual(report.pages[0].output_height, 128)
self.assertEqual(report.pages[0].resampling, "nearest")
```

Add separate tests for `1254x1254` rounded edges, exact-size `not_required`, three pages, transparent margin/spacing, rectangular compatible input, aspect mismatch, undersized cells, missing/reordered/duplicate pages, `coherent_foundation`, bilinear-to-lanczos, non-native rejection, and `allow_non_native=True`.

- [ ] **Step 2: Run processing tests and verify the new imports fail**

Run: `python -m unittest tests.test_normalize_tile_atlas`

Expected: FAIL because `game_visual_forge.processing.tilemap_atlas_normalization` is absent.

- [ ] **Step 3: Implement safe path and geometry helpers**

```python
def _inside(root: Path, path: Path, field: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{field} must remain inside repo_root") from exc
    return resolved

def _cell_edges(length: int, count: int) -> tuple[int, ...]:
    return tuple(round(index * length / count) for index in range(count + 1))
```

Require the output directory inside `repo_root`. Compare average source-cell and target-Tile aspect ratios with a one-percent relative tolerance. Check every rounded source cell is at least the target Tile size.

- [ ] **Step 4: Implement ordered page normalization and report emission**

```python
def normalize_tilemap_atlases(
    repo_root: Path,
    request: TileMapRequest,
    decision: MapSourceDecision,
    atlas_pages: tuple[tuple[str, Path], ...],
    out_dir: Path,
    *,
    allow_non_native: bool = False,
) -> AtlasNormalizationReport:
    ...
```

Use `Image.Resampling.NEAREST` for `point` and `Image.Resampling.LANCZOS` for `bilinear`. Create an RGBA output of the exact request size, crop and resize each cell independently, place each Tile at `margin + index * (tile_size + spacing)`, save page PNGs, calculate hashes, and write `atlas-normalization-report.json` with `dump_json`.

If every page is exact-size, return `NOT_REQUIRED` and keep each source path as its output path. Reject coherent foundations before writing derived files. Do not overwrite any input path.

- [ ] **Step 5: Implement evidence revalidation**

```python
def validate_atlas_normalization_report(
    repo_root: Path,
    request: TileMapRequest,
    decision: MapSourceDecision,
    report: AtlasNormalizationReport,
    atlas_pages: tuple[tuple[str, Path], ...],
) -> None:
    ...
```

Recompute the request fingerprint and every input/output hash and size. Require exact page order and require the supplied atlas paths to match each page record's final `output_path`.

- [ ] **Step 6: Run processing and image-quality regression tests**

Run: `python -m unittest tests.test_normalize_tile_atlas tests.test_tilemap_processing tests.test_tilemap_quality_metrics`

Expected: PASS.

- [ ] **Step 7: Commit the production engine and replacement tests**

```powershell
git add -- src/game_visual_forge/processing/tilemap_atlas_normalization.py tests/test_normalize_tile_atlas.py
git diff --cached --check
git commit -m "feat(tilemap): normalize generated atlas pages"
```

Confirm `skills/forge-2d-map/scripts/normalize_tile_atlas.py` is absent from the staged and committed file list; the unified CLI added next is the only public implementation.

### Task 3: CLI Command and Preflight Binding

**Files:**
- Modify: `src/game_visual_forge/cli/main.py`
- Modify: `src/game_visual_forge/cli/tilemap.py`
- Modify: `src/game_visual_forge/contracts/tilemap_asset_review.py`
- Modify: `src/game_visual_forge/processing/tilemap_asset_preflight.py`
- Create: `tests/test_tilemap_atlas_normalization_cli.py`
- Modify: `tests/test_tilemap_asset_preflight.py`

**Interfaces:**
- Produces: `run_tilemap_normalize_atlases(...) -> dict[str, Any]` and CLI `map tile normalize-atlases`.
- Extends: `run_tilemap_preflight_assets(..., decision_path: Path | None = None, normalization_report_path: Path | None = None)` and `TilemapCriticalAssetReport.normalization_report_path/_sha256`.

- [ ] **Step 1: Write failing CLI parser and execution tests**

```python
result = main([
    "map", "tile", "normalize-atlases",
    "--request", str(request_path),
    "--decision", str(decision_path),
    "--atlas-page", f"page-01={source}",
    "--repo-root", str(root),
    "--out-dir", str(root / "normalized"),
])
self.assertEqual(result, 0)
self.assertTrue((root / "normalized" / "atlas-normalization-report.json").is_file())
```

Also assert `--allow-non-native` is required for existing/provider decisions and stdout contains ordered final page paths plus `normalized_page_ids` and `unchanged_page_ids`.

- [ ] **Step 2: Run CLI tests and verify parser rejection**

Run: `python -m unittest tests.test_tilemap_atlas_normalization_cli`

Expected: FAIL because `normalize-atlases` is not a recognized command.

- [ ] **Step 3: Add parser and dispatch**

Add arguments:

```python
tilemap_normalize = tilemap_commands.add_parser("normalize-atlases")
tilemap_normalize.add_argument("--request", type=Path, required=True)
tilemap_normalize.add_argument("--decision", type=Path, required=True)
tilemap_normalize.add_argument("--atlas-page", action="append", default=[])
tilemap_normalize.add_argument("--repo-root", type=Path, required=True)
tilemap_normalize.add_argument("--out-dir", type=Path, required=True)
tilemap_normalize.add_argument("--allow-non-native", action="store_true")
```

Parse page arguments with `parse_atlas_page_argument`, load the request and decision, call the processing function, and return deterministic JSON paths relative to `repo_root`.

- [ ] **Step 4: Extend critical-asset evidence backward-compatibly**

Add optional `normalization_report_path` and `normalization_report_sha256` fields to `TilemapCriticalAssetReport`. Serialize them and read absent fields as `None`. Require both or neither.

Add `--decision` and `--normalization-report` to `preflight-assets`. When a decision is supplied, require its request fingerprint to match. For `agent-native`, require a normalization report even when every page is `not_required`; load and validate the report against the request, decision, and atlas candidates before rendering the review sheet. Save its repository-relative path and hash in the critical report.

Reject an `agent-native` preflight when the decision or report is missing. Existing workflows that supply neither new argument remain backward compatible. Fix the existing dimension check to compare each atlas candidate with `request.expected_atlas_sizes[candidate.asset_id]` instead of comparing every page with the first page's dimensions.

- [ ] **Step 5: Add stale-report preflight tests**

Test successful binding, candidate/output path mismatch, changed output hash, changed source hash, wrong request fingerprint, missing decision, missing native report, and distinct expected dimensions across multiple pages.

- [ ] **Step 6: Run CLI and preflight suites**

Run: `python -m unittest tests.test_tilemap_atlas_normalization_cli tests.test_tilemap_asset_preflight tests.test_tilemap_contract`

Expected: PASS.

- [ ] **Step 7: Commit CLI and preflight integration**

```powershell
git add -- src/game_visual_forge/cli/main.py src/game_visual_forge/cli/tilemap.py src/game_visual_forge/contracts/tilemap_asset_review.py src/game_visual_forge/processing/tilemap_asset_preflight.py tests/test_tilemap_atlas_normalization_cli.py tests/test_tilemap_asset_preflight.py
git diff --cached --check
git commit -m "feat(tilemap): bind normalized atlases to preflight"
```

### Task 4: Ingest, Publication, and Manifest Provenance

**Files:**
- Modify: `src/game_visual_forge/contracts/tilemap_sources.py`
- Modify: `src/game_visual_forge/cli/tilemap.py`
- Modify: `src/game_visual_forge/processing/tilemap.py`
- Modify: `src/game_visual_forge/quality/tilemap.py`
- Modify: `tests/test_tilemap_manifest_integrity.py`

**Interfaces:**
- Extends: `TileMapSourceSet` with optional normalization report path/hash.
- Extends: `TileMapProcessingResult` with `atlas_normalization_path: str = ""`.
- Produces: final manifest artifact role `atlas-normalization-report`.

- [ ] **Step 1: Write failing end-to-end provenance tests**

Create a temporary native request and normalize it, preflight it, accept every candidate, and ingest the accepted pages. Assert:

```python
self.assertEqual(source_set.atlas_normalization_report_path,
                 "atlas-normalization-report.json")
self.assertEqual(source_set.atlas_normalization_report_sha256,
                 sha256_file(raw_dir / "atlas-normalization-report.json"))
```

Mutate a normalized page after review and assert ingest fails. Complete process/validate and assert final `asset-manifest.json` contains exactly one artifact with role `atlas-normalization-report` and the staged report hash.

- [ ] **Step 2: Run the targeted manifest test and verify failure**

Run: `python -m unittest tests.test_tilemap_manifest_integrity`

Expected: FAIL because source-set and processing-result contracts do not expose normalization evidence.

- [ ] **Step 3: Extend source-set and processing-result contracts**

Add paired optional fields:

```python
atlas_normalization_report_path: str | None = None
atlas_normalization_report_sha256: str | None = None
```

to `TileMapSourceSet`, requiring both or neither and reading old payloads as `None`.

Add `atlas_normalization_path: str = ""` to `TileMapProcessingResult`, including round-trip serialization with an empty backward-compatible default.

- [ ] **Step 4: Copy and revalidate evidence during ingest and processing**

During ingest, load the normalization path/hash from the accepted critical report, validate source and output files again, copy the report beside `raw/source-set.json`, and bind the copied hash in `TileMapSourceSet`.

During processing, verify the bound report hash, copy it to staging as `atlas-normalization-report.json`, and set `TileMapProcessingResult.atlas_normalization_path`. Do not copy a report for workflows that never normalized.

- [ ] **Step 5: Publish normalization evidence**

Include the staging report in `_paths(processing)`, validate it is readable, verify it still matches source-set pages, assign artifact role `atlas-normalization-report`, and include it in `AssetManifest`. Unity continues to consume only the final Tileset images.

- [ ] **Step 6: Run workflow integrity and publication suites**

Run: `python -m unittest tests.test_tilemap_manifest_integrity tests.test_tilemap_processing tests.test_tilemap_sources tests.test_tilemap_object_processing tests.test_tilemap_approvals`

Expected: PASS.

- [ ] **Step 7: Commit provenance propagation without the pending bridge evidence hunk**

Stage `tests/test_tilemap_manifest_integrity.py` interactively or by an exact patch so only normalization tests enter the index. Confirm this command does not list any `assets/readme` file:

```powershell
git diff --cached --name-only
```

Then commit:

```powershell
git add -- src/game_visual_forge/contracts/tilemap_sources.py src/game_visual_forge/cli/tilemap.py src/game_visual_forge/processing/tilemap.py src/game_visual_forge/quality/tilemap.py
git commit -m "feat(tilemap): publish atlas normalization provenance"
```

### Task 5: Skill Integration and Release Verification

**Files:**
- Modify: `skills/forge-2d-map/SKILL.md`
- Modify: `tests/test_skill_contracts.py`
- Verify: `skills/forge-2d-map/agents/openai.yaml`

**Interfaces:**
- Consumes: public `map tile normalize-atlases` and `preflight-assets --normalization-report` commands.
- Produces: a concise standard workflow another Codex instance can execute without discovering a hidden helper.

- [ ] **Step 1: Write failing Skill contract assertions**

```python
self.assertIn("map tile normalize-atlases", skill)
self.assertIn("--normalization-report", skill)
self.assertLess(skill.index("map tile normalize-atlases"),
                skill.index("map tile preflight-assets"))
self.assertIn("coherent_foundation", skill)
self.assertIn("do not normalize", skill.lower())
```

Update the launcher command list assertion to require `normalize-atlases`.

- [ ] **Step 2: Run Skill tests and verify failure**

Run: `python -m unittest tests.test_skill_contracts tests.test_forge_skill_scope`

Expected: FAIL because the Skill and launcher help do not yet document/expose the full workflow.

- [ ] **Step 3: Add the concise native normalization step to `SKILL.md`**

Document one command between route/native generation and preflight. State that the returned page paths are mandatory inputs for preflight and ingest, the report is mandatory when pages changed, non-native sources are not silently modified, coherent foundations are excluded, and normalization does not prove seam or visual correctness.

Do not add a Skill-local README. Compare `agents/openai.yaml` to the updated `SKILL.md`; leave it unchanged if its trigger, display name, and default prompt remain accurate.

- [ ] **Step 4: Validate the Skill package**

Run:

```powershell
python C:/Users/QJX/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/forge-2d-map
python skills/forge-2d-map/scripts/run.py map tile --help
```

Expected: Skill validation passes and help lists `normalize-atlases`.

- [ ] **Step 5: Run targeted and full Python verification**

Run:

```powershell
python -m unittest tests.test_tilemap_atlas_normalization_contract tests.test_normalize_tile_atlas tests.test_tilemap_atlas_normalization_cli tests.test_tilemap_asset_preflight tests.test_tilemap_manifest_integrity tests.test_skill_contracts
python -m unittest discover -s tests
```

Expected: all tests pass.

- [ ] **Step 6: Run a clean workflow fixture**

In a temporary directory inside the repository, generate synthetic `agent-native` atlas pages, run `plan`, `route`, `normalize-atlases`, `preflight-assets`, accepted preassembly review, `ingest`, `process`, approvals, and `validate`. Assert the final directory exists, atlas dimensions match the request, and the manifest contains the normalization report role. Remove only the explicitly resolved temporary fixture directory after verifying it is inside the repository test-output directory.

- [ ] **Step 7: Check repository and staged isolation**

Run:

```powershell
git diff --check
git status --short
git diff --cached --name-only
```

Confirm no pending `assets/readme/adaptive-river-crossing-map-*`, bridge prompt/contract, or sample-specific bridge evidence test hunk is staged.

- [ ] **Step 8: Commit Skill integration and final tests**

```powershell
git add -- skills/forge-2d-map/SKILL.md tests/test_skill_contracts.py
git diff --cached --check
git commit -m "docs(skill): require atlas normalization before preflight"
```

- [ ] **Step 9: Review commits and push only after every check passes**

Run:

```powershell
git log --oneline --decorate -8
git status --branch --short
git push origin main
```

Expected: implementation commits are pushed to `main`; only the explicitly excluded bridge evidence remains uncommitted.
