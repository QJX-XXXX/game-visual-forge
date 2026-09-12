# H3 Character Animation Quality Profile

## When to use

Read this reference only for a local `comfyui-h3` request that produces a 2D
game character or Sprite animation. Do not apply it to an existing-file-only
processing run, hosted video provider, map, audio, or general-purpose video.

## Prompt assembly

Keep the exact mode-specific alignment line required by the H3 Prompt Writing
Skill first, with no preamble. Then use the fields in this order:

1. `integrated_multimodal_description` contains the shared quality block,
   followed by the character identity, defining equipment, action timeline,
   camera, and delivery-specific constraints.
2. `overall_soundscape` describes only the requested soundscape.
3. `non_diegetic_music` describes only the requested non-diegetic music.

The quality and identity blocks below are composed with the action description
inside `integrated_multimodal_description`; they are not appended as a
separate prompt format and do not change the H3 Prompt Writing Skill's field
names or order.

### Canonical quality prefix

Use this reusable English block as the canonical quality prefix, allowing only
grammatical joining to the character description:

> Crisp, high-detail stylized 2D game-Sprite animation with clean hard-readable outlines and stable fine details. Render every frame as an individually readable game frame with no motion blur, smear, defocus, temporal ghosting, frame blending, low-detail redraw, shimmering edges, or compression-like blocks.

This block describes the desired output. It cannot repair detail that the
source video never contained, so final visual review remains mandatory.

### Identity and equipment lock

Replace every bracketed value in this parameterized block with the actual
character facts before submitting a prompt:

> The defining [equipment or prop] shown in <Picture 1> is a mandatory identity prop. It remains attached to the same [hand or body location] throughout the action, with its complete visible shape readable inside the canvas. Never remove, hide, shorten, blur away, duplicate, mirror, detach, morph, or replace it. Do not use a global `No weapons` constraint when this prop is part of the character; use `No extra weapons` only when needed.

The character identity, silhouette, palette, and defining equipment must stay
stable across frames. Preserve the complete prop inside the frame. Derive the
frame margin from the source composition so the prop is not cropped; a fixed
margin that cuts off a large prop is invalid.

## Mode selection

I2VA and FL2VA are action-level choices, not universal quality switches. Use
the following matrix and justify the choice by the required end pose and the
current visual review:

| Need | Preferred mode | Required review |
|---|---|---|
| One opening frame develops into a collapse/death | I2VA | final pose, identity, timing, and semantic action |
| Exact opening and exact return pose for a loop | FL2VA | first/last pose, loop difference, identity, and timing |
| Attack recovery to a ready stance | FL2VA by default; I2VA only as a reviewed clarity candidate | complete equipment, recovery pose, no blur or weapon omission |

For I2VA, describe how the approved opening frame develops into the ending
without requiring an exact final keyframe. For FL2VA, connect the continuous
action between the approved first and last frames; use the same approved source
when an exact return pose is intended. An I2VA candidate may be preferred for
clarity only after its ending pose, loop difference, identity, and action
semantics pass visual review. Never switch modes solely because one sample
happened to look sharper.

## Reproducibility

Use a fixed H3 seed for every local character run. The seed controls the
initial random state, but it does not guarantee identical output across model,
software, hardware, or prompt changes.

Before submission, bind the prompt, reference image, workflow, model,
resolution, duration, steps, and seed. Preserve the existing provenance hashes
for the prompt, reference, workflow, model, and output video, together with
the Comfy `prompt_id`. The generated video must remain tied to its fetched
video hash and to the same run record; do not silently substitute another
candidate.

## Visual review and failure handling

Review the current candidate for, at minimum:

- character identity and defining equipment;
- action semantics, direction, and camera lock;
- crisp edges, readable fine details, and absence of blur or ghosting;
- transparency cleanup, clipping, and complete in-frame equipment;
- frame semantics, timing, and loop/end pose where applicable;
- absence of text, watermarks, or extra characters.

Automatic checks are evidence, not semantic proof. A failed candidate stays in
its isolated run and is neither published nor silently substituted. Revise the
prompt or mode only in a new run after the failure is understood. Do not add
an uncalibrated hard sharpness threshold; manual visual review remains the
semantic gate.
