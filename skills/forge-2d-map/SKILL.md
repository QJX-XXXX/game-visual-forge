---
name: forge-2d-map
description: "Generate and integrate playable 2D game maps with demand-driven terrain Tilemaps, complete building/prop objects, collision and traversal contracts, deterministic quality gates, and explicit user approvals. Use for RPG villages, overworlds, arenas, bridges, water, Unity Tilemaps, and map previews/imports."
---

# Forge 2D Map

Use this skill when the requested map must be a real runtime map rather than a decorative bitmap. Treat the map as a contract shared by generated images, deterministic processing, quality validation, and the target engine.

## Required interaction

1. Start by asking what the player should do in the map: camera/style, size, walkability, collision, water, bridges, entrances, building identities, engine/project, and import mode.
2. Present a compact design summary. Do not generate assets until the user confirms it.
3. For a playable village or similar map, use the `TWO_GATE` workflow. Stop after showing the style sample and wait for the user’s explicit approval. Generate the assembled map only after that approval; stop again and wait for explicit assembled-map approval.
4. A user approval is not implied by “continue” or by an agent visual judgment. Record approvals with `map tile record-approval`; the reviewer must be `user`.

## Architecture defaults

- Use a hybrid delivery for playable maps: terrain, roads, water, banks, bridge deck, and other repeatable ground use Tilemap layers; complete buildings and meaningful props use independent Sprite/Prefab objects.
- Never put building façades, roofs, doors, complete-building crops, or large collision-critical subjects into repeatable terrain Tiles.
- Use demand-driven Tilesets. Declare only the terrain semantics the layout needs; do not fill an atlas to a fixed quota. `TileSetProfile.DEMAND_DRIVEN` permits one to four pages with each page no larger than 4×4 and `max_tile_count` no larger than declared capacity.
- Water is blocked by default. A bridge is traversal-critical only when `BridgeConnectivityRule.traversable=true`; then declare its span and positive `minimum_traversal_width`, and verify the approach/bridge corridor.
- Road global connectivity is optional. Set `road_connectivity_policy` to `none`, `partial`, or `required`; only declared `road_connection_requirements` are tested.
- Buildings need complete object images, footprint-relative collision cells, a clear doorway cell, placements, and object entrances. Unity receives `Buildings`, `Props`, and `Metadata` hierarchies.

## Standard CLI flow

For a Tilemap request, run:

```powershell
python skills/forge-2d-map/scripts/run.py map tile plan --request <request.json> --out-dir <run> --now <utc>
python skills/forge-2d-map/scripts/run.py map tile route --request <run>/tilemap-request.json --capabilities <capabilities.json> --out <run>/source-decision.json --state <run>/job-state.json --now <utc>
python skills/forge-2d-map/scripts/run.py map tile ingest --request <run>/tilemap-request.json --decision <run>/source-decision.json --atlas-page page-01=<terrain.png> --object-asset inn=<inn.png> --repo-root <repo> --out <run>/raw/source-set.json --state <run>/job-state.json --style-approval <run>/source/style-approval.json --now <utc>
python skills/forge-2d-map/scripts/run.py map tile process --request <run>/tilemap-request.json --raw-image <run>/raw/source-set.json --repo-root <repo> --out-dir <run> --state <run>/job-state.json --now <utc>
python skills/forge-2d-map/scripts/run.py map tile validate --request <run>/tilemap-request.json --raw-image <run>/raw/source-set.json --processing-result <staging>/processing-result.json --repo-root <repo> --staging-dir <staging> --final-dir <run>/final --style-approval <run>/source/style-approval.json --assembled-approval <run>/assembled-map-approval.json --state <run>/job-state.json --now <utc>
```

Use repeated `--atlas-page` and `--object-asset` arguments in request order. The request fingerprint, source fingerprints, object IDs, atlas IDs, placements, and approval hashes must remain unchanged through processing.

Record a gate only after the user approves the displayed artifacts:

```powershell
python skills/forge-2d-map/scripts/run.py map tile record-approval --gate style-sample --artifact style-sample=<run>/source/style-sample.png --artifact art-direction=<run>/source/art-direction.json --out <run>/source/style-approval.json --repo-root <repo> --now <utc>
python skills/forge-2d-map/scripts/run.py map tile record-approval --gate assembled-map --artifact tilemap-preview=<staging>/tilemap-preview.png --artifact gameplay-crop=<staging>/tilemap-gameplay-crop.png --artifact tilemap-placement=<staging>/tilemap-placement.json --artifact tilemap-objects=<staging>/tilemap-objects.json --artifact tilemap-collision=<staging>/tilemap-collision.json --artifact asset-set=<staging>/asset-set.json --out <run>/assembled-map-approval.json --repo-root <repo> --now <utc>
```

The style gate requires exactly `style-sample` and `art-direction`. The assembled gate requires exactly `tilemap-preview`, `gameplay-crop`, `tilemap-placement`, `tilemap-objects`, `tilemap-collision`, and `asset-set`. Every artifact is rehashed at validation and Unity import.

## Quality and publication

Inspect at least `tilemap-preview.png`, `tilemap-gameplay-crop.png`, `tilemap-collision-preview.png`, `tile-seam-preview.png`, `tile-usage-preview.png`, `tilemap-quality-metrics.json`, `tilemap-collision.json`, and `map-quality-report.json`.

Deterministic checks cover atlas dimensions/slices, semantic adjacency, clipping, object alpha and silhouette, duplicate/overlapping objects, density limits, doorway reachability, water collision, declared road policy, and traversable bridge width/connectivity. Any deterministic failure blocks publication. `TWO_GATE` also blocks publication/import when either approval is missing, stale, agent-authored, extra-role, or hash-mismatched. Do not pass `--visual-review` for a two-gate request.

To reject an unusable run while preserving evidence:

```powershell
python skills/forge-2d-map/scripts/run.py map tile reject --state <run>/job-state.json --run-root <run> --out <run>/rejection.json --reason-code <code> --reason <explanation> --now <utc>
```

Rejected runs are terminal, immutable evidence. Validation, publication, and Unity import must refuse any run containing `rejection.json`; never delete or silently overwrite its artifacts.

## Unity integration

Use the repository package `integrations/unity/com.game-visual-forge.tilemap`. Choose `AssetsOnly` unless the user explicitly requests placing the Tilemap Prefab in the active scene; then use `ImportAndPlace`. The importer must preflight rejection and approvals before creating or mutating assets, preserve GUIDs on repeat imports, create complete object Prefabs, and place exactly one scene root when requested. After script changes, wait for Unity compilation, read the console, run EditMode tests, and capture a screenshot of the imported scene.

Keep runtime collision and entrance data in generated manifests. Do not claim a map is playable from a decorative preview alone.
