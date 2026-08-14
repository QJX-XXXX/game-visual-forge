# Stable Audio 3 Runtime Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy Stable Audio research adapter with the official `stable-audio-3` Python API, discover an isolated user-selected runtime through an ignored repository-local config, publish complete bilingual installation guidance, and prove the migration with automated and real G-drive acceptance.

**Architecture:** Game Visual Forge continues to run in its existing Python environment. A focused runtime resolver reads `game-visual-forge.local.json`, selects the isolated Stable Audio Python, and launches the repository provider adapter with child-only cache and offline variables. The provider imports `stable_audio_3.StableAudioModel`, maps the four existing Forge modes to the official API, and preserves the current UTF-8 JSON, processing, review, publication, and Unity contracts.

**Tech Stack:** Python 3.11+, `argparse`, JSON, `subprocess`, official `stable-audio-3`, PyTorch/Torchaudio, Hugging Face Hub, FFmpeg/FFprobe, `unittest`, PowerShell, Unity 2022.3 package regression tests.

## Global Constraints

- Use only the official local `stable-audio-3` runtime and the post-trained `small-sfx` model.
- Support exactly `text-to-audio`, `redraw`, `inpaint`, and `continue`.
- Do not add a hosted API, legacy provider fallback, automatic retry, automatic license acceptance, or ordinary-request installation.
- Let every user choose any installation directory and drive.
- Do not require persistent user environment variables or PATH changes.
- Store local runtime paths in ignored `game-visual-forge.local.json`; never store tokens or media there.
- Keep provider stdin/stdout as one binary UTF-8 JSON request and one binary UTF-8 JSON response; diagnostics go to stderr.
- Preserve final delivery as reviewed 44,100 Hz, 16-bit signed PCM WAV.
- Keep every file under `skills/` in English; Chinese belongs only in Chinese README files.
- Do not stage or modify the user's existing `tests/test_tilemap_manifest_integrity.py` worktree change.
- Automated tests must not download or run the real model.
- The current user's real runtime root is exactly `G:\AI\stable-audio-3`; this is acceptance data, not a public default.

---

### Task 1: Add the repository-local runtime configuration contract

**Files:**
- Create: `src/game_visual_forge/contracts/audio_runtime.py`
- Modify: `src/game_visual_forge/contracts/__init__.py`
- Create: `src/game_visual_forge/providers/audio_runtime.py`
- Create: `tests/test_audio_runtime_config.py`

**Interfaces:**
- Produces: `StableAudioRuntimeConfig.from_dict(value)`, `.to_dict()`, and `StableAudioRuntimeConfig.standard_python(root, platform=sys.platform)`.
- Produces: `StableAudioRuntimeResolution` with `source`, `root`, `python_executable`, `config_path`, and derived cache paths.
- Produces: `repository_root() -> Path`, `configure_stable_audio_runtime(repo_root: Path, root: Path, python_executable: Path | None, *, replace: bool) -> StableAudioRuntimeResolution`, `resolve_stable_audio_runtime(repo_root: Path, *, explicit_python: Path | None = None, current_python: Path = Path(sys.executable)) -> StableAudioRuntimeResolution`, `show_stable_audio_runtime(repo_root: Path) -> StableAudioRuntimeResolution`, and `stable_audio_child_environment(root: Path, *, base: Mapping[str, str] | None = None, offline: bool) -> dict[str, str]`.
- Consumed by: provider orchestration and CLI tasks below.

- [ ] **Step 1: Write failing configuration and discovery tests**

Add tests that exercise absolute Windows-style paths without requiring those paths to exist, then use temporary real directories for executable validation:

