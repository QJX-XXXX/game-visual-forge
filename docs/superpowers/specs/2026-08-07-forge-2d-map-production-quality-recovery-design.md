# Forge 2D Map Production Quality Recovery Design

## 1. Status and decision

The `spring-creek-village-20260803` run is rejected. Its files remain available as failure evidence, but it must no longer be described as accepted, published for use, or visually approved. The placed Unity scene instance must be deactivated rather than deleted.

The replacement workflow uses a hybrid runtime model:

- repeatable terrain remains Unity Tilemap data;
- buildings are complete object assets and Prefabs;
- props are independent reusable objects;
- collision, entrances, traversal rules, and approvals are structured data;
- Unity import is forbidden until the current assembled preview has explicit user approval.

This design replaces the assumption that every visible map element should occupy a fixed 32x32 atlas slot. It also removes the requirement to fill exactly 48 Tiles or three atlas pages.

## 2. Failure diagnosis

The rejected run passed because its deterministic checks verified file integrity, dimensions, Tile IDs, semantic roles, collision flags, and a coarse seam threshold. Those facts did not establish that the runtime composition looked like a usable village.

The process failed in five ways:

1. Complete-building image fragments were classified as repeatable 32x32 Tiles, producing building mosaics instead of cottages.
2. A fixed 48-Tile, three-page quota encouraged filler assets and forced incompatible subjects into one atlas model.
3. The composition contract could express cells but not complete buildings, footprints, render anchors, or object collision outlines.
4. Visual review had no user provenance or artifact hash, so an agent-generated `passed` payload could publish an unacceptable result.
5. The quality gate had no object-level checks for building integrity, repeated-object density, entrance reachability, or runtime-scale composition.

## 3. Goals

- Produce a medium, top-down, modern-pixel-art spring village that is usable as an actual Unity game map.
- Preserve editable Tilemaps for grass, paths, water, banks, and bridge terrain.
- Preserve complete silhouettes for six buildings through object assets and Prefabs.
- Make walkability, collision, building entrances, optional road connectivity, and optional bridge traversal explicit contracts.
- Require user approval at the art-direction sample and assembled-map preview stages.
- Prevent stale approval from authorizing changed assets or placement.
- Preserve rejected evidence and make rejection visible in run state and reports.

## 4. Non-goals

- No interior scenes, NPCs, player controller, spawn implementation, or teleport runtime code.
- No package installation or Unity upgrade.
- No deletion of the rejected output bundle or its generated Unity assets.
- No requirement that all roads connect unless the user selects that policy.
- No requirement that opposite sides of water be mutually reachable unless a traversable bridge is declared.
- No fixed Tile count, atlas-page count, or decorative-prop quota.

## 5. Runtime asset model

### 5.1 Terrain Tilemaps

Terrain contains only subjects that can safely repeat or connect on the cell grid:

- grass and restrained grass variation;
- path straights, turns, junctions, and borders;
- water center and compatible banks;
- bridge deck and approaches when a bridge is requested;
- optional farm soil/crop terrain when it is genuinely grid-repeatable.

Terrain generation is demand-driven. An atlas may contain fewer than 16 Tiles or use multiple pages only when the declared terrain set requires them. Buildings, large trees, complete fences, signs, and other collision-critical objects are forbidden from terrain atlas slots.

### 5.2 Building assets

Each entrance corresponds to one complete building asset and one Unity Prefab. The six-building art plan is:

- one inn;
- one shop;
- one player home;
- three village homes sharing architectural language but differing in palette and decoration.

Every building definition contains:

- stable building and asset IDs;
- source image path and content hash;
- pixel dimensions and pixels per unit;
- world/grid anchor;
- occupied footprint;
- render-order policy;
- collision outline or grid blockers;
- one doorway opening and entrance anchor;
- target scene and target spawn metadata.

The doorway must be outside the collision outline and touch a walkable cell. A building is one runtime object even if its footprint spans many cells.

### 5.3 Prop objects

Trees, rocks, flower clusters, short fence segments, lamps, signs, and similar objects use an object layer. Each prop definition declares anchor, display size, collision role, and repeat policy. Large, wide, tall, or collision-bearing objects are generated one by one or in a compatible non-square pack; they are never forced into compact square Tile slots.

