# Processing and quality

Raw provider output and user source files are immutable. Every processed candidate is written to a separate staging directory and binds the request fingerprint, source hash when present, candidate hash, processed WAV hash, waveform hash, and spectrum hash.

The published format is Microsoft WAV, 44,100 Hz, 16-bit signed PCM, mono or stereo according to the confirmed usage and Unity profile. The workflow does not upsample to 48 kHz and does not publish MP3 previews.

For non-looping text-to-audio requests with the one-shot usage profile, normalize the converted staging WAV to a -1.0 dBFS sample peak before preview generation. Skip silent or already clipped input so silence remains reviewable and clipping remains a hard-failure signal. Do not apply peak normalization to raw files, redraw, inpaint, continue, UI, scene, or looping-ambience output.

For one-shots, remove only bounded leading silence and pad or trim the tail to the confirmed duration. For inpainting, convert both source and generated audio to the common PCM format, preserve source samples outside the edit region plus 20 ms guards, and crossfade only inside the guards. For continuation, preserve the converted source prefix before the final 20 ms guard, crossfade into the generated continuation, and enforce the exact target duration. For loops, analyze a 50 ms boundary and apply a 20 ms wrap crossfade without changing sample count.

Hard failures include decode or format mismatch, wrong duration, empty output, clipping, missing previews, stale hashes, failed protected-region comparison, and missing loop evidence when looping is requested. Speech/music detection is advisory only; the user must still complete the semantic listening check.

Unity profiles are explicit: UI uses mono PCM with preload; one-shots use low-latency PCM or ADPCM without looping; 3D scene sounds use mono; long looping ambience uses stereo Vorbis streaming. The UPM importer writes only under `Assets/GameVisualForgeAudio/<asset-id>/`, preserves existing GUIDs on repeat import, and writes `Reports/unity-import-report.json`. Scene placement is outside the package and occurs only through Unity MCP after an explicit user request.