```python
class AudioRuntimeConfigTests(unittest.TestCase):
    def test_config_round_trips_absolute_paths(self) -> None:
        config = StableAudioRuntimeConfig.from_dict({
            "schema_version": 1,
            "stable_audio": {
                "root": r"G:\AI\stable-audio-3",
                "python_executable": r"G:\AI\stable-audio-3\runtime\.venv\Scripts\python.exe",
            },
        })
        self.assertEqual(config.to_dict()["stable_audio"]["root"], r"G:\AI\stable-audio-3")

    def test_config_rejects_relative_root_and_unknown_schema(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute"):
            StableAudioRuntimeConfig.from_dict({
                "schema_version": 1,
                "stable_audio": {"root": "relative", "python_executable": "relative/python"},
            })

    def test_configure_is_atomic_idempotent_and_requires_replace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            runtime = Path(directory) / "runtime-a"
            python = write_fake_python(runtime)
            with patch("game_visual_forge.providers.audio_runtime._python_can_import", return_value=True):
                first = configure_stable_audio_runtime(repo, runtime, python, replace=False)
                second = configure_stable_audio_runtime(repo, runtime, python, replace=False)
            self.assertEqual(first.to_dict(), second.to_dict())
            config = repo / LOCAL_CONFIG_NAME
            original = config.read_bytes()
            self.assertEqual(list(repo.glob(f"{LOCAL_CONFIG_NAME}.*.tmp")), [])
            other_root = Path(directory) / "runtime-b"
            other = write_fake_python(other_root)
            with patch("game_visual_forge.providers.audio_runtime._python_can_import", return_value=True):
                with self.assertRaisesRegex(ValueError, "--replace"):
                    configure_stable_audio_runtime(repo, other_root, other, replace=False)
            self.assertEqual(config.read_bytes(), original)

    def test_resolver_prefers_explicit_then_local_config_then_current_python(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            explicit = Path(directory) / "explicit" / "python.exe"
            explicit.parent.mkdir()
            explicit.write_bytes(b"fake")
            with patch("game_visual_forge.providers.audio_runtime._python_can_import", return_value=True):
                selected = resolve_stable_audio_runtime(repo, explicit_python=explicit)
            self.assertEqual(selected.source, "explicit-python")
            self.assertEqual(selected.python_executable, explicit.resolve())

            configured_root = Path(directory) / "音频 环境"
            configured_python = configured_root / "runtime" / ".venv" / "Scripts" / "python.exe"
            configured_python.parent.mkdir(parents=True)
            configured_python.write_bytes(b"fake")
            (repo / LOCAL_CONFIG_NAME).write_text(json.dumps({
                "schema_version": 1,
                "stable_audio": {
                    "root": str(configured_root.resolve()),
                    "python_executable": str(configured_python.resolve()),
                },
            }, ensure_ascii=False), encoding="utf-8")
            with patch("game_visual_forge.providers.audio_runtime._python_can_import", return_value=True):
                selected = resolve_stable_audio_runtime(repo, current_python=Path(sys.executable))
            self.assertEqual(selected.source, "local-config")
            self.assertEqual(selected.root, configured_root.resolve())

    def test_resolver_uses_current_python_then_path_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            current = Path(directory) / "current-python.exe"
            current.write_bytes(b"fake")
            with patch("game_visual_forge.providers.audio_runtime._python_can_import", side_effect=lambda path, module: path == current):
                selected = resolve_stable_audio_runtime(repo, current_python=current)
            self.assertEqual(selected.source, "current-python")

            scripts = Path(directory) / "custom-runtime" / "Scripts"
            scripts.mkdir(parents=True)
            command = scripts / "stable-audio.exe"
            sibling = scripts / "python.exe"
            command.write_bytes(b"fake")
            sibling.write_bytes(b"fake")
            with patch("game_visual_forge.providers.audio_runtime.shutil.which", return_value=str(command)), patch(
                "game_visual_forge.providers.audio_runtime._python_can_import",
                side_effect=lambda path, module: path == sibling,
            ):
                selected = resolve_stable_audio_runtime(repo, current_python=Path(directory) / "missing.exe")
            self.assertEqual(selected.source, "path-command")
            self.assertEqual(selected.python_executable, sibling.resolve())

    def test_child_environment_keeps_every_cache_under_selected_root(self) -> None:
        env = stable_audio_child_environment(Path(r"G:\Audio Runtime"), base={"PATH": "base"}, offline=True)
        self.assertEqual(env["HF_HOME"], r"G:\Audio Runtime\models\huggingface")
        self.assertEqual(env["TEMP"], r"G:\Audio Runtime\temp")
        self.assertEqual(env["HF_HUB_OFFLINE"], "1")
```

Add a separate `StableAudioRuntimeConfig.standard_python()` assertion for both `win32` (`runtime/.venv/Scripts/python.exe`) and `linux` (`runtime/.venv/bin/python`); the examples above already cover spaces, Chinese path components, and a PATH launcher whose sibling Python can import `stable_audio_3`.

- [ ] **Step 2: Run the tests and confirm they fail for missing modules**

Run:

```powershell
python -m unittest tests.test_audio_runtime_config -v
```

Expected: import failure for `game_visual_forge.contracts.audio_runtime` or missing runtime functions.

- [ ] **Step 3: Implement the versioned local config**

Implement focused immutable types:

```python
@dataclass(frozen=True)
class StableAudioRuntimeConfig:
    schema_version: int
    root: str
    python_executable: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StableAudioRuntimeConfig":
        if int(value.get("schema_version", 0)) != 1:
            raise ValueError("schema_version must be 1")
        stable = value.get("stable_audio")
        if not isinstance(stable, dict):
            raise ValueError("stable_audio must be an object")
        root = _absolute_path(stable.get("root"), "stable_audio.root")
        python = _absolute_path(stable.get("python_executable"), "stable_audio.python_executable")
        return cls(1, root, python)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "stable_audio": {"root": self.root, "python_executable": self.python_executable},
        }
```

Use `PureWindowsPath.is_absolute()` for drive-letter strings and `Path.is_absolute()` for native paths so Windows config fixtures remain testable on other operating systems.

- [ ] **Step 4: Implement atomic configure and deterministic discovery**

Use `game-visual-forge.local.json` at the root returned by `repository_root()`. Write UTF-8 JSON to a sibling temporary file and replace the target only after validation succeeds. Do not use a user profile, registry, environment variable, or disk scan.

