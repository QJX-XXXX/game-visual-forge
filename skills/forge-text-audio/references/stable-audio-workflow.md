# Stable Audio workflow

The provider uses only the official locally installed `stable-audio-3` Python runtime and the gated model repository `stabilityai/stable-audio-3-small-sfx`. The repository adapter does not implement a model, use an undocumented console command, call a hosted API, download weights, or accept licenses.

## Manual prerequisites

Install the official `Stability-AI/stable-audio-3` checkout and its dependencies in an isolated Python environment under a directory you choose. Configure that runtime with `audio sfx provider configure`; the command writes only the ignored repository-local `game-visual-forge.local.json` and never changes user environment variables or `PATH`. Accept the model's applicable Stability AI Community License and Gemma terms on the official model page, then make the model snapshot available locally. Install `ffmpeg` and `ffprobe` separately. The Skill reports missing prerequisites as `needs_user_action` and stops.

Discovery order is explicit: one-command Python override, repository-local config, current Python if it imports `stable_audio_3`, then a `stable-audio` PATH command whose sibling Python imports `stable_audio_3`. The provider child receives temporary cache, temp, and offline variables; the parent process is never mutated. Use `provider show-config` to inspect the selected non-secret paths and `provider preflight` for a non-mutating offline check.

## JSON provider boundary

The shared runtime sends one UTF-8 JSON object to `scripts/providers/stable_audio.py` and reads one UTF-8 JSON object from stdout. Diagnostics go to stderr. The commands are `models`, `preflight`, and `generate`.

Preflight is non-mutating. It verifies the `stable-audio-3`, `torch`, and `torchaudio` imports; resolves FFmpeg and FFprobe; checks the local model snapshot with `snapshot_download(..., local_files_only=True)`; and reports the package version, Python interpreter, exact model ID, cache, CUDA/device evidence, and availability. It sets `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_DATASETS_OFFLINE=1`, and `HF_HUB_DISABLE_TELEMETRY=1` before importing model code.

Generation loads the cached model with `StableAudioModel.from_pretrained("small-sfx")`, calls the official `StableAudioModel.generate()` method, and writes the raw provider tensor as a 32-bit floating-point WAV. The wrapper uses the installed model configuration's sample size and sample rate and records the seed and mode. The shared runtime converts the raw result to the delivery contract. Official progress is redirected to stderr so stdout remains exactly one UTF-8 JSON object.

Modes map as follows:

- `text-to-audio`: conditional generation from an English prompt and exact target duration.
- `redraw`: generation with source `(sample_rate, waveform)` as `init_audio` and the confirmed `init_noise_level`.
- `inpaint`: generation with source `inpaint_audio` and `inpaint_mask_start_seconds`/`inpaint_mask_end_seconds`.
- `continue`: inpainting with a mask from the final join guard of the source through the confirmed target end.

The adapter treats a changed official API, package identity, or model identity as a preflight failure; it never falls back to the retired legacy package.
