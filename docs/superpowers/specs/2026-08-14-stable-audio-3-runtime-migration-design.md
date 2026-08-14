# Stable Audio 3 Runtime Migration Design

## Status

Approved in conversation on 2026-08-14.

## Goal

Migrate `forge-text-audio` from the legacy `stable-audio-tools` research package to the official `stable-audio-3` inference library while preserving the existing text-to-audio, redraw, inpaint, continuation, review, WAV publication, and Unity AudioClip workflows.

The runtime must be isolated from the Python environment that runs Game Visual Forge. Users choose any installation directory. The repository discovers the configured runtime without persistent user environment variables or PATH changes.

This design supersedes the provider, runtime installation, and audio documentation portions of `2026-08-10-forge-text-audio-stable-audio-unity-design.md`. The existing intake, processing, review, publication, and Unity contracts remain unchanged unless this document explicitly changes them.

## Scope

The migration includes:

- the official `stable_audio_3.StableAudioModel` Python API;
- an isolated Stable Audio Python environment under a user-selected directory;
- repository-local runtime configuration and automatic discovery;
- `provider configure` and `provider show-config` commands;
- offline preflight and four-mode generation through the existing UTF-8 JSON boundary;
- English and Chinese installation documentation;
- concise, copyable README prompts that authorize an Agent to install the runtime;
- migration, configuration, documentation, and regression tests;
- one real local installation and acceptance run at `G:\AI\stable-audio-3` for the current user.

The migration does not add a hosted Stability API, automatic license acceptance, silent model downloads, automatic retry, a fallback provider, speech generation, music generation, or Unity scene placement.

## Selected Architecture

Game Visual Forge and Stable Audio use separate Python interpreters:

```text
Game Visual Forge Python
  -> resolve repository-local Stable Audio configuration
  -> launch the configured Stable Audio Python
  -> run skills/forge-text-audio/scripts/providers/stable_audio.py
  -> import stable_audio_3
  -> emit one UTF-8 JSON response
```

The Stable Audio installation is self-contained under a directory selected by the user. The standard layout is:

```text
<stable-audio-root>/
  bin/                         # optional local uv executable
  python/                      # optional uv-managed Python
  runtime/                     # official Stability-AI/stable-audio-3 checkout
    .venv/
  models/huggingface/
  models/torch/
  cache/uv/
  cache/pip/
  temp/
```

The current user's selected root is `G:\AI\stable-audio-3`. That path is an acceptance fixture, not a public default or repository rule. Other users may choose any drive and directory, including a system drive.

## Repository-Local Configuration

The repository root contains an ignored local file named `game-visual-forge.local.json` after configuration:

```json
{
  "schema_version": 1,
  "stable_audio": {
    "root": "G:\\AI\\stable-audio-3",
    "python_executable": "G:\\AI\\stable-audio-3\\runtime\\.venv\\Scripts\\python.exe"
  }
}
```

The file contains paths only. It must not contain access tokens, license responses, credentials, prompts, or generated media. Add it to `.gitignore`.

Runtime discovery uses this stable order:

1. an explicit one-command override supplied by the caller;
2. `game-visual-forge.local.json` beside the repository `pyproject.toml`;
3. the current Python interpreter when it can import `stable_audio_3`;
4. a usable official `stable-audio` command on PATH, but only when a sibling environment Python (`python.exe` on Windows or `python` on POSIX) can import `stable_audio_3`;
5. `needs_user_action` when no runtime is usable.

Discovery must not scan drives, assume a drive letter, assume an `AI` directory, modify PATH, or read persistent user environment variables. The public workflow does not require `GVF_STABLE_AUDIO_ROOT` or `GVF_STABLE_AUDIO_PYTHON`.

## Configuration Commands

Add these commands to the shared audio CLI:

```text
audio sfx provider configure
audio sfx provider show-config
```

The standard Windows command is:

```powershell
python skills/forge-text-audio/scripts/run.py audio sfx provider configure `
  --root "<user-selected-directory>"
