# Forge 2D Map Atlas Normalization Design

## Objective

Integrate deterministic atlas normalization into `forge-2d-map` so native image generation can produce contract-valid Tilemap atlas pages without manual slicing or resizing. Preserve every generated source, bind normalized outputs to their request and source hashes, and ensure preflight, approval, ingest, publication, and Unity all consume the same normalized pixels.

This feature standardizes atlas geometry. It does not repair artwork, seams, topology, object transparency, perspective, or semantic errors.

## Scope

Support every legal atlas page declared by these profiles:

- `standard_16`
- `adaptive_hd`
- `demand_driven`

Support single-page and multi-page requests, rectangular grids, preset and custom Tile sizes, `atlas_margin`, and `atlas_spacing`.

Reject normalization for `coherent_foundation`. That profile requires pixel-identical foundation recomposition and must retain its original pixels and dimensions.

Automatically normalize only `agent-native` atlas sources. Existing files and external-provider sources remain unchanged unless an operator explicitly opts in to normalization. The Skill must not add a new user approval gate for this deterministic processing step.

## Chosen Architecture

Add a dedicated normalization stage between native generation and critical-asset preflight:

```text
native atlas generation
  -> normalize-atlases
  -> normalized pages and provenance report
  -> preflight-assets
  -> preassembly review
  -> ingest
  -> process
  -> validate and publish
```

Expose the stage through the existing Skill launcher:

```powershell
python skills/forge-2d-map/scripts/run.py map tile normalize-atlases `
  --request <run>/tilemap-request.json `
  --decision <run>/source-decision.json `
  --atlas-page page-01=<generated-page-01.png> `
  --atlas-page page-02=<generated-page-02.png> `
  --repo-root <repo> `
  --out-dir <run>/normalized
```

Keep normalization separate from preflight and ingest. Preflight must remain a validator rather than silently mutating candidates, and ingest must not change pixels after review.

Implement one production normalization engine in the repository processing layer and expose it through the main tilemap CLI. Do not retain a second standalone implementation with different behavior. Update `forge-2d-map/SKILL.md` to call the unified CLI after native generation and before `preflight-assets`.

## Atlas Normalization Contract

Write `<out-dir>/atlas-normalization-report.json` with schema version 1. The report contains:

- the Tilemap request fingerprint;
- the routed source type;
- the overall status;
- one page record for every request atlas page, in request order.

Each page record contains:

- atlas page ID and page status;
- source repository-relative path, SHA-256, and pixel size;
- columns, rows, Tile width, and Tile height;
- target margin and spacing;
- actual resampling algorithm;
- output repository-relative path, SHA-256, and pixel size.

Page status is `normalized` when new pixels are emitted and `not_required` when the input already matches the contract. The overall report is valid only when every request page has a successful page record.

Paths must remain inside the declared repository and run output boundaries. Page IDs, ordering, and count must exactly match `TileMapRequest.resolved_atlas_pages`. Missing, duplicate, and unknown pages are invalid.

The source decision fingerprint must match the request fingerprint. Automatic mode requires `agent-native`. A non-native decision requires an explicit CLI opt-in and is never selected automatically by `SKILL.md`.

## Pixel Processing Rules

For each page, calculate the required output size from the request:

```text
output width  = 2 * margin + columns * tile_width
                + (columns - 1) * spacing
output height = 2 * margin + rows * tile_height
                + (rows - 1) * spacing
```

When the source already has the required size, record `not_required`, preserve its path and hash, and do not emit a duplicate image.

When normalization is required:

1. Interpret the generated source as one dense grid without labels, borders, or gutters.
2. Calculate cell edges proportionally with rounded boundaries so non-divisible source dimensions are fully covered.
3. Crop each source cell independently.
4. Refuse a page when any source cell is smaller than its target Tile.
5. Refuse a page when source cell aspect ratio differs materially from target Tile aspect ratio. Permit only a one-percent tolerance for output-size rounding.
6. Resize each cell independently so sampling cannot cross into an adjacent cell.
7. Preserve RGBA pixels and assemble cells in their original row-major order.
8. Insert transparent target margin and spacing pixels.
9. Save a PNG with the exact calculated output size.

Use nearest-neighbor resampling when `filter_mode` is `point`. Use a high-quality smooth downsampling algorithm when `filter_mode` is `bilinear`, and record the concrete Pillow resampling name in the report. Do not infer resampling behavior from free-form `art_style` text.

Rectangular grids are supported only when the source grid geometry is compatible. For example, a `4x2` page of square Tiles needs source content near a `2:1` aspect ratio. A square source divided into `4x2` rectangular cells must fail rather than distort the artwork into square Tiles.

## Provenance and Workflow Binding

