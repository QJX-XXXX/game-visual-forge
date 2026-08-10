# Processing and quality

## Contents

- [Tool discovery and source](#tool-discovery-and-source)
- [Sampling and cleanup](#sampling-and-cleanup)
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

Trim transparent bounds per frame, compute a stable bottom-center/feet anchor,
and place every frame on one canvas with one scale policy. Pixel mode uses
nearest-neighbor resizing. HD mode uses high-quality resampling.

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
images, empty visible content, out-of-canvas content, fully opaque requested
transparency, visible direct-chroma residue, and manifest path/hash mismatches.
Direct chroma cleanup tolerates small codec color drift, and the residue check
blocks significant remaining key color before publication.

Direct chroma cleanup uses the declared RGB key with tolerance 80 to absorb
codec drift, clears hidden RGB on transparent pixels, and uses premultiplied
alpha for HD resampling. Pixel mode remains nearest-neighbor. The deterministic
`chroma-residue` check examines every delivered frame at every requested density;
more than 1.0% visible near-key pixels in any frame fails publication.

Temporal metrics report exact and near duplicates, motion coverage, static
intervals, bounds and area variation, anchor jitter, loop difference, alpha
coverage, clipping risk, background change, and flicker. These metrics can set
`needs_attention`; they do not decide whether a deliberate hold or impact frame
is semantically correct.

The final review checks identity, clothing/colors/equipment, action and
direction, timing, start/end pose, anatomy, camera lock, drift, cleanup, edge
quality, loop continuity, text/watermarks, and semantic duplicates. The review
record binds all displayed artifacts and the quality report by hash. A current
approved record is required for atomic publication.