Implement discovery in this exact order:

```python
def resolve_stable_audio_runtime(
    repo_root: Path,
    *,
    explicit_python: Path | None = None,
    current_python: Path = Path(sys.executable),
) -> StableAudioRuntimeResolution:
    if explicit_python is not None:
        return _validate_explicit(explicit_python)
    local = repo_root / LOCAL_CONFIG_NAME
    if local.is_file():
        return _resolution_from_config(local)
    if _python_can_import(current_python, "stable_audio_3"):
        return _resolution_from_python(current_python, "current-python")
    command = shutil.which("stable-audio")
    if command:
        sibling = Path(command).parent / ("python.exe" if os.name == "nt" else "python")
        if _python_can_import(sibling, "stable_audio_3"):
            return _resolution_from_python(sibling, "path-command")
    raise ForgeError(
        ErrorCode.PROVIDER_UNAVAILABLE,
        "Stable Audio 3 runtime is not configured",
        recoverable=True,
        context={"status": "needs_user_action", "action": "install-stable-audio-3"},
    )
```

Validate imports with a bounded subprocess using binary output and `-c "import stable_audio_3"`. Do not import the large package into the Game Visual Forge process.

- [ ] **Step 5: Implement child-only cache and offline variables**

Return a copied environment mapping with derived root paths. Do not call `os.environ.update()` and do not persist settings. Create no directory during `show-config` or preflight resolution.

- [ ] **Step 6: Export contracts and run tests**

Run:

```powershell
python -m unittest tests.test_audio_runtime_config -v
python -m unittest tests.test_audio_contract tests.test_audio_provider_contract -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit the runtime configuration boundary**

```powershell
git add -- src/game_visual_forge/contracts/audio_runtime.py src/game_visual_forge/contracts/__init__.py src/game_visual_forge/providers/audio_runtime.py tests/test_audio_runtime_config.py
git diff --cached --check
git commit -m "feat: configure isolated stable audio runtime"
```

---

### Task 2: Launch audio providers through the resolved isolated Python

**Files:**
- Modify: `src/game_visual_forge/providers/stdio.py`
- Modify: `src/game_visual_forge/providers/audio.py`
- Modify: `tests/test_audio_provider_orchestration.py`
- Modify: `tests/fixtures/fake_audio_provider.py`

**Interfaces:**
- Consumes: `StableAudioRuntimeResolution` and `stable_audio_child_environment()` from Task 1.
- Changes: `run_utf8_json_process(argv: Sequence[str], payload: dict[str, Any], *, timeout_seconds: int, env: Mapping[str, str] | None = None) -> Utf8JsonProcessResult`.
- Changes: audio provider functions accept optional `python_executable` and `environment`; existing test fakes default to the current interpreter.
- Produces: one execution path used by models, preflight, and generation.

- [ ] **Step 1: Add failing external-interpreter and environment tests**

Extend orchestration tests with a fake runtime Python shim that records argv and selected child variables. Assert:

```python
result = run_audio_provider_models(
    FAKE,
    {"log_path": str(log)},
    python_executable=shim,
    environment={"GVF_TEST_CHILD": "中文值", "PATH": os.environ.get("PATH", "")},
)
self.assertEqual(record["python"], str(shim))
self.assertEqual(record["environment"]["GVF_TEST_CHILD"], "中文值")
```

Also assert that the parent `os.environ` does not gain `GVF_TEST_CHILD`, `HF_HOME`, or `TEMP` changes.

- [ ] **Step 2: Run the orchestration tests and confirm signature failures**

```powershell
python -m unittest tests.test_audio_provider_orchestration -v
```

Expected: unexpected keyword argument failures for `python_executable` or `environment`.

- [ ] **Step 3: Pass an optional environment through the binary subprocess helper**

Change the helper without changing its UTF-8 contract:

```python
def run_utf8_json_process(
    argv: Sequence[str],
    payload: dict[str, Any],
    *,
    timeout_seconds: int,
    env: Mapping[str, str] | None = None,
) -> Utf8JsonProcessResult:
    completed = subprocess.run(
        list(argv),
        input=_encode(payload),
        capture_output=True,
        text=False,
        timeout=timeout_seconds,
        shell=False,
        check=False,
        env=None if env is None else dict(env),
    )
```

- [ ] **Step 4: Make the audio runner choose the isolated Python explicitly**

Change `_argv` and `_run`:

```python
def _argv(executable: Path, command: ProviderCommand, python_executable: Path | None) -> list[str]:
    if executable.suffix.lower() == ".py":
        return [str(python_executable or Path(sys.executable)), str(executable), command.value]
    return [str(executable), command.value]
