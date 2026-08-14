# Stable Audio workflow

The first release uses only the official locally installed `stable-audio-tools` Python package and the gated model repository `stabilityai/stable-audio-3-small-sfx`. The repository adapter does not implement a model, use an undocumented console command, call a hosted API, download weights, or accept licenses.

## Manual prerequisites

Install the official package and dependencies in the Python environment that runs the provider wrapper. Accept the model's applicable Stability AI Community License and T5Gemma terms on the official model page, then make the model snapshot available locally. Install `ffmpeg` and `ffprobe` separately. The Skill reports missing prerequisites as `needs_user_action` and stops.

## JSON provider boundary

The shared runtime sends one UTF-8 JSON object to `scripts/providers/stable_audio.py` and reads one UTF-8 JSON object from stdout. Diagnostics go to stderr. The commands are `models`, `preflight`, and `generate`.

Preflight is non-mutating. It verifies the `stable-audio-tools`, `torch`, and `torchaudio` imports; resolves FFmpeg and FFprobe; checks the local model snapshot with `snapshot_download(..., local_files_only=True)`; and reports the package version, Python interpreter, exact model ID, and availability. It sets `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_DATASETS_OFFLINE=1`, and `HF_HUB_DISABLE_TELEMETRY=1` before importing model code.

Generation loads the cached model with `get_pretrained_model("stabilityai/stable-audio-3-small-sfx")`, calls the official `generate_diffusion_cond` or `generate_diffusion_cond_inpaint` function, and writes the raw provider tensor as a 32-bit floating-point WAV. The wrapper derives sample rate, sample size, and channels from the installed model configuration and records the seed and mode. The shared runtime converts the raw result to the delivery contract.

Modes map as follows:

- `text-to-audio`: conditional generation from an English prompt and exact target duration.
- `redraw`: conditional generation with decoded source audio and the confirmed `init_noise_level`.
- `inpaint`: conditional inpainting with source audio and confirmed start/end mask bounds.
- `continue`: conditional inpainting with a mask from the final join guard of the source through the confirmed target end.

The adapter checks the installed function signatures at runtime. A package release that changes a signature is handled inside this adapter and covered by its fixture tests; the repository JSON protocol remains unchanged.