```

`configure` must:

- locate the repository root independently of the current working directory;
- require an absolute root path;
- derive `runtime\.venv\Scripts\python.exe` on Windows and `runtime/.venv/bin/python` on POSIX;
- accept `--python-executable` for a non-standard isolated environment;
- validate that the root, Python executable, and provider imports are usable;
- write schema-versioned UTF-8 JSON atomically;
- be idempotent when the requested configuration matches the existing file;
- reject a different existing configuration unless `--replace` is present;
- never write secrets or modify user environment variables or PATH;
- return the config path, resolved runtime, and next preflight command as UTF-8 JSON.

`show-config` must return the source of discovery, config path when present, resolved root, resolved Python, derived cache directories, and validation problems. It must not import or load the model.

## Ephemeral Runtime Environment

The Game Visual Forge process constructs an environment only for each Stable Audio provider child process. It sets the following paths beneath the configured root:

```text
HF_HOME=<root>/models/huggingface
HUGGINGFACE_HUB_CACHE=<root>/models/huggingface/hub
TORCH_HOME=<root>/models/torch
UV_CACHE_DIR=<root>/cache/uv
PIP_CACHE_DIR=<root>/cache/pip
TEMP=<root>/temp
TMP=<root>/temp
HF_HUB_DISABLE_TELEMETRY=1
```

For preflight and generation it also sets `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and `HF_DATASETS_OFFLINE=1`. These values are not persisted after the child process exits.

Installation documentation sets the same paths only in the active installation shell. It does not create user or machine environment variables.

## Official Stable Audio 3 Provider

Replace imports from `stable_audio_tools` with:

```python
from stable_audio_3 import StableAudioModel
```

Load only the post-trained `small-sfx` model:

```python
model = StableAudioModel.from_pretrained("small-sfx")
```

Use `model.model_config["sample_size"]` for the maximum sample size and `model.model.sample_rate` for output. Default inference parameters are 8 steps, CFG scale 1.0, batch size 1, the confirmed seed, and automatic device selection.

Mode mapping is exact:

| Forge mode | Official API inputs |
| --- | --- |
| `text-to-audio` | `prompt`, `duration`, `seed` |
| `redraw` | text inputs plus `init_audio` and `init_noise_level` |
| `inpaint` | text inputs plus `inpaint_audio`, `inpaint_mask_start_seconds`, and `inpaint_mask_end_seconds` |
| `continue` | inpaint inputs with the mask beginning at the confirmed source-tail join guard and ending at the target duration |

Source audio is loaded as `(sample_rate, waveform)`. The generated tensor is saved as an immutable raw floating-point WAV. The existing deterministic processing layer remains responsible for the reviewed 44,100 Hz, 16-bit signed PCM delivery file and protected-region preservation.

Provider stdout must contain exactly one UTF-8 JSON object. All official-library progress, warnings, diagnostics, and tracebacks go to stderr. The adapter must redirect incidental stdout during imports, model loading, generation, and audio saving so it cannot corrupt the JSON protocol.

Remove all runtime and public documentation references to `stable-audio-tools` and `stable_audio_tools`. No compatibility fallback remains.

## Preflight

Preflight is offline and non-mutating. It verifies:

- the resolved isolated Python executable;
- import and version metadata for `stable-audio-3`;
- imports for Torch, Torchaudio, and Hugging Face Hub;
- the exact `small-sfx` model identity;
- a complete locally cached `stabilityai/stable-audio-3-small-sfx` snapshot;
- FFmpeg and FFprobe;
- CUDA availability and detected device name when present;
- the resolved runtime, model, cache, and temporary directories.

Preflight must not load the full model, access the network, download files, accept terms, or reject a user-selected drive letter. A missing package, inaccessible gated model, or incomplete cache returns `needs_user_action` with the relevant installation or authorization action.

## Installation Boundary

The repository never installs Stable Audio during an ordinary sound request. Installation occurs only after an explicit user request, including the copyable README delegation prompt.

The installer or Agent must:

1. ask the user to choose an installation directory;
2. keep the isolated Python environment, official source, model weights, and caches beneath that directory by default;
3. install the official `Stability-AI/stable-audio-3` repository and its locked dependencies;
4. require the user personally to accept the Stability AI Community License and redistributed Gemma terms;
5. cache `stabilityai/stable-audio-3-small-sfx` only after authorization;
6. run `provider configure` to create the repository-local configuration;
7. run offline preflight and report the result;
8. never use a hosted API or accept terms for the user.

The current acceptance installation uses `G:\AI\stable-audio-3`. It must not install Stable Audio packages into `G:\python\3.12`, and its Stable Audio source, virtual environment, weights, caches, and installation temporary files must remain beneath the chosen G-drive root.

## README Delegation Prompts

The root READMEs remain concise and contain one copyable installation request.

Chinese:

```text
请为 forge-text-audio 安装并配置官方 stable-audio-3：先询问我安装目录，将独立 Python 环境、模型和全部缓存放入该目录；许可证必须由我本人确认，禁止调用托管 API；安装完成后在 game-visual-forge 仓库中运行 provider configure 命令创建本地配置，不修改用户环境变量或 PATH，最后运行离线预检并报告结果。
```