```

Thread optional `python_executable` and `environment` through `run_audio_provider_models`, `run_audio_provider_preflight`, and `generate_audio_candidates`. Do not change the video provider runner.

- [ ] **Step 5: Include source duration and join guard in continuation payloads**

The current provider payload omits values needed by the official continuation API. Add:

```python
"source_duration_seconds": getattr(source, "duration_seconds", None),
"join_guard_ms": request.join_guard_ms,
```

Assert both fields in the fake provider log for continuation mode.

- [ ] **Step 6: Run provider and clean-workflow regressions**

```powershell
python -m unittest tests.test_audio_provider_orchestration tests.test_audio_clean_workflow -v
```

Expected: all tests pass, including Chinese payloads and invalid UTF-8 classification.

- [ ] **Step 7: Commit external runtime execution**

```powershell
git add -- src/game_visual_forge/providers/stdio.py src/game_visual_forge/providers/audio.py tests/test_audio_provider_orchestration.py tests/fixtures/fake_audio_provider.py
git diff --cached --check
git commit -m "feat: run audio provider in isolated runtime"
```

---

### Task 3: Migrate the provider adapter to the official Stable Audio 3 API

**Files:**
- Modify: `skills/forge-text-audio/scripts/providers/stable_audio.py`
- Modify: `src/game_visual_forge/contracts/audio_provider.py`
- Modify: `tests/test_stable_audio_provider.py`
- Modify: `tests/test_audio_provider_contract.py`
- Modify: `tests/fixtures/fake_audio_provider.py`

**Interfaces:**
- Provider commands remain `models`, `preflight`, and `generate` over stdin/stdout JSON.
- Preflight package changes from `stable-audio-tools` to `stable-audio-3` and adds optional runtime/cache/device evidence.
- Generation uses `StableAudioModel.from_pretrained("small-sfx")` and `StableAudioModel.generate()` with the mode-specific keyword arguments defined below.

- [ ] **Step 1: Replace source-fragment tests with behavioral official-API tests**

Load the provider module with `importlib.util.spec_from_file_location`. Patch its `_load_backend()` to return deterministic fakes:

```python
class FakeModel:
    model_config = {"sample_size": 5_292_032}
    model = SimpleNamespace(sample_rate=44_100)
    calls: list[dict[str, object]] = []

    @classmethod
    def from_pretrained(cls, name: str):
        print("official progress on stdout")
        if name != "small-sfx":
            raise AssertionError(name)
        return cls()

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return FakeTensor()
```

Add one test per mode. Assert exact `prompt`, `duration`, `seed`, `sample_size`, `steps=8`, `cfg_scale=1.0`, source tuple ordering, redraw strength, inpaint bounds, and continuation bounds.

- [ ] **Step 2: Add a strict stdout test**

Call `main()` with fake stdin/stdout/stderr while the fake model prints progress. Assert stdout parses as one JSON object and the progress message appears only in stderr.

- [ ] **Step 3: Run tests and confirm legacy expectations fail**

```powershell
python -m unittest tests.test_stable_audio_provider tests.test_audio_provider_contract -v
```

Expected: failures for legacy package/import fragments and missing official API calls.

- [ ] **Step 4: Implement official backend loading and generation**

Use a small loader for testability:

```python
def _load_backend() -> tuple[Any, Any, Any]:
    import torch
    import torchaudio
    from stable_audio_3 import StableAudioModel
    return StableAudioModel, torch, torchaudio