Continuous terrain-like fences may instead use a dedicated strip or Tile set when the design needs them to connect.

### 5.4 Unity hierarchy

The imported root contains:

```text
spring-creek-village
|-- Grid
|   |-- Ground
|   |-- Paths
|   |-- Water
|   `-- Bridge (only when declared)
|-- Buildings
|-- Props
`-- Metadata
```

`Buildings` and `Props` contain Prefab instances. `Metadata` contains entrance, collision/traversal, approval, and import-report TextAssets or project-native equivalents. The importer remains idempotent and updates existing instances without duplicating them or changing stable resource GUIDs.

## 6. Request and policy contracts

### 6.1 Road connectivity

The request declares one `road_connectivity_policy`:

- `required`: all declared primary-road cells must form one connected component;
- `partial`: validate only explicitly declared endpoint or segment relationships;
- `none`: do not enforce global road connectivity.

The planner must ask the user for this policy when the map includes roads and the request does not already provide it. It must not silently assume full connectivity.

### 6.2 Water and bridge traversal

Water defaults to non-walkable and colliding. Bridge traversal checks are conditional:

- when no traversable bridge is declared, no cross-water reachability or bridge-width requirement applies;
- when a traversable bridge is declared, its deck and approaches must connect the declared banks, be walkable, and satisfy the declared minimum traversal width;
- the minimum width applies to that traversable crossing and its approach corridor, not to every road or path on the map.

The bridge contract records orientation, span, approach endpoints, traversable flag, and minimum traversal width. A traversable bridge requires an integer minimum width of at least one cell; a non-traversable or absent bridge ignores that field.

### 6.3 Approval records

There are exactly two user approval gates:

1. `style-sample` approval binds to the style-sample image hash and art-direction manifest hash.
2. `assembled-map` approval binds to the runtime-composed preview hash, placement hash, collision/traversal hash, and asset-set hash.

Approval records contain schema version, gate ID, artifact hashes, approval status, timestamp, and `reviewer: user`. Validation rejects missing approvals, agent-authored approvals, non-passed approvals, unexpected gate IDs, and any hash mismatch.

After an explicit user response, the agent may serialize that decision into an approval record with `reviewer: user`. It cannot originate an approval, mark a gate passed from its own visual judgment, or infer approval from conversational silence.

### 6.4 Rejection records

A rejected run retains all artifacts and adds a versioned rejection record containing run ID, rejected artifact hashes, reason codes, user-provided reason, and timestamp. Its job state becomes `rejected`; the original final quality report and asset manifest remain immutable historical evidence. Validation and import check the rejection record before trusting those historical reports. A rejected run cannot be imported or treated as a source for a replacement run.

## 7. Workflow

1. Collect gameplay, style, scale, engine, road policy, and conditional bridge requirements.
2. Plan and route image generation before producing images.
3. Generate one small in-world style sample showing grass, path, water, bridge, and one complete cottage at the intended gameplay scale.
4. Stop at `style-sample`; continue only after explicit user approval bound to its hashes.
5. Generate the minimal terrain Tile set, six complete transparent building assets, and a restrained prop set using the approved sample as visible reference.
6. Run internal asset checks. Retry or reclassify failed assets without asking for per-asset approval.
7. Create layout, footprints, collision, entrances, road-policy data, and conditional bridge traversal data.
8. Compose the map preview exclusively from the actual runtime assets and placement data.
9. Produce both a whole-map view and a 1:1/gameplay-scale crop. Stop at `assembled-map` for explicit user approval.
10. Validate approval hashes and all deterministic gates, then publish atomically.
11. Import and place the final bundle in the current Unity scene, save, capture evidence, and repeat import to prove idempotency.

## 8. Quality gates

### 8.1 Asset checks

- Terrain Tile images have compatible declared edges and contain no complete buildings or scene fragments.
- Building and prop images contain usable alpha, no text or watermark, no clipped required silhouette, and dimensions consistent with their declared display scale.
- Complete buildings have one connected primary silhouette and one declared doorway; they are not assembled by repeating façade fragments.
- No generated sheet mixes compact decoration with buildings, bridges, platforms, long fences, or other collision-critical subjects.

### 8.2 Layout and gameplay checks

