---
name: forge-2d-map
description: "Build reviewed, playable 2D game maps with terrain Tilemaps, complete object prefabs, collision and traversal contracts, deterministic quality gates, user approvals, and Unity scene parity. Use for RPG villages, overworlds, arenas, bridges, water, and Unity Tilemap import or placement."
---

# Forge 2D Map

Use this Skill when the result must be a runtime map that a player can walk through, collide with, and enter—not a decorative bitmap. Treat the request, generated candidates, processed artifacts, approval records, and Unity scene as one hash-bound contract.

## Standard interaction

1. Collect one grouped intake card before creating a request. Ask together for gameplay actions, visual direction, terrain topology, object identities and entrances, engine/project delivery, and source/regeneration policy. Do not repeat answered questions or ask one question per field.
2. Run `map tile plan` with the raw intake. It must return one of:
   - `needs_user_input` with all unresolved groups in stable order;
   - `needs_user_confirmation` with one canonical summary and SHA-256;
   - `planned` only after the user confirms that exact summary.
   No plan, Job state, or generated artifact may be written for either unresolved status.
3. Keep exactly two user approval gates:
   - `style-sample`: approve visual direction before generation;
   - `assembled-map`: approve one assembled review sheet after processing.
   Intake confirmation and agent preassembly review are workflow checks, not extra user gates.
4. If a critical candidate fails, replace only that candidate inside the confirmed layout, source, cost, art direction, and delivery boundaries. Re-run preflight and agent review; do not terminally reject the run just because a candidate needs replacement.

## Architecture routing

- Route a fixed authored layout containing any of `watercourse`, `bridge`, `complex-paths`, `paths`, or `building-pads` to `coherent_foundation`. Use one foundation image at map pixel dimensions, one unique tile per map cell, and verify pixel-identical recomposition.
- Route reusable or procedural terrain to `demand_driven`. Declare only the pages and semantics the layout needs.
- Reject a request when its declared profile conflicts with the deterministic route.
- Use hybrid delivery: repeatable ground, roads, water, banks, and bridge deck are Tilemap layers; complete buildings and meaningful props are independent Sprite/Prefab objects.
- Water is blocked by default. A bridge is traversable only when its contract declares `traversable=true`; then preserve the declared corridor width and verify bridge cells are not terrain blockers. Main roads are not globally required unless the request declares a required connectivity policy.

## Candidate preflight

Before ingest, run:

```powershell
python skills/forge-2d-map/scripts/run.py map tile preflight-assets --request <run>/tilemap-request.json --architecture <run>/architecture-decision.json --atlas-page page-01=<foundation-or-atlas.png> --object-asset inn=<inn.png> --repo-root <repo> --out-dir <run>/preflight
python skills/forge-2d-map/scripts/run.py map tile record-asset-review --report <run>/preflight/critical-assets-report.json --decisions <run>/preflight/decisions.json --out <run>/preflight/preassembly-review.json --now <utc>
```

The report must contain candidate paths and hashes, deterministic checks, visual-review status, a critical-assets review sheet, and focused bridge/object crops. Ingest must refuse missing, rejected, stale, or hash-mismatched reports/reviews. Keep candidate pixels unchanged; labels belong in review-sheet margins.

## Two-gate CLI flow

After `planned`, route and ingest only with the accepted preassembly review:

```powershell
python skills/forge-2d-map/scripts/run.py map tile route --request <run>/tilemap-request.json --capabilities <capabilities.json> --out <run>/source-decision.json --state <run>/job-state.json --now <utc>
python skills/forge-2d-map/scripts/run.py map tile ingest --request <run>/tilemap-request.json --decision <run>/source-decision.json --atlas-page page-01=<terrain.png> --object-asset inn=<inn.png> --repo-root <repo> --out <run>/raw/source-set.json --state <run>/job-state.json --style-approval <run>/source/style-approval.json --preassembly-review <run>/preflight/preassembly-review.json --critical-assets-report <run>/preflight/critical-assets-report.json --now <utc>
python skills/forge-2d-map/scripts/run.py map tile process --request <run>/tilemap-request.json --raw-image <run>/raw/source-set.json --repo-root <repo> --out-dir <run> --state <run>/job-state.json --now <utc>
```

Inspect `assembled-review-sheet.png` and the underlying preview, gameplay crop, collision preview, bridge crops, object entrance crops, seam/usage previews, manifests, and quality report. Record the assembled approval with the exact role order beginning with `review-sheet`, then validate:

```powershell
python skills/forge-2d-map/scripts/run.py map tile record-approval --gate assembled-map --artifact review-sheet=<staging>/assembled-review-sheet.png --artifact tilemap-preview=<staging>/tilemap-preview.png --artifact gameplay-crop=<staging>/tilemap-gameplay-crop.png --artifact tilemap-placement=<staging>/tilemap-placement.json --artifact tilemap-objects=<staging>/tilemap-objects.json --artifact tilemap-collision=<staging>/tilemap-collision.json --artifact asset-set=<staging>/asset-set.json --out <run>/assembled-map-approval.json --repo-root <repo> --now <utc>
python skills/forge-2d-map/scripts/run.py map tile validate --request <run>/tilemap-request.json --raw-image <run>/raw/source-set.json --processing-result <staging>/processing-result.json --repo-root <repo> --staging-dir <staging> --final-dir <run>/final --style-approval <run>/source/style-approval.json --assembled-approval <run>/assembled-map-approval.json --state <run>/job-state.json --now <utc>
```

Approval hashes are rechecked at validation and Unity import. A rejection artifact is immutable and blocks publication/import.

## Unity completion

Use `integrations/unity/com.game-visual-forge.tilemap`. Use `AssetsOnly` unless the user explicitly requests placing the prefab in the active scene; then use `ImportAndPlace`. The importer validates approvals and rejection state before mutation, preserves generated GUIDs on repeat imports, and runs post-placement scene acceptance. Acceptance must report `passed` and cover one owned root, tile/object counts, object transforms and Sprite bounds, colliders, doorway cells, terrain blockers, and traversable bridge cells. `AssetsOnly` records `scene_acceptance_status=not_run`.

After Unity changes, wait for compilation, inspect the console, run EditMode and PlayMode tests, save the target scene, confirm it is clean, and capture an orthographic top-down screenshot that matches the assembled review sheet. Never claim playability from a preview alone.