```

Build common kwargs from the official API:

```python
model = StableAudioModel.from_pretrained(MODEL_ID)
kwargs = {
    "prompt": str(payload["prompt"]),
    "duration": float(payload["duration_seconds"]),
    "steps": 8,
    "cfg_scale": 1.0,
    "batch_size": 1,
    "sample_size": int(model.model_config["sample_size"]),
    "seed": int(payload["seed"]),
}
```

For redraw, load `(waveform, sample_rate)` and pass `(sample_rate, waveform)` as `init_audio`. For inpaint and continue, pass the same tuple as `inpaint_audio` with the correct mask bounds. For continue, calculate:

```python
start = max(0.0, float(payload["source_duration_seconds"]) - float(payload["join_guard_ms"]) / 1000.0)
end = float(payload["duration_seconds"])
```

Save `audio[0].cpu()` with `model.model.sample_rate`, `encoding="PCM_F"`, and `bits_per_sample=32`.

- [ ] **Step 5: Implement offline preflight without loading the model**

Set offline variables before importing Hugging Face components. Verify distribution metadata `stable-audio-3`, imports, tools, and the complete local snapshot with:

```python
snapshot_download(MODEL_REPOSITORY, local_files_only=True)
```

Return package name `stable-audio-3`, CUDA availability, device name, runtime root, model cache, and reason. Keep optional new fields backward-compatible in `AudioProviderPreflight.from_dict()`.

- [ ] **Step 6: Redirect official output away from JSON stdout**

Wrap backend import, preflight, model load, generation, and save operations with `contextlib.redirect_stdout(sys.stderr)`. Call `_write_json()` only after leaving that context.

- [ ] **Step 7: Remove every legacy adapter import and run tests**

```powershell
rg -n "stable-audio-tools|stable_audio_tools|get_pretrained_model|generate_diffusion_cond" skills/forge-text-audio/scripts/providers src/game_visual_forge tests/test_stable_audio_provider.py tests/test_audio_provider_contract.py tests/test_audio_provider_orchestration.py tests/fixtures/fake_audio_provider.py
python -m unittest tests.test_stable_audio_provider tests.test_audio_provider_contract tests.test_audio_provider_orchestration -v
```

Expected: `rg` finds only deliberate negative assertions in migration tests; all tests pass.

- [ ] **Step 8: Commit the official provider migration**

```powershell
git add -- skills/forge-text-audio/scripts/providers/stable_audio.py src/game_visual_forge/contracts/audio_provider.py tests/test_stable_audio_provider.py tests/test_audio_provider_contract.py tests/fixtures/fake_audio_provider.py
git diff --cached --check
git commit -m "feat: migrate audio provider to stable audio 3"
```

---

### Task 4: Expose configure, show-config, and automatic runtime use in the CLI

**Files:**
- Modify: `src/game_visual_forge/cli/audio.py`
- Modify: `src/game_visual_forge/cli/main.py`
- Modify: `tests/test_audio_cli.py`
- Modify: `tests/test_audio_clean_workflow.py`

**Interfaces:**
- Produces: `run_audio_provider_configure(root, python_executable, replace)`.
- Produces: `run_audio_provider_show_config()`.
- Changes: official `models`, `preflight`, and `generate` resolve the runtime automatically.
- Keeps: explicit `--executable` as an optional test/custom adapter override.

- [ ] **Step 1: Write failing CLI surface tests**

Assert provider help contains `configure`, `show-config`, `models`, and `preflight`. Assert configure help contains `--root`, `--python-executable`, and `--replace`.

Add subprocess tests from a temporary unrelated working directory using the absolute Skill launcher. Run configure against a temporary fake runtime and assert the config is written at the repository root supplied through a test-only function call, not at the current working directory.

- [ ] **Step 2: Run CLI tests and confirm missing commands**

```powershell
python -m unittest tests.test_audio_cli -v
```

Expected: `configure` and `show-config` are absent.

- [ ] **Step 3: Add CLI command handlers**

Implement:

```python
def run_audio_provider_configure(root: Path, python_executable: Path | None, replace: bool) -> dict[str, Any]:
    resolution = configure_stable_audio_runtime(repository_root(), root, python_executable, replace=replace)
    return {
        "schema_version": 1,
        "status": "configured",
        **resolution.to_dict(),
        "next_command": "python skills/forge-text-audio/scripts/run.py audio sfx provider preflight",
    }

def run_audio_provider_show_config() -> dict[str, Any]:
    return show_stable_audio_runtime(repository_root()).to_dict()
```

Configure must not call preflight automatically; it reports the next command so the installation flow remains inspectable.

- [ ] **Step 4: Make preflight and models user-friendly**

Make `--payload`, `--out`, and `--executable` optional for `models` and `preflight`. Default payload is `{}`, default adapter is the repository's `stable_audio.py`, and omitted `--out` means return JSON to the normal CLI stdout without writing a file.

When official defaults are used, resolve the runtime and pass its Python and ephemeral environment. Keep explicit executable support for deterministic fixtures.

- [ ] **Step 5: Resolve the runtime for generation**

Before official generation, call `resolve_stable_audio_runtime(repo_root)`, pass its Python and child environment to `generate_audio_candidates`, and record the resolved non-secret runtime source in `generation-result.json`. Do not include access tokens or full environment dumps.

- [ ] **Step 6: Preserve fake clean-workflow execution**

Update the clean workflow to pass the fake provider explicitly and verify it does not require a real local config. Add a separate test that uses the official default path and fails with `needs_user_action` when no runtime config exists.

- [ ] **Step 7: Run CLI, routing, and workflow tests**

```powershell
python -m unittest tests.test_audio_cli tests.test_audio_routing tests.test_audio_clean_workflow -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit the public command workflow**

```powershell
git add -- src/game_visual_forge/cli/audio.py src/game_visual_forge/cli/main.py tests/test_audio_cli.py tests/test_audio_clean_workflow.py
git diff --cached --check
git commit -m "feat: configure stable audio from forge cli"
```

---

### Task 5: Publish the Skill and bilingual installation guidance

**Files:**
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `install/codex/README.md`
- Modify: `install/claude/README.md`
- Create: `install/stable-audio-3/README.md`
- Create: `install/stable-audio-3/README.zh-CN.md`
- Modify: `skills/forge-text-audio/SKILL.md`
- Modify: `skills/forge-text-audio/references/stable-audio-workflow.md`
- Modify: `tests/test_repository_contract.py`
- Modify: `tests/test_skill_contracts.py`

**Interfaces:**
- Root READMEs expose one copyable Agent installation request and link to detailed setup.
- Detailed setup documents install into a user-selected isolated root without persistent environment variables or PATH changes.
- Skill stays English and sends missing-runtime work to `needs_user_action`.

- [ ] **Step 1: Write failing repository and Skill contract tests**

