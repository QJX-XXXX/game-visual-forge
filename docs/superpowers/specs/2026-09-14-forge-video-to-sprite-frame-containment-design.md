# Forge Video to Sprite Frame Containment Design

## Decision

Make canvas containment a first-class contract for game-oriented video-to-
Sprite processing. A generated or existing clip is not delivery-safe merely
because its post-cleanup image can be composited onto a canvas: the complete
foreground silhouette, defining equipment, and the full motion sweep must
remain inside an inset safe frame for every delivered frame.

The request contract gains a `canvas_policy` and a normalized
`safe_frame_margin`. The default policy is `strict` and the default margin is
`0.05`, which is compatible with the existing `fit_scale=0.88` baseline while
leaving a measurable guard band. `report-only` is available for preserved
background or non-game review runs, but it never converts an unsafe result into
a passing containment claim. Strict policy requires a positive margin.

The quality report gains a top-level `canvas_containment` object. It records
the policy, margin, per-frame foreground bounds, safe rectangle, union (swept) bounds, the
minimum observed normalized margin, delivery edge-contact frames, frames that
leave the safe rectangle, source frames whose cleaned foreground already
touches an original image edge, and whether the foreground was automatically
evaluable. A strict, evaluable violation is a deterministic failure and blocks
publication. An unevaluable preserved-background run is `needs_attention` and
requires the existing manual review; it is not silently treated as clean.

## Containment semantics

The safe rectangle is represented with half-open pixel coordinates:

```text
left   = ceil(width  * safe_frame_margin)
top    = ceil(height * safe_frame_margin)
right  = floor(width  * (1 - safe_frame_margin))
bottom = floor(height * (1 - safe_frame_margin))
```

Visible foreground bounds use alpha values of at least 8, so a negligible
resampling halo does not create a false edge contact. A frame violates the
safe frame when its visible bounds extend below `left`/`top` or beyond
`right`/`bottom`. Edge contact is recorded independently, including the
original cleaned source bounds before `tight` trimming. This preserves evidence
that a source weapon was cropped even when tight layout later recenters the
remaining pixels.

The swept bounds are the union of all visible delivery-frame bounds. The
minimum margin is the smallest normalized distance from a visible bound to any
canvas edge; source-edge evidence sets it to zero. Empty frames remain invalid through the existing empty-content
checks. Preserved backgrounds are marked `foreground_evaluable=false` because
the full opaque image is not a foreground mask; their containment status is a
strict deterministic failure unless a caller explicitly chooses `report-only`,
which records `needs_attention`.

Containment is checked for every requested density. The highest-density
temporal metrics remain the canonical motion metrics, while the report stores
per-density containment evidence and per-frame foreground bounds so a modified
lower-density frame cannot be hidden by a clean high-density sample.

## H3 prompt contract

The H3 prompt profile remains owned by the H3 Prompt Writing Skill for exact
alignment-line and field ordering. The Forge profile adds only the game-safe
composition constraints inside `integrated_multimodal_description`: keep the
entire character, shield, weapon, projectile origin, and the farthest point of
the complete attack sweep inside the declared safe frame; use a locked static
camera; and reject any motion that would require cropping, zooming, panning,
or an out-of-frame weapon tip. The canonical crisp-outline, no-blur,
no-smear, no-defocus, no-ghosting constraints remain unchanged.

## Review contract

Manual review must include `no-canvas-clipping` and
`equipment-in-safe-frame` checks in addition to identity, action, timing,
transparency, and edge quality. `approved=true` cannot override a failed
deterministic containment check. A failed candidate remains isolated and must
be regenerated or reframed in a new run.

## Compatibility and scope

- Existing reports without `canvas_containment` deserialize with an empty
  object.
- Existing requests without the new fields use the strict 5% safe-frame
  default; preserved-background quality checks are explicitly unevaluable and
  therefore blocked by strict publication.
- The schema version remains `1`; the additions are backward-compatible
  fields.
- No ComfyUI installation, model, custom node, global workflow, asset, or
  project-local absolute path is changed.
- No automatic sharpness threshold is introduced. Containment is geometric;
  identity and action semantics remain manual visual-review concerns.
