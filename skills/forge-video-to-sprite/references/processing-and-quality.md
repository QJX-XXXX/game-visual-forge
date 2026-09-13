# Processing and quality

## Contents

- [Tool discovery and source](#tool-discovery-and-source)
- [Sampling and cleanup](#sampling-and-cleanup)
- [Canvas containment](#canvas-containment)
- [Artifacts](#artifacts)
- [Quality and review](#quality-and-review)

## Tool discovery and source

Discover FFmpeg and FFprobe in this order: explicit command path, dedicated
environment variable, `PATH`, then documented Windows package locations. The
Skill never installs them. FFprobe JSON must contain a decodable video stream,
positive dimensions and duration. Rotation is normalized for display and audio
presence is recorded but audio is not exported.

Supported examples are MP4, MOV, and WebM; any format accepted by the selected
FFmpeg installation is allowed after probing. The source path stays immutable
and its SHA-256, container, codec, dimensions, rotation, duration, frame rates,
VFR state, frame count when known, audio state, and request fingerprint are
stored in `video-source-record.json`. Start/end trims are validated before any
frame output is written.

## Sampling and cleanup

Sampling uses presentation timestamps. Looping clips use `[start,end)` so the
endpoint does not duplicate the first pose. Non-looping clips include both
endpoints when more than one frame is requested. When multiple densities such
as 8, 16, 24, and 48 are requested, extract the highest density once and derive
the lower densities from that ordered timeline.

Background modes are explicit:

- `preserve` keeps the source background;
- `chroma` requires a declared RGB key color;
- `rembg` tries CUDA then CPU and may use Chroma fallback only when a valid key
  color was declared. If removal fails without a valid fallback, mark the run
  as needing attention instead of claiming transparency.

For the default `tight` layout, trim transparent bounds per frame, compute a
stable bottom-center/feet anchor, and place every frame on one canvas with one
scale policy. For `reference-locked`, keep each cleaned frame's full source
coordinates, derive scale and the feet anchor from the first frame only, and
reuse that placement for every frame. Require identical source dimensions and
leave out-of-canvas pixels visible to the clipping-risk check instead of
silently rescaling them. Pixel mode uses nearest-neighbor resizing. HD mode
uses high-quality resampling.

## Canvas containment

`VideoSpriteRequest` exposes `canvas_policy` (`strict` or `report-only`) and a
normalized `safe_frame_margin` in `[0, 0.5)`. Strict is the default for game
Sprites and uses `0` by default: the complete canvas is allowed, so content
may approach or touch an edge. A positive margin is an optional guard band,
not a mandatory rejection threshold. The half-open safe rectangle is:

```text
left   = ceil(width  * safe_frame_margin)
top    = ceil(height * safe_frame_margin)
right  = floor(width  * (1 - safe_frame_margin))
bottom = floor(height * (1 - safe_frame_margin))
```

Foreground bounds use alpha >= 8. The quality report records per-frame
`frame_bounds`, along with `safe_frame_bounds`, `swept_bounds`, `minimum_margin`,
`edge_contact_frames`, `out_of_safe_frame_frames`, and
`source_edge_contact_frames`. The last field is measured on the cleaned source
before `tight` trimming so a cropped weapon cannot be hidden by recentering the
remaining pixels; any such contact drives `minimum_margin` to zero. Every
requested density is checked; the highest-density timeline remains the
canonical temporal metric source.

An evaluated strict violation produces the deterministic `canvas-containment`
failure and blocks publication. A strict `preserve` background is likewise a
hard failure because it has no foreground mask. `report-only` records the same
evidence as `needs_attention` and can proceed only through intentional manual
review. Edge contact is not a violation when the visible bounds remain within
the declared safe rectangle; it is recorded as `needs_attention` so review can
distinguish a border touch from evidence of cropped source content. Source-edge
contact is also a review warning, not an automatic margin failure.

## Artifacts

The staging run records raw/clean/delivery frames, per-density strips and
sheets, GIF previews, frame timing, processing metadata, source provenance,
quality report, and review evidence. Required review evidence includes:

- timestamped contact sheet;
- motion-difference image;
- anchor/bounds diagnostic;
- transparent or preserved preview GIF;
- selected strips and sheets.

Only requested runtime formats and required provenance/quality evidence move to
the final output. Raw evidence may remain in the staging run.

## Quality and review

Deterministic blocking checks cover source/request/attempt/model/artifact hash
mismatches, missing or unordered frames, wrong counts or dimensions, corrupt
images, empty visible content, the `canvas-containment` safe-frame gate,
out-of-canvas content, fully opaque requested transparency, visible direct-
chroma residue, and manifest path/hash mismatches.
Direct chroma cleanup tolerates small codec color drift, and the residue check
blocks significant remaining key color before publication.

Direct chroma cleanup uses the declared RGB key with tolerance 80 to absorb
codec drift, clears hidden RGB on transparent pixels, and uses premultiplied
alpha for HD resampling. Pixel mode remains nearest-neighbor. The deterministic
`chroma-residue` check examines every delivered frame at every requested density;
more than 1.0% visible near-key pixels in any frame fails publication.

Temporal metrics report exact and near duplicates, motion coverage, static
intervals, bounds and area variation, anchor jitter, loop difference, alpha
coverage, clipping risk, background change, flicker, safe-frame bounds, swept
bounds, per-frame bounds, edge-contact indexes, source-edge indexes, and
minimum margin. `temporal_metrics.frame_bounds` is the highest-density
timeline; lower-density containment evidence is under
`canvas_containment.densities`.
Reference-locked runs also record the immutable reference bounds and draw them
alongside the safe rectangle and swept bounds in the anchor diagnostic. These metrics can set
`needs_attention`; they do not decide whether a deliberate hold or impact frame
is semantically correct. `clipping_risk` is a broad historical signal; the
deterministic `canvas-containment` check is the publication gate.

The final review checks identity, clothing/colors/equipment, action and
direction, timing, start/end pose, anatomy, camera lock, drift, cleanup, edge
quality, loop continuity, text/watermarks, semantic duplicates,
`no-canvas-clipping`, and `equipment-in-safe-frame`. The review record binds
all displayed artifacts and the quality report by hash. A current approved
record is required for atomic publication; it cannot override a failed
deterministic containment check.