Require both root READMEs to contain `stable-audio-3`, `provider configure`, `game-visual-forge.local.json`, and the language-specific delegation prompt. Require both detailed install READMEs and reciprocal language links.

Require `.gitignore` to contain:

```text
game-visual-forge.local.json
```

Require Codex and Claude installation guides to list all four Skills. Require all public code, Skills, tests, install docs, and root READMEs to contain neither legacy package spelling.

- [ ] **Step 2: Run contract tests and confirm documentation failures**

```powershell
python -m unittest tests.test_repository_contract tests.test_skill_contracts -v
```

Expected: missing install docs, missing config ignore rule, and legacy name failures.

- [ ] **Step 3: Update the English Skill package**

Replace the runtime prerequisite step with the approved isolated-runtime workflow. Keep SKILL.md concise and point detailed provider behavior to `references/stable-audio-workflow.md`. State that ordinary use never installs, downloads, changes PATH/user variables, accepts licenses, or calls a hosted API.

Update the reference with the official import, exact four-mode mapping, repository-local config schema, discovery order, ephemeral environment, configure/show-config commands, offline preflight, and stdout/stderr rule.

- [ ] **Step 4: Add the root README delegation prompts**

Use the exact approved English and Chinese text from the specification. Keep each README below its existing 180-line contract and link to the corresponding detailed installation README.

- [ ] **Step 5: Write the detailed English installation README**

Use a user prompt instead of a hard-coded path:

```powershell
$AudioRoot = Read-Host "Stable Audio 3 installation directory"
$AudioRoot = [System.IO.Path]::GetFullPath($AudioRoot)
$AudioRuntime = Join-Path $AudioRoot "runtime"
$AudioTemp = Join-Path $AudioRoot "temp"
New-Item -ItemType Directory -Force -Path $AudioRoot,$AudioTemp | Out-Null
```

Set `UV_INSTALL_DIR`, `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`, `UV_PYTHON_BIN_DIR`, `HF_HOME`, `HUGGINGFACE_HUB_CACHE`, `TORCH_HOME`, `PIP_CACHE_DIR`, `TEMP`, and `TMP` only in that PowerShell process. Set `UV_NO_MODIFY_PATH=1`.

Document the official standalone uv install, official repo clone, `uv python install 3.12`, and `uv sync`. For Windows NVIDIA CUDA 12.6, document the official pinned wheels before sync:

```powershell
& $Uv pip install --python "$AudioRuntime\.venv\Scripts\python.exe" `
  torch==2.7.1 torchaudio==2.7.1 `
  --index-url https://download.pytorch.org/whl/cu126
& $Uv sync --project $AudioRuntime --no-install-package torch --no-install-package torchaudio
```

Document CPU as a supported Small-SFX route without claiming NVIDIA-only support.

- [ ] **Step 6: Document the license and model gate**

Tell the user to open `https://huggingface.co/stabilityai/stable-audio-3-small-sfx`, accept the Stability and Gemma terms personally, then run the isolated `hf auth login`. Cache the snapshot under the active `HF_HOME`:

```powershell
& "$AudioRuntime\.venv\Scripts\python.exe" -c "from huggingface_hub import snapshot_download; print(snapshot_download('stabilityai/stable-audio-3-small-sfx'))"
```

Do not embed a token in commands or config files.

- [ ] **Step 7: Document configure, show-config, and preflight**

From the Game Visual Forge repository:

```powershell
python skills/forge-text-audio/scripts/run.py audio sfx provider configure --root "$AudioRoot"
python skills/forge-text-audio/scripts/run.py audio sfx provider show-config
python skills/forge-text-audio/scripts/run.py audio sfx provider preflight
```

Include upgrade and removal steps. Removal first deletes `game-visual-forge.local.json`, then removes only the exact user-selected Stable Audio root after displaying and confirming it. Do not provide a broad recursive path expression.

- [ ] **Step 8: Write the equivalent Chinese installation README**

Keep commands identical and translate explanations accurately. Preserve official package, command, environment-variable, and model identifiers in English.

- [ ] **Step 9: Update Codex and Claude installation scope**

Change “three” to “four”, list `forge-text-audio`, retain the full-repository layout requirement, and link the Stable Audio setup without making it part of ordinary Skill installation.

- [ ] **Step 10: Validate documentation and Skill packaging**

```powershell
python -m unittest tests.test_repository_contract tests.test_skill_contracts tests.test_forge_skill_scope -v
python C:\Users\QJX\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills/forge-text-audio
```

Expected: all tests pass and `Skill is valid!`.

- [ ] **Step 11: Commit public documentation and Skill updates**

```powershell
git add -- .gitignore README.md README.zh-CN.md install/codex/README.md install/claude/README.md install/stable-audio-3/README.md install/stable-audio-3/README.zh-CN.md skills/forge-text-audio/SKILL.md skills/forge-text-audio/references/stable-audio-workflow.md tests/test_repository_contract.py tests/test_skill_contracts.py
git diff --cached --check
git commit -m "docs: install official stable audio 3 runtime"
```