Native generated sources are immutable inputs. Normalization writes derived files under the requested output directory and never overwrites a source file.

Extend `preflight-assets` with:

```text
--normalization-report <run>/normalized/atlas-normalization-report.json
```

Require the report when an `agent-native` page was dimensionally normalized. Validate its request fingerprint, page set, source hashes, output hashes, and output dimensions. The `--atlas-page` candidates supplied to preflight must be the exact report outputs.

Store the normalization report path and SHA-256 in the critical-asset report. Bind the accepted preassembly review to that critical-asset report through the existing report hash. During ingest, revalidate the source and normalized page hashes, copy the normalization report into the raw source evidence, and bind its path and hash in the Tilemap source set.

During processing and validation, copy the report into staging and include it as an artifact in the final asset manifest. Unity imports only the final normalized atlas pages and performs no additional resize. The source generation artifacts remain in the run directory for auditability but are not treated as runtime Tilesets.

Any change to the request, source decision, generated input, normalized output, or report invalidates downstream preflight and approval evidence.

## CLI Results and Errors

On success, `normalize-atlases` prints machine-readable JSON containing:

- schema version and overall status;
- the normalization report path;
- the final path for every page;
- normalized and unchanged page IDs.

A failed command must not produce a report that can pass preflight. Errors identify the atlas page ID, source size, expected size, grid definition, reason, and whether regeneration or explicit manual normalization is allowed.

Fail deterministically for:

- corrupt or unreadable images;
- missing, duplicate, reordered, or unknown pages;
- unsafe input or output paths;
- request and decision fingerprint mismatch;
- automatic normalization of a non-native source;
- `coherent_foundation`;
- zero-sized source cells or source cells smaller than target Tiles;
- incompatible source-grid and target-Tile aspect ratios;
- output dimensions or hashes that do not match the report;
- stale normalization evidence supplied to preflight or ingest.

## Skill Instructions

Keep `SKILL.md` concise. Add one normalization command to the native atlas path and state these invariants:

- run normalization after native atlas generation and before preflight;
- pass the returned final atlas paths to every later command;
- pass the report to preflight when normalization occurred;
- do not automatically normalize user-supplied or provider-supplied assets;
- do not normalize `coherent_foundation`;
- do not treat normalization as proof that Tile artwork or seams are valid.

Do not add a Skill-local README or a second processing implementation. Validate the existing `agents/openai.yaml` against the updated Skill and regenerate it only if its user-facing metadata becomes inaccurate.

## Test Strategy

Add contract, processing, CLI, workflow-integrity, Skill-contract, and end-to-end tests for:

1. report serialization, round-trip behavior, and invalid records;
2. `1024x1024 / 4x4` normalization to exact target Tiles;
3. non-divisible dimensions such as `1254x1254` without gaps or reordering;
4. multi-page requests with page-specific definitions;
5. exact margin, spacing, and transparent padding;
6. point and smooth resampling selection;
7. exact-size pages returning `not_required` without duplicate output;
8. compatible rectangular pages;
9. incompatible source-grid aspect ratios;
10. source cells smaller than target Tiles;
11. missing, duplicate, reordered, and unknown pages;
12. `coherent_foundation` rejection;
13. non-native automatic rejection and explicit opt-in behavior;
14. invalidation after request or source mutation;
15. preflight rejection of mismatched report paths or hashes;
16. ingest rejection after an approved normalized page is replaced;
17. final manifest inclusion of normalization provenance;
18. `SKILL.md` command ordering and invariants;
19. Skill folder validation and the complete Python test suite.

Use synthetic solid-color cells to prove row-major preservation without relying on image perception. Exercise the public CLI for workflow tests rather than validating only internal helpers.

## Non-Goals

Atlas normalization does not:

- generate, regenerate, rearrange, or semantically classify Tiles;
- remove labels, gutters, borders, watermarks, or opaque backgrounds;
- repair seams, terrain transitions, bridges, buildings, entrances, or perspective;
- create missing variants or enforce gameplay topology;
- improve low-quality source art;
- normalize independent building or prop assets;
- alter `coherent_foundation` pixels.

Those concerns remain with generation constraints, critical-asset preflight, seam and topology quality checks, targeted regeneration, and assembled-map review.

## Delivery and Commit Isolation

Commit this specification independently. Implement the processing engine, contracts, CLI wiring, workflow evidence, Skill instructions, and tests in a later implementation commit after the written plan is approved.

Stage explicit paths and inspect the staged file list before every commit. Do not include the pending bridge-connectivity sample JSON, prompt, README asset reports, or sample-specific bridge evidence test in either the design or implementation commits.

The implementation is complete only when targeted tests, the full Python suite, Skill validation, staged-diff checks, and a clean-clone workflow verification pass.
