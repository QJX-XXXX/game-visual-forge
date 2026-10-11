# ComfyUI MiniMax Music 3 reference

## Local capability snapshot

The Comfy Desktop installation was inspected on 2026-10-10. The installed workflow is named `audio_minimax_music_3`; its local check reported runnable, with no required partner nodes and no credit-spending API node. The workflow contains the Music 3 text encoder, an empty audio latent, a sampler, tiled decode, and an advanced audio save step. The observed text encoder exposes caption, lyrics, seed, maximum duration, CFG scale, and top-k inputs. The observed latent duration ceiling is 360 seconds.

This is a capability snapshot, not proof of audio quality. A real run must still record the Comfy prompt ID, native output, decoded WAV, actual duration, and listening review. A warning from a switch node is not silently treated as a successful generation.

## Execution contract

1. Discover the current Comfy server and the current workflow slot.
2. Validate the expanded graph and inspect the real node and model names before changing inputs.
3. Set caption, lyric section, duration, model references, and both sampler seeds through the workflow interface. Keep the original workflow JSON intact; do not hand-edit subgraph definitions.
4. Submit once with `wait=False`, persist the prompt ID, and recover through queue/history if the client disconnects.
5. Fetch the saved native file, hash it, and decode an immutable staging copy to WAV before ingestion. If no prompt ID exists after a transport failure, mark the attempt unknown and do not submit again automatically.

For strict pure music, use `Instrumental, no vocals` in the caption and `[instrumental]` in the lyric field. Duration is a generation ceiling; the produced file may end earlier. A 60-second request may still produce a shorter native file, so do not claim duration compliance until `ffprobe` and listening confirm it. For continuous BGM, require the full groove from beat one and either verify a clean seam or create a short instrumental ending. The default project recommendation is at most 300 seconds until a local long-form sample has been listened to.

## Output and provenance

Save the native provider output before any loop, gain, or Unity processing. The current Comfy template exposes `mp3`, `flac`, and `opus` on `SaveAudioAdvanced`, not WAV; the test run used MP3 and then decoded an immutable staging copy to 44.1 kHz, 16-bit stereo WAV. Record both native codec and delivered WAV provenance. A seed does not guarantee sample-identical output across Comfy or model versions.

## Sources

- [MiniMax Music 3 repository](https://github.com/MiniMax-AI/MiniMax-Music3) — verified 2026-10-10; official model and caption context.
- [MiniMax Music 3 official Space](https://huggingface.co/spaces/MiniMaxAI/MiniMax-Music3/blob/7b66a0bee1103243bf4d9406edd735619d55568c/app.py) — verified 2026-10-10; instrumental input convention.
- Local Comfy Desktop capability inspection — verified 2026-10-10; workflow and node facts above. No model upgrade or environment mutation is implied.