English:

```text
Install and configure the official stable-audio-3 runtime for forge-text-audio: ask me to choose the installation directory, keep the isolated Python environment, model weights, and all caches under that directory, require me to accept all licenses personally, never use a hosted API, run the repository's provider configure command without changing user environment variables or PATH, and finish by running and reporting the local offline preflight.
```

The prompt is explicit installation authority. It does not authorize license acceptance, hosted API use, unrelated system changes, or automatic generation.

## Documentation

Update:

- `README.md` and `README.zh-CN.md` with the concise delegation prompt and a link to full setup;
- `install/codex/README.md` and `install/claude/README.md` to list all four public Skills and the audio prerequisite boundary;
- `skills/forge-text-audio/SKILL.md` and its provider reference to describe the isolated official runtime and local configuration;
- repository contract tests to require `stable-audio-3` and reject legacy package names.

Add:

- `install/stable-audio-3/README.md` for the complete English setup;
- `install/stable-audio-3/README.zh-CN.md` for the complete Chinese setup.

The detailed setup documents cover directory selection, isolated installation, Windows and POSIX paths, GPU and CPU notes, license gating, model caching, configuration, offline preflight, upgrade, removal, and local-license cost boundaries. Do not add a README or installation guide inside the Skill package.

## Error Handling

- Missing runtime configuration or installation returns `needs_user_action` plus the README delegation prompt.
- An invalid or stale local config reports the exact invalid field and does not fall through silently to a different provider.
- A different configuration is never overwritten without `--replace`.
- Missing license access or model cache returns `needs_user_action` without attempting a download.
- Provider timeout or nonzero exit records a failed attempt; an indeterminate outcome records `generation_unknown`.
- No failed or unknown attempt is retried automatically.
- CUDA out-of-memory errors are reported without silently switching to a hosted service.
- An official API signature or model identity change fails preflight and does not fall back to the legacy library.

## Tests

Add or update tests for:

- local config parsing, path validation, atomic writing, idempotence, and `--replace`;
- config discovery from any working directory;
- Windows, POSIX, spaces, and Unicode paths;
- discovery precedence without persistent environment variables or drive scanning;
- child-process Python selection and ephemeral cache environment;
- `configure` and `show-config` CLI help and JSON output;
- official package preflight and exact `small-sfx` identity;
- all four `StableAudioModel.generate()` mappings through a deterministic fake module;
- source tuple order, model sample size, sample rate, seed, and raw WAV output;
- strict stdout JSON with official progress redirected to stderr;
- missing runtime, inaccessible model, timeout, nonzero exit, and `generation_unknown` behavior;
- removal of legacy package references from public code, Skills, tests, installation docs, and READMEs;
- updated Codex and Claude installation scope for all four Skills;
- a clean fake-provider end-to-end audio workflow;
- all existing map, Sprite, video, audio processing, review, publication, and Unity tests.

Automated tests never download or execute the real model.

## Real Acceptance

After implementation tests pass:

1. install the runtime at `G:\AI\stable-audio-3`;
2. stop for the user's personal Hugging Face license acceptance when required;
3. cache the official `small-sfx` snapshot under the configured model directory;
4. create the repository-local config with `provider configure`;
5. require offline preflight to report `available: true`;
6. generate one short sound-effect candidate;
7. verify the file with FFprobe and the repository audio probe;
8. confirm no Stable Audio package was installed into `G:\python\3.12`;
9. run the focused migration suite, all four Skill validations, launcher help checks, and the full repository test suite.

The real generated sound is acceptance evidence only and is not committed unless the user explicitly requests a curated repository asset.

## Acceptance Criteria

- The Provider imports `stable_audio_3` and has no legacy runtime fallback.
- All four existing audio generation modes use the official API correctly.
- Users may choose any installation directory and are never forced to a drive or folder convention.
- A repository-local ignored config enables automatic use without user environment variables or PATH changes.
- `provider configure` safely creates or updates that config from any working directory.
- Missing installation produces a copyable Agent installation request rather than an opaque import error.
- Ordinary audio requests never install, download, accept terms, or call a hosted API.
- English and Chinese documentation provide complete manual and Agent-assisted setup.
- The current user's real installation is isolated beneath `G:\AI\stable-audio-3` and passes offline preflight plus one real generation.
- Existing review, WAV publication, Unity AudioClip import, and non-audio workflows remain compatible.
- Automated and real acceptance checks pass without modifying unrelated user worktree changes.
