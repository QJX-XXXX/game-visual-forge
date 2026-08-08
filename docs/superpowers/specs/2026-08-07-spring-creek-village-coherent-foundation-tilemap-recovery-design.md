# Spring Creek Village Coherent Foundation Tilemap Recovery Design

Date: 2026-08-07

## Status

Approved in conversation for one final implementation attempt. Runs v2, v3, and v4 remain immutable rejected evidence and must not be imported into Unity.

## Problem

The previous hybrid runs generated terrain Tiles, a bridge, and buildings independently. Their visual boundaries did not share a common composition, so riverbanks, bridge approaches, paths, building footprints, and surrounding ground read as incorrectly assembled puzzle pieces. Replacing individual Tiles did not solve the systemic mismatch.

## Goal

Produce a playable medium top-down healing-style RPG village in `2DMirrorDemo` with coherent spring terrain, a north-south creek, one east-west traversable wooden bridge, six distinct village buildings, collision, walkable ground, and building entrance hooks.

## Chosen Architecture

Use a coherent-foundation Tilemap:

1. Generate one foundation-only map image at exactly 768×576 pixels.
2. The foundation contains stable terrain only: grass, flowers, paths, the north-south creek, both riverbanks, the complete east-west bridge, and six prepared building pads with path connections.
3. The foundation contains no buildings, trees, signs, actors, labels, UI, or other runtime-controlled tall objects.
4. Slice the accepted foundation into a 16×12 grid of unique 48×48 Tiles. Every adjacent Tile comes from the same source image, so visible seams preserve the original continuous image.
5. Import the slices as a Unity Tilemap. The Tiles are map-specific and are not required to be reusable autotiles.
6. Keep six buildings as separate transparent Sprite/Prefab objects. Their declared footprints, doorway cells, sorting orders, collision cells, and interior hooks remain independent from the visual foundation.
7. Keep water blocking, bridge traversal, entrances, and walkable-space validation as semantic grid data independent from the pixels.

## Art Direction

- Modern pixel-inspired top-down RPG art.
- Spring daylight, tender green grass, sparse wildflowers, light blue water, warm timber and roof colors.
- Buildings use timber frames, pale plaster walls, and warm tiled roofs.
- The previously approved style sample remains the art-direction reference.
- All new visible art uses built-in image generation. Scripts may crop, remove backgrounds, resize, slice, assemble, and validate but must not procedurally draw final creative art.

## Layout Contract

- Canvas: 768×576 pixels.
- Grid: 16×12 cells.
- Tile size: 48×48 pixels.
- Creek: north-south, visually continuous, blocking by default.
- Bridge: east-west, visibly integrated into both banks, traversable, with at least one 48-pixel-wide player route.
- Roads: global connectivity is not required. Only declared entrance and bridge approaches are validated.
- Buildings: one inn, one shop, one player home, and three visually distinct villager homes.
- Each building pad must visually connect its doorway to adjacent walkable ground without a hard rectangular grass patch or mismatched texture border.

## Generation Flow

1. Reuse the approved style sample and art-direction record.
2. Generate a foundation-only image with the fixed layout and empty building pads.
3. Internally reject any foundation containing buildings, visible tile-grid seams, disconnected bridge approaches, malformed riverbanks, text, or watermarks.
4. Slice the accepted foundation into unique Tiles and compose a lossless round-trip preview. The recomposed preview must pixel-match the foundation.
5. Generate the six building sprites with the approved style reference and declared footprints.
6. Assemble buildings over their prepared pads and produce the map, gameplay crop, and collision previews.
7. Request the existing `assembled-map` approval only after deterministic validation and visual inspection.
8. After approval, publish the bundle and import its Tilemap Prefab plus building objects into the current `2DMirrorDemo` scene.

## Contracts and Artifacts

The final bundle must contain:

- `foundation.png` and `foundation.prompt.txt`
- the 16×12 Tile atlas or equivalent Unity slice metadata
- `tilemap-placement.json`
- `tilemap-objects.json`
- `tilemap-collision.json`
- `building-entrances.json`
- `tilemap-preview.png`
- `tilemap-gameplay-crop.png`
- `tilemap-collision-preview.png`
- `map-quality-report.json`
- `asset-manifest.json`
- style and assembled approval records
- Unity import manifest and acceptance report

The manifest must identify the foundation source, all building sources, hashes, generated prompts, Tile slicing metadata, collision data, and approval records.

## Validation

Deterministic checks must verify:

- the foundation is exactly 768×576;
- the grid is exactly 16×12 at 48×48 pixels;
- slicing and recomposition are pixel-identical;
- all required artifacts exist and their hashes match;
- water cells are blocked except the declared bridge route;
- the bridge has continuous east-west walkability of at least one Tile;
- building sprites have alpha and match declared dimensions;
- building collision regions do not overlap each other or block their doorway cells;
- every doorway reaches adjacent walkable ground;
- no undeclared global road-connectivity requirement is enforced;
- the rejected v2–v4 run roots cannot be validated, published, or imported.

Visual review must reject:

- visible puzzle-like seams;
- bridge art that contains unrelated grass, water, or path fragments;
- rectangular or mismatched ground patches around buildings;
- floating buildings, blocked doors, inconsistent scale, unwanted text, or watermarks.

## Unity Result

Import into `I:/UnityProject/2DMirrorDemo`, scene `Assets/Scenes/SampleScene.unity`:

- one generated foundation Tilemap Prefab;
- a `Buildings` child containing six separate Sprite/Prefab objects;
- collision and entrance objects derived from the validated manifests;
- the previously rejected generated roots disabled or absent from the active scene;
- the new generated root active, saved, and covered by an import/acceptance report.

## Failure Handling

This is one final attempt under the new architecture. If the foundation or assembled result fails visual review, record an immutable rejection with the concrete reason and do not import or publish it. Do not resume patching individual bridge, bank, path, or grass Tiles from the rejected runs.