- Building footprints and collision outlines stay in bounds and do not overlap each other.
- Every declared entrance lies at its building doorway, is non-colliding, and reaches its declared path or nearby walkable area.
- Road connectivity follows the selected `road_connectivity_policy` only.
- Water is non-walkable unless covered by a declared traversable crossing.
- Bridge connectivity and minimum corridor width are checked only for a declared traversable bridge.
- Object placement enforces configurable repetition and density limits; identical props cannot form unapproved mechanical borders or large repeated blocks.
- Required walkable cells, entrances, bridge approaches, and collision blockers agree across placement, preview, runtime metadata, and Unity import data.

### 8.3 Visual checks

Internal visual checks verify scale consistency, natural spacing, readable entrances, absence of visible grid seams, and correspondence between individual assets and the composed map. These checks cannot replace the two user approvals.

The assembled-map gate shows:

- the whole runtime-composed map without debug overlays;
- a gameplay-scale crop;
- an optional collision/path overlay as separate evidence, never baked into the accepted art.

## 9. Failure handling

- A failed asset is retained with prompt and failure reason, then regenerated or reclassified to the correct asset strategy.
- A failed style sample returns to the style-sample stage and invalidates no later data because later generation has not started.
- Any asset or placement change after assembled-map approval invalidates that approval and requires a new preview.
- A failed deterministic gate cannot be overridden by visual approval.
- A rejected or unapproved run cannot invoke Unity Import and Place.
- Unity failures preserve the published bundle, report the importer error, and do not delete existing scene objects or assets.

## 10. Tests

### 10.1 Python contract and processing tests

- Terrain definitions reject building semantic roles and complete-building assets.
- Building definitions round-trip footprints, anchors, collision outlines, doorway anchors, and target metadata.
- Road policy validates `required`, declared `partial` relationships, and `none` independently.
- Bridge width and reachability checks run only when `traversable` is true.
- Entrance reachability, footprint overlap, out-of-bounds placement, and object density failures block publication.
- Runtime preview hashes change when assets or placement change.

### 10.2 Approval and publication tests

- Missing, agent-authored, stale, failed, extra, or hash-mismatched approvals block publication.
- Both correct user approvals are required.
- Rejected state blocks validation, publication, and Unity import.
- Quality reports distinguish deterministic checks, internal visual checks, and user approvals.

### 10.3 Skill contract tests

- The Skill asks for road connectivity policy rather than assuming it.
- The Skill applies bridge width only to declared traversable bridges.
- The Skill forbids buildings in repeatable terrain atlases.
- The Skill stops at both user approval gates and forbids agent-authored approval payloads.
- The Skill uses actual runtime assets for the assembled preview.

### 10.4 Unity Editor tests

- Terrain Tilemaps and object roots import with expected hierarchy and collision behavior.
- Six building Prefabs retain unique asset/instance IDs and doorway metadata.
- Repeat import updates exactly one scene root and preserves GUIDs.
- Rejected or unapproved manifests are refused.
- Scene save and import report contain the accepted preview and approval hashes.

## 11. Migration and recovery sequence

1. Add a rejection record for `spring-creek-village-20260803` and update its state/report without deleting evidence.
2. Deactivate its placed Unity root while retaining Prefabs and generated assets.
3. Extend contracts and validators for hybrid terrain/object maps, policies, approvals, and rejection.
4. Update `forge-2d-map` instructions and contract tests.
5. Extend processing, publication, and Unity importing.
6. Forward-test the revised Skill against the rejected scenario using isolated artifacts.
7. Start a new run ID; do not reuse any rejected atlas, placement, preview, or approval file.
8. Stop for user approval at the style sample and assembled-map preview.

## 12. Acceptance criteria

The recovery is complete only when:

- the rejected run is visibly rejected and inactive in Unity;
- the revised Skill and validators prevent its failure mode;
- all repository and Unity tests pass;
- the new run uses no old generated visual asset;
- the user approves the current style sample;
- six complete building objects, minimal terrain Tiles, and restrained props compose a coherent playable village;
- the user approves the current assembled map and gameplay-scale crop;
- published hashes match approved hashes;
- Unity imports one clean, saved, idempotent scene root with correct collision and entrance metadata.