---

### Task 6: Run the complete automated migration regression

**Files:**
- Modify only when a migration-owned test exposes a genuine implementation defect.
- Do not modify: `tests/test_tilemap_manifest_integrity.py`.

**Interfaces:**
- Consumes all implementation tasks.
- Produces a clean automated acceptance result without a real model download.

- [ ] **Step 1: Run the focused audio and documentation suite**

```powershell
python -m unittest tests.test_audio_runtime_config tests.test_audio_contract tests.test_audio_plan tests.test_audio_routing tests.test_audio_provider_contract tests.test_audio_provider_orchestration tests.test_stable_audio_provider tests.test_audio_probe tests.test_audio_ingest tests.test_audio_processing tests.test_audio_preservation tests.test_audio_quality tests.test_audio_review tests.test_audio_publication tests.test_audio_cli tests.test_audio_clean_workflow tests.test_unity_audio_integration tests.test_repository_contract tests.test_skill_contracts tests.test_forge_skill_scope -v
```

Expected: all focused tests pass.

- [ ] **Step 2: Validate all four Skill packages**

```powershell
$Validator = "C:\Users\QJX\.codex\skills\.system\skill-creator\scripts\quick_validate.py"
python $Validator skills/forge-2d-map
python $Validator skills/forge-2d-sprite
python $Validator skills/forge-text-audio
python $Validator skills/forge-video-to-sprite
```

Expected: four `Skill is valid!` results.

- [ ] **Step 3: Check all launcher surfaces**

```powershell
python skills/forge-2d-map/scripts/run.py --help
python skills/forge-2d-sprite/scripts/run.py --help
python skills/forge-text-audio/scripts/run.py audio sfx provider --help
python skills/forge-video-to-sprite/scripts/run.py --help
```

Expected: exit code 0 for every command; audio provider help lists configure, show-config, models, and preflight.

- [ ] **Step 4: Run the full repository suite**

```powershell
python -m unittest discover -s tests -q
```

Expected: all tests pass. Existing Pillow deprecation warnings are acceptable; new migration warnings are not.

- [ ] **Step 5: Verify tracked scope and legacy removal**

```powershell
rg -n -i "stable-audio-tools|stable_audio_tools" README.md README.zh-CN.md install skills src tests
git diff --check
git status --short
```

Expected: the search has no matches except a test that contains the forbidden strings as negative fixtures; `git status --short` shows only the user's pre-existing `tests/test_tilemap_manifest_integrity.py` change.

- [ ] **Step 6: Stop on regression instead of broadening scope**

Do not edit files in Task 6. If a check fails, return to the task that owns the failing file, add a focused failing test there, fix it, rerun that task's verification commands, and create that task's named commit before restarting Task 6. Never stage `tests/test_tilemap_manifest_integrity.py`.

---

### Task 7: Install and accept the real runtime on G drive

**Files:**
- External install root: `G:\AI\stable-audio-3`
- Local ignored config: `game-visual-forge.local.json`
- Generated acceptance outputs: ignored local run directory under `outputs/stable-audio-3-acceptance/`
- Do not commit model weights, runtime files, tokens, generated WAVs, or the local config.

**Interfaces:**
- Consumes the detailed Chinese/English installation guide and configure/preflight commands.
- Produces one available offline preflight and one probed short WAV.

- [ ] **Step 1: Resolve and display every target before installation**

In PowerShell:

```powershell
$AudioRoot = [System.IO.Path]::GetFullPath("G:\AI\stable-audio-3")
$AudioRuntime = Join-Path $AudioRoot "runtime"
$AudioPython = Join-Path $AudioRuntime ".venv\Scripts\python.exe"
$AudioRoot
$AudioRuntime
$AudioPython
```

Expected: every path begins with `G:\AI\stable-audio-3`. Stop if any resolved path is on C or outside the selected root.

- [ ] **Step 2: Install uv, managed Python, official source, and locked dependencies under G**

Follow the exact environment and commands from `install/stable-audio-3/README.zh-CN.md`. Set all install-shell cache and temp variables before invoking the uv installer, Git, uv, pip, or Hugging Face commands.

Expected: `G:\AI\stable-audio-3\runtime\.venv\Scripts\python.exe` exists and imports `stable_audio_3`, `torch`, and `torchaudio`.

- [ ] **Step 3: Stop at the license gate**

Open the official model page and ask the user to accept the Stability AI Community License and Gemma terms personally. Do not click agreement controls, paste a token, or continue a gated download on the user's behalf.

Expected: the user explicitly confirms authorization is complete.

- [ ] **Step 4: Authenticate and cache the model under G**

Run the documented isolated `hf auth login` interactively, then the documented `snapshot_download`. Do not echo or capture the token in task output.

Expected: the snapshot path is beneath `G:\AI\stable-audio-3\models\huggingface` and contains `model_config.json` plus `model.safetensors`.

- [ ] **Step 5: Create and inspect repository-local configuration**

