# H3 Sprite Workflow Reliability Design

## Goal

Make a local MiniMax H3 FL2VA workflow produce reproducible, game-ready
character action frames without upgrading ComfyUI or downloading models. The
result must preserve the character's screen position and effective scale while
long weapons or projectiles move during an attack.

## Scope

This change covers the versioned Game Visual Forge video-Sprite pipeline, the
public `forge-video-to-sprite` Skill, and one explicitly selected local ComfyUI
workflow. It adds deterministic validation and provenance for the local H3
route, plus a reference-locked layout mode for extracted frames.

It does not change a game project, install or update ComfyUI, install custom
nodes or models, submit a generation, or alter hosted-provider behavior.

## Current evidence

The selected workflow's `MiniMaxH3ImageToVideo` node exposes both
`first_frame` and `last_frame`. Its current first-frame image is connected only
to `first_frame`; the `last_frame` input is disconnected. The H3 prompt asks
the character to return to the opening pose, but there is no image condition at
the end of the clip.

The current video delivery code derives one scale from the largest alpha bounds
across every frame and then crops and re-centres every frame independently.
Consequently a long bow, a held arrow, or a generated projectile can change the
character's apparent size and horizontal position even when the source camera
does not move.

## Design

### H3 keyframe policy

The selected workflow will use the already-present `last_frame` input. The
same ready-pose image used by `first_frame` will also feed `last_frame`, making
the clip FL2VA rather than first-frame-only I2V. The prompt will describe the
entire generated duration, return to ready pose before the final hold, and
state that the supplied final image is the exact end-pose condition.

The workflow will use a fixed seed and a 124-frame H3 length (the `17k + 5`
form, approximately five seconds at 24 fps). A sprite request may still select
its three-second action interval during PTS sampling; the remaining generated
time is a final ready-pose hold needed for a stable terminal keyframe. The
workflow is inspected before use for a connected first frame, connected last
frame, fixed seed, a valid H3 length, and no Cloud or partner/API nodes.

The Forge repository will provide a pure-Python inspection and generation
record utility. It will read a workflow JSON without modifying it, report the
H3 keyframe and seed state, and create a sanitized record containing the
request fingerprint, workflow SHA-256, prompt SHA-256, reference paths and
hashes, selected model, sampling settings, `prompt_id`, terminal state, and
immutable output video hash. Credentials, signed URLs, Base64 media, and raw
Comfy responses remain prohibited.

### Reference-locked Sprite layout

`VideoSpriteRequest` will gain `layout_mode`, with the existing alpha-tight
layout as the backwards-compatible default and `reference-locked` as the new
game-character option.

For `reference-locked`, cleaning retains every source frame's full image
coordinates. The cleaned first frame supplies a single alpha reference bounds
rectangle. Its width and height determine one global scale; its center and
bottom determine one global placement on every delivery canvas. Each source
frame is resized as a whole and composited at that one placement. No later
frame's bow, arrow, projectile, or extremity can alter character scale or
placement.

All source frames must have the same dimensions in this mode. Frames that
extend beyond the delivery canvas remain detectable as clipping risk instead of
being silently re-scaled to fit. The generated projectile is still considered
temporary artwork: game implementations should create the actual flying arrow
as an independent game projectile after the release frame.

The existing `feet` anchor remains the default. For reference-locked frames it
means the bottom of the first-frame visible reference is placed at the existing
bottom safety margin; it does not mean the bottom of a later arrow or bow.

### Quality evidence

Quality reports will retain the existing alpha-bound metrics, and additionally
record the requested layout mode and the reference bounds used by the delivery
pass. Anchor diagnostics will draw the immutable reference anchor alongside
per-frame visible bounds, making weapon expansion distinct from character
placement.

The existing chroma route remains available. Its H3 game-sprite profile will
use chroma cleanup after sampling and must continue to pass the all-density
visible-residue gate. This design does not add an unreliable attempt to
semantically remove an arrow from a character frame.

### Skill behavior

`forge-video-to-sprite` will provide a concise local H3 game-character profile:

- Use FL2VA with the same ready-pose image connected to first and last frames
  when an attack must return to a tower, platform, or other fixed location.
- Use a fixed seed, a valid `17k + 5` H3 length, a complete-duration prompt,
  and a PTS-selected delivery interval.
- Use one static source image for a no-motion idle; do not generate an H3
  video solely to simulate a standing idle.
- Use `reference-locked` layout for stationary character actions with extending
  props, and visually review the release frame before accepting the clip.
- Treat a flying projectile as runtime-owned after release; reject a clip when
  a malformed or duplicated held projectile changes the character anatomy.

The Skill continues to require explicit source and generation confirmation and
continues to prohibit automatic resubmission.

## Interfaces

`VideoLayoutMode` has values `tight` and `reference-locked`.

`VideoSpriteRequest.layout_mode` defaults to `VideoLayoutMode.TIGHT`. Existing
serialized requests with no field keep their current output behavior.

`inspect_comfy_h3_workflow(workflow: dict[str, Any]) -> ComfyH3WorkflowReport`
returns check results and normalized H3 settings without changing a workflow.

`ComfyH3GenerationRecord` serializes only deterministic provenance and recovery
state. Its output fields are optional until a local job reaches a known terminal
state; it validates SHA-256 digests whenever a path or digest is supplied.

## Validation

Tests will prove that:

1. legacy video requests keep `tight` layout;
2. reference-locked delivery retains the first-frame scale and bottom-center
   placement while a later frame has a much wider weapon;
3. reference-locked mode rejects mixed source dimensions and preserves clipping
   evidence;
4. workflow inspection accepts a local, fixed-seed FL2VA graph and rejects a
   disconnected last frame, a randomized seed, invalid H3 length, or an API
   node;
5. generation records reject malformed digests and do not serialize secrets;
6. the public Skill and its contract test document static idle, FL2VA,
   reference-locked layout, runtime projectile ownership, and recovery rules.

The selected local workflow will be re-read after the tail link and deterministic
settings are applied. If ComfyUI is running at that point, it will be validated
through the local Comfy MCP; otherwise the report will distinguish JSON
inspection from live-node validation.
