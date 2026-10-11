# Music prompt guide

This guide turns a game-music brief into a provider-neutral prompt package. It is intentionally small enough to read for one request; the scene templates are in `game-music-templates.md`.

## Caption structure

Use three layers, in this order:

1. **Global metadata** — purpose, scene, energy, duration target, loop intent, tempo range, tonal colour, and production quality.
2. **Vocal details** — `instrumental / no vocals` by default. A request may opt into vocals only when the user explicitly asks. Spoken words, chant, humming, choir, and non-lexical vocal texture all count as human voice for the default policy.
3. **Arrangement** — intro, thematic layers, development, peak, release, and outro. State instruments and transitions rather than naming a living artist or copying a song.

For `standalone-instrumental`, put `Instrumental, no vocals` in the caption and use an `[instrumental]` lyric section. Do not put lyrics, syllables, humming, choir, or voice instructions in the package. For a continuous `bgm-loop`, state that the full groove starts on beat one, remains present without an intro or low-energy section, and ends on the same rhythmic material; verify the seam after generation. If a seam is not clean, use a short instrumental cadence and normal ending rather than forcing a bad loop.

## Provider mapping

- **MiniMax Music 3**: send the structured caption and the instrumental lyric section. The local Comfy workflow owns duration, seed, sampler, tiled decode, and WAV save settings.
- **Stable Audio 3.0**: send an instrumental arrangement prompt. Treat lexical singing and requested lyrics as unsupported during preflight. The service may still produce non-lexical vocal-like texture, so listening review remains required.
- **Suno**: keep provider fields unresolved until the official account exposes its API documentation and commercial terms. Do not infer an instrumental, model, length, candidate, or task field from an unofficial client.

## Example package

```text
Global metadata: menu puzzle BGM; gentle forward motion; 90–110 BPM; warm, uncluttered mix; 180 seconds; loop candidate.
Vocal details: instrumental, no vocals.
Arrangement: soft marimba ostinato; felt piano motif; light plucked strings; low pad enters after 16 bars; small harmonic lift at the midpoint; return to the opening texture with a held tail for looping.
```

For a fast game loop, prefer `steady kick and bass pulse from the first beat`, `mid-register repeating motif`, `stable moderate loudness`, and `no sudden high note, impact, breakdown, voice-like texture, or fade-out`. These exclusions describe musical behaviour; the listening review still decides whether the result is usable.

## Sources

- [MiniMax Music 3 repository](https://github.com/MiniMax-AI/MiniMax-Music3) — verified 2026-10-10; supplies the structured caption concept and local model context.
- [MiniMax Music 3 official Space](https://huggingface.co/spaces/MiniMaxAI/MiniMax-Music3/blob/7b66a0bee1103243bf4d9406edd735619d55568c/app.py) — verified 2026-10-10; shows the explicit instrumental caption and lyric section convention.
- [Stable Audio 3 prompt guide](https://kb.stability.ai/knowledge-base/stable-audio-3-prompt-guide) — verified 2026-10-10; supports TrackType, instruments, genre, mood, and BPM prompt vocabulary.
- [Suno Platform](https://platform.suno.com/) — verified 2026-10-10; confirms an official REST API product exists, but does not expose the fields needed by this skill without account access.