```powershell
python skills/forge-text-audio/scripts/run.py audio sfx provider configure --root "G:\AI\stable-audio-3"
python skills/forge-text-audio/scripts/run.py audio sfx provider show-config
```

Expected: `game-visual-forge.local.json` points to the G-drive root and isolated Python, remains ignored by Git, and reports no persistent environment requirement.

- [ ] **Step 6: Run the real offline preflight**

```powershell
python skills/forge-text-audio/scripts/run.py audio sfx provider preflight --out "outputs\stable-audio-3-acceptance\preflight.json"
```

Expected JSON fields: `available: true`, package `stable-audio-3`, model `small-sfx`, `model_local: true`, FFmpeg/FFprobe true, and the actual CUDA/device report.

- [ ] **Step 7: Generate one short acceptance sound**

Create `outputs/stable-audio-3-acceptance/request.json` with `apply_patch` and this exact UTF-8 content:

```json
{
  "schema_version": 1,
  "asset_id": "stable-audio-acceptance",
  "mode": "text-to-audio",
  "prompt": "Dry wooden UI click, short transient, no music, no voice",
  "output_dir": "outputs/stable-audio-3-acceptance",
  "duration_seconds": 1.0,
  "usage_profile": "ui",
  "spatial_mode": "2d",
  "loop": false,
  "candidate_count": 1,
  "join_guard_ms": 20,
  "loop_analysis_ms": 50,
  "loop_crossfade_ms": 20,
  "unity_import_requested": false,
  "unity_scene_placement_requested": false
}
```

Run the initial planning command and show its canonical confirmation summary to the user:

```powershell
python skills/forge-text-audio/scripts/run.py audio sfx plan --request "outputs\stable-audio-3-acceptance\request.json" --out-dir "outputs\stable-audio-3-acceptance\run" --now "2026-08-14T00:00:00Z"
```

Expected: `needs_user_confirmation`, with no execution plan or job state written. After the user confirms the displayed request, use `apply_patch` to add the returned `confirmed_sha256` to `request.json`; do not calculate or insert a different digest. Then run:

```powershell
python skills/forge-text-audio/scripts/run.py audio sfx plan --request "outputs\stable-audio-3-acceptance\request.json" --out-dir "outputs\stable-audio-3-acceptance\run" --now "2026-08-14T00:01:00Z"
python skills/forge-text-audio/scripts/run.py audio sfx route --request "outputs\stable-audio-3-acceptance\request.json" --preflight "outputs\stable-audio-3-acceptance\preflight.json" --out "outputs\stable-audio-3-acceptance\decision.json" --state "outputs\stable-audio-3-acceptance\run\job-state.json" --now "2026-08-14T00:02:00Z"
python skills/forge-text-audio/scripts/run.py audio sfx generate --request "outputs\stable-audio-3-acceptance\request.json" --decision "outputs\stable-audio-3-acceptance\decision.json" --repo-root "." --out-dir "outputs\stable-audio-3-acceptance\run" --state "outputs\stable-audio-3-acceptance\run\job-state.json" --now "2026-08-14T00:03:00Z"
python skills/forge-text-audio/scripts/run.py audio sfx process --request "outputs\stable-audio-3-acceptance\request.json" --generation "outputs\stable-audio-3-acceptance\run\generation-result.json" --repo-root "." --out-dir "outputs\stable-audio-3-acceptance\run" --state "outputs\stable-audio-3-acceptance\run\job-state.json" --now "2026-08-14T00:04:00Z"
```

Expected: one raw provider WAV and one staged 44,100 Hz, 16-bit PCM WAV. This acceptance does not bypass the normal listening review or publish a final asset.

- [ ] **Step 8: Probe the generated WAV**

```powershell
ffprobe -v error -show_streams -show_format -of json "outputs\stable-audio-3-acceptance\staging\candidate-01.wav"
```

Run the repository audio probe as well. Expected: readable audio, 44,100 Hz, mono or stereo according to the request, exact duration tolerance, and no empty output.

- [ ] **Step 9: Verify installation isolation**

Use the Game Visual Forge Python and isolated Stable Audio Python separately:

```powershell
G:\python\3.12\python.exe -c "import importlib.util; print(importlib.util.find_spec('stable_audio_3'))"
G:\AI\stable-audio-3\runtime\.venv\Scripts\python.exe -c "import stable_audio_3, sys; print(sys.executable)"
```

Expected: the global Game Visual Forge Python does not find `stable_audio_3`; the isolated interpreter prints its G-drive `.venv` path.

- [ ] **Step 10: Re-run automated acceptance after real installation**

```powershell
python -m unittest discover -s tests -q
git status --short
```

Expected: all tests pass; model/runtime/config/output paths are untracked or ignored; only the user's pre-existing `tests/test_tilemap_manifest_integrity.py` modification remains visible.

- [ ] **Step 11: Report the license-dependent result without committing external artifacts**

Report the selected root, runtime Python, package/model identity, preflight status, generated WAV probe, and test counts. Do not commit or push unless the user gives a separate instruction.
