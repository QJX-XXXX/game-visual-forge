# Audio One-Shot Peak Normalization Design

## Goal

Make locally generated one-shot sound effects consistently audible without
changing their character, masking clipping, modifying raw provider output, or
altering source-preserving audio modes.

## Scope

Peak normalization applies only when all of these conditions are true:

- mode is `text-to-audio`;
- usage profile is `one-shot`;
- the request is not a loop;
- the staging file is readable, non-silent 44,100 Hz 16-bit PCM;
- the converted staging file contains no clipped samples.

The target peak is exactly `-1.0 dBFS`. Raw candidates remain immutable.
`redraw`, `inpaint`, `continue`, UI sounds, scene sounds, and looping ambience
keep their current processing behavior.

## Processing Design

Add a focused PCM helper in `src/game_visual_forge/processing/audio.py`. It
reads the converted staging WAV with the existing PCM reader, computes the
largest absolute sample, derives the linear gain required for `-1.0 dBFS`,
scales every channel equally, clamps only for integer rounding safety, and
writes the same sample rate, channel count, frame count, and duration.

The helper returns without changing the file when the peak is zero or when the
input already contains a clipped sample. Skipping clipped input preserves the
existing hard-failure evidence instead of hiding it by attenuation.

For eligible output, `process_audio_candidates()` first applies `volume=-1dB`
during FFmpeg format conversion. This reserves headroom before full-scale
floating-point model output is quantized to PCM16. It then calls the helper
before duration validation and preview generation. Protected splicing remains
unaffected because normalization is not enabled for inpaint or continue.

## Quality and Failure Behavior

- Peak normalization is deterministic for identical PCM input.
- The normalized peak must be within one 16-bit sample of the `-1.0 dBFS`
  target.
- A silent candidate remains silent, retains its existing metrics evidence,
  and cannot be published without passing the listening gate.
- A clipped candidate remains clipped so the existing quality check fails it.
- No compressor, limiter, EQ, LUFS normalization, dithering, or channel remix
  is introduced.
- Preview waveform and spectrum files are generated from the normalized
  staging WAV.

## Tests

Add processing tests that prove:

1. a quiet generated one-shot reaches `-1.0 dBFS` within PCM rounding tolerance;
2. frame count, duration, sample rate, and channel count do not change;
3. the raw candidate hash and bytes do not change;
4. a UI request is not normalized;
5. silent input remains unchanged;
6. clipped input remains unchanged and the quality layer still reports clipping.

Run the focused audio tests, the complete repository test suite, and the Skill
validator. After those checks pass, generate three new 0.8-second blacksmith
strike candidates using the user-approved prompt. Only a candidate that passes
the six listening checks may be copied into `assets/readme/` and documented as
a successful README example.

## Documentation

Update `skills/forge-text-audio/references/processing-and-quality.md` with the
narrow normalization rule. Keep `SKILL.md` concise; add one sentence to its
processing step so agents know that generated one-shots have a deterministic
peak target and that source-preserving modes do not.

The English and Chinese READMEs receive the blacksmith prompt and artifact only
after user listening approval. Failed candidates and local run metadata remain
under ignored `outputs/` paths.
