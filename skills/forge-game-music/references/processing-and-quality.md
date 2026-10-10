# Processing and quality reference

## Source and staging rules

A generated or imported source is immutable. Processing writes a new staging file and records the source hash, processed hash, input sample rate, output sample rate, channel count, duration, and every requested transform. Safe repository-relative paths reject absolute paths, parent traversal, and output-directory escape.

The delivery default is 44,100 Hz, 16-bit signed PCM, stereo WAV. A sample-rate conversion improves compatibility; it does not create detail that was absent from the source. Keep the native source and codec information in provenance.

## Duration and loop modes

`natural` preserves the actual source duration. `trim` requires an explicit interval and never silently pads a short source. A loop request requires a start/end interval and evidence. The loop interval must be inside the source and use a positive length. By default crossfade is zero. If a positive crossfade is selected, blend equal-power end/start frames, record the rotation point and effective length, and re-check peak after rendering. Never call a processed file a seamless loop based only on file existence.

Loop evidence contains boundary metrics, a before/after audition slice, and three concatenated loop rounds. Human review decides whether beat, harmony, and reverb tails are acceptable. Continuous music is not evaluated with the SFX transient or dense-noise gate.

## Listening and publication gates

A music review is required before publication. It checks file readability, finite duration, no clipping after processing, expected channel/rate/format, vocal policy, musical artefacts, loop evidence when requested, provenance, and a stable fingerprint. Changing source bytes, processed bytes, loop evidence, or the quality report invalidates the old review. Unity output is an optional manifest that points to the selected WAV and does not create an AudioSource or mutate a scene.

## Sources

- Existing project audio contracts and FFmpeg processing — inspected 2026-10-10; SFX semantics are kept separate from music review.
- Existing Unity audio manifest importer — inspected 2026-10-10; music can use a manifest without scene mutation.
- [Stable Audio 3 prompt guide](https://kb.stability.ai/knowledge-base/stable-audio-3-prompt-guide) — verified 2026-10-10; supports instrumental prompt vocabulary.
