# Audio One-Shot Peak Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic `-1.0 dBFS` peak normalization for generated text-to-audio one-shots, prove its safeguards, then generate and publish only a user-approved blacksmith strike README example.

**Architecture:** Keep normalization inside the existing PCM processing module, after FFmpeg format conversion and before previews. A focused helper scales all channels equally and skips silent or clipped input; request routing limits the helper to non-looping `text-to-audio` requests with the `one-shot` usage profile. Raw provider files and all source-preserving modes remain untouched.

**Tech Stack:** Python 3.12 repository runtime, Python `wave` and `array`, FFmpeg/FFprobe, `unittest`, Stable Audio 3 Small-SFX, Markdown Skill documentation.

## Global Constraints

- Normalize only `text-to-audio` + `one-shot` + `loop == false` staging WAV files.
- Use an exact `-1.0 dBFS` PCM peak target within one 16-bit sample of rounding tolerance.
- Never overwrite raw provider output.
- Skip silent input and input containing samples with absolute value at least `32767`.
- Do not add compression, limiting, EQ, LUFS normalization, dithering, channel remixing, or new dependencies.
- Do not change redraw, inpaint, continue, UI, scene, or looping-ambience processing.
- Keep failed generations and local run metadata under ignored `outputs/` directories.
- Do not add a blacksmith artifact to README until the user passes all six listening checks.
- Preserve the user's unrelated `tests/test_tilemap_manifest_integrity.py` working-tree modification.

---

### Task 1: Specify PCM Peak Normalization Behavior

**Files:**
- Modify: `tests/test_audio_processing.py`
- Test: `tests/test_audio_processing.py`

**Interfaces:**
- Consumes: existing `write_pcm_samples()` and `read_pcm16_metrics()` helpers.
- Produces: executable expectations for `_normalize_pcm16_peak(path: Path, target_dbfs: float = -1.0) -> bool`.

- [ ] **Step 1: Add failing helper tests**

Import `_normalize_pcm16_peak` from `game_visual_forge.processing.audio` and add tests equivalent to:

```python
def test_peak_normalization_reaches_minus_one_dbfs_without_changing_shape(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "quiet.wav"
        write_pcm_samples(path, [1000, -1000] * 200, channels=2)
        before = read_pcm16_metrics(path)
        self.assertTrue(_normalize_pcm16_peak(path))
        after = read_pcm16_metrics(path)
        target = round(32767 * (10 ** (-1.0 / 20.0)))
        self.assertLessEqual(abs(after.peak_sample - target), 1)
        self.assertEqual(after.frame_count, before.frame_count)
        self.assertEqual(after.sample_rate, before.sample_rate)
        self.assertEqual(after.channels, before.channels)

def test_peak_normalization_leaves_silence_and_clipping_unchanged(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for name, samples in (("silent.wav", [0, 0, 0, 0]), ("clipped.wav", [32767, -32767, 0, 0])):
            path = root / name
            write_pcm_samples(path, samples, channels=2)
            before = path.read_bytes()
            self.assertFalse(_normalize_pcm16_peak(path))
            self.assertEqual(path.read_bytes(), before)
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
python -m unittest tests.test_audio_processing -v
```

Expected: import failure because `_normalize_pcm16_peak` does not exist.

---

### Task 2: Implement and Route Deterministic Normalization

**Files:**
- Modify: `src/game_visual_forge/processing/audio.py`
- Modify: `tests/test_audio_processing.py`
- Test: `tests/test_audio_processing.py`
- Test: `tests/test_audio_quality.py`

**Interfaces:**
- Consumes: `_read_pcm()`, `_write_pcm()`, `AudioGenerationMode`, `AudioUsageProfile`, and `AudioRequest.loop`.
- Produces: `_normalize_pcm16_peak(path: Path, target_dbfs: float = -1.0) -> bool` and restricted invocation from `process_audio_candidates()`.

- [ ] **Step 1: Implement the PCM helper**

Add `import math`, import `AudioUsageProfile`, and implement:

```python
def _normalize_pcm16_peak(path: Path, target_dbfs: float = -1.0) -> bool:
    channels, rate, frames = _read_pcm(path)
    peak = max((abs(value) for frame in frames for value in frame), default=0)
    if peak == 0 or peak >= 32767:
        return False
    target = round(32767 * math.pow(10.0, target_dbfs / 20.0))
    gain = target / peak
    normalized = [tuple(round(value * gain) for value in frame) for frame in frames]
    _write_pcm(path, channels, rate, normalized)
    return True
```

The existing `_write_pcm()` clamp remains integer-rounding protection. No limiter or compressor is introduced.

- [ ] **Step 2: Add a failing integration test for eligibility and raw immutability**

Add a one-second stereo fixture and assert that processing normalizes only the staging copy:

```python
def test_process_normalizes_only_generated_one_shot_staging(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        request = AudioRequest.from_dict(valid_audio_request(
            duration_seconds=1.0,
            spatial_mode="2d",
            unity_import_requested=False,
        ))
        raw = root / request.output_dir / "raw" / "candidate-01.wav"
        write_pcm_samples(raw, [1000, -1000] * 44100, channels=2)
        raw_before = raw.read_bytes()
        generation = AudioGenerationResult(
            1,
            fingerprint_request(request.to_dict()),
            request.mode,
            (AudioCandidateRecord(1, "candidate-01", "candidate-01", 1, "raw/candidate-01.wav", "a" * 64),),
            (),
        )
        result = process_audio_candidates(root, request, generation, None, FAKE_FFMPEG, FAKE_FFMPEG)
        metrics = read_pcm16_metrics(root / result.artifacts[0].wav_path)
        target = round(32767 * (10 ** (-1.0 / 20.0)))
        self.assertEqual(raw.read_bytes(), raw_before)
        self.assertLessEqual(abs(metrics.peak_sample - target), 1)
        self.assertEqual(metrics.frame_count, 44100)
        self.assertEqual(metrics.channels, 2)
```

Add a second integration test with `usage_profile="ui"` and assert that staging bytes equal the quiet raw fixture after the fake converter copies it.

- [ ] **Step 3: Route only eligible requests**

Immediately after FFmpeg conversion and before duration metrics, add:

```python
if (
    request.mode is AudioGenerationMode.TEXT_TO_AUDIO
    and request.usage_profile is AudioUsageProfile.ONE_SHOT
    and not request.loop
):
    _normalize_pcm16_peak(processed)
```

Keep this call before waveform and spectrum creation so previews represent the delivered WAV.

- [ ] **Step 4: Run focused processing and quality tests**

Run:

```powershell
python -m unittest tests.test_audio_processing tests.test_audio_quality -v
```

Expected: all tests pass; the existing clipping hard-failure test remains green.

- [ ] **Step 5: Commit the implementation and tests**

Stage only:

```powershell
git add src/game_visual_forge/processing/audio.py tests/test_audio_processing.py
git diff --cached --check
git commit -m "feat: normalize generated one-shot audio peaks"
```

Do not stage `tests/test_tilemap_manifest_integrity.py`, README files, or README audio assets.

---

### Task 3: Align the Skill Contract and Validate It

**Files:**
- Modify: `skills/forge-text-audio/SKILL.md`
- Modify: `skills/forge-text-audio/references/processing-and-quality.md`
- Test: `tests/test_skill_contracts.py`

**Interfaces:**
- Consumes: the normalization behavior implemented in Task 2.
- Produces: concise agent guidance that exposes the exact target and scope.

- [ ] **Step 1: Update Skill guidance**

Extend workflow step 5 in `SKILL.md` with one concise sentence:

```text
Normalize eligible generated text-to-audio one-shots to a deterministic -1.0 dBFS PCM peak; never apply that gain stage to raw files or source-preserving modes.
```

Add this paragraph to `references/processing-and-quality.md` after the delivery-format paragraph:

```text
For non-looping text-to-audio requests with the one-shot usage profile, normalize the converted staging WAV to a -1.0 dBFS sample peak before preview generation. Skip silent or already clipped input so silence remains reviewable and clipping remains a hard-failure signal. Do not apply peak normalization to raw files, redraw, inpaint, continue, UI, scene, or looping-ambience output.
```

- [ ] **Step 2: Add a contract assertion**

In `tests/test_skill_contracts.py`, extend the forge-text-audio contract test to require both `-1.0 dBFS` and `one-shot` in the Skill or its directly referenced processing guide.

- [ ] **Step 3: Run Skill tests and validator**

Run:

```powershell
python -m unittest tests.test_skill_contracts -v
python "C:\Users\QJX\.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills/forge-text-audio
```

Expected: contract tests pass and the validator prints `Skill is valid!`.

- [ ] **Step 4: Commit Skill documentation**

```powershell
git add skills/forge-text-audio/SKILL.md skills/forge-text-audio/references/processing-and-quality.md tests/test_skill_contracts.py
git diff --cached --check
git commit -m "docs: define one-shot audio peak target"
```

---

### Task 4: Run Repository Verification

**Files:**
- Verify: repository Python test suite
- Verify: `skills/forge-text-audio/`

**Interfaces:**
- Consumes: Tasks 2 and 3.
- Produces: evidence that normalization does not regress other map, sprite, video, audio, or Unity contracts.

- [ ] **Step 1: Run the full test suite**

```powershell
Set-Location "G:\GitProject\game-visual-forge"
python -m unittest discover -s tests -q
```

Expected: all tests pass. Existing Pillow deprecation warnings are non-blocking.

- [ ] **Step 2: Audit the working tree**

```powershell
git status --short
git diff --check
git diff --name-status origin/main..main
```

Expected: no model weights, Hugging Face tokens, `game-visual-forge.local.json`, or `outputs/` files are tracked. The unrelated Tilemap test remains unstaged.

---

### Task 5: Generate the Third-Round Blacksmith Candidates

**Files:**
- Create with `apply_patch`: `outputs/stable-audio-3-blacksmith-crisp-v3/request.json`
- Create locally: ignored generation, processing, preview, and state artifacts below `outputs/stable-audio-3-blacksmith-crisp-v3/`

**Interfaces:**
- Consumes: the configured local Stable Audio 3 runtime and Task 2 normalization.
- Produces: three normalized 0.8-second candidates for user listening review.

- [ ] **Step 1: Create the exact confirmed request**

Use this UTF-8 JSON content:

```json
{
  "schema_version": 1,
  "asset_id": "stable-audio-blacksmith-loud-crisp-strike",
  "mode": "text-to-audio",
  "prompt": "One very loud isolated strike of a small hardened-steel blacksmith hammer on the bare edge of a hardened-steel anvil, piercing bright metallic ping, razor-sharp attack, strong high-frequency sparkle, short clean bell-like ring, close-miked game-ready crafting SFX, no low thud, no muffled clang, no multiple hits, no scraping, no machinery, no ambience, no music, no voice",
  "output_dir": "outputs/stable-audio-3-blacksmith-crisp-v3",
  "duration_seconds": 0.8,
  "usage_profile": "one-shot",
  "spatial_mode": "2d",
  "loop": false,
  "candidate_count": 3,
  "join_guard_ms": 20,
  "loop_analysis_ms": 50,
  "loop_crossfade_ms": 20,
  "unity_import_requested": false,
  "unity_scene_placement_requested": false
}
```

- [ ] **Step 2: Run the confirmation plan**

```powershell
python skills/forge-text-audio/scripts/run.py audio sfx plan --request "outputs/stable-audio-3-blacksmith-crisp-v3/request.json" --out-dir "outputs/stable-audio-3-blacksmith-crisp-v3/run" --now "2026-08-14T03:00:00Z"
```

Expected: `needs_user_confirmation`. Insert the exact returned `confirmation_sha256` into the request with `apply_patch`; do not calculate or substitute a different digest. The user has already approved this exact prompt, duration, mode, profile, spatial mode, candidate count, and delivery scope.

- [ ] **Step 3: Plan, preflight, route, generate, and process**

Run the repository commands in order, using the configured runtime rather than an executable override:

```powershell
python skills/forge-text-audio/scripts/run.py audio sfx plan --request "outputs/stable-audio-3-blacksmith-crisp-v3/request.json" --out-dir "outputs/stable-audio-3-blacksmith-crisp-v3/run" --now "2026-08-14T03:01:00Z"
python skills/forge-text-audio/scripts/run.py audio sfx provider preflight --out "outputs/stable-audio-3-blacksmith-crisp-v3/preflight.json"
python skills/forge-text-audio/scripts/run.py audio sfx route --request "outputs/stable-audio-3-blacksmith-crisp-v3/request.json" --preflight "outputs/stable-audio-3-blacksmith-crisp-v3/preflight.json" --out "outputs/stable-audio-3-blacksmith-crisp-v3/decision.json" --state "outputs/stable-audio-3-blacksmith-crisp-v3/run/job-state.json" --now "2026-08-14T03:02:00Z"
python skills/forge-text-audio/scripts/run.py audio sfx generate --request "outputs/stable-audio-3-blacksmith-crisp-v3/request.json" --decision "outputs/stable-audio-3-blacksmith-crisp-v3/decision.json" --repo-root "." --out-dir "outputs/stable-audio-3-blacksmith-crisp-v3/run" --state "outputs/stable-audio-3-blacksmith-crisp-v3/run/job-state.json" --now "2026-08-14T03:03:00Z"
python skills/forge-text-audio/scripts/run.py audio sfx process --request "outputs/stable-audio-3-blacksmith-crisp-v3/request.json" --generation "outputs/stable-audio-3-blacksmith-crisp-v3/run/generation-result.json" --repo-root "." --out-dir "outputs/stable-audio-3-blacksmith-crisp-v3/run" --state "outputs/stable-audio-3-blacksmith-crisp-v3/run/job-state.json" --now "2026-08-14T03:04:00Z"
```

- [ ] **Step 4: Verify every candidate**

Use FFprobe and `read_pcm16_metrics()` to prove each staging WAV is 0.8 seconds, 44,100 Hz, stereo, 16-bit PCM, unclipped, and within one sample of `-1.0 dBFS`. Verify raw SHA-256 values still match `generation-result.json`.

- [ ] **Step 5: Stop for user listening review**

Present all three staging WAV files. Require the user to choose one candidate and explicitly pass all six checks: prompt/action match, transient/impact clarity, noise/generation artifacts, unwanted speech/music, spatial/channel suitability, and loop/tail quality. Do not publish or edit README if all candidates fail.

---

### Task 6: Record Approval and Publish the README Showcase

**Files:**
- Create with `apply_patch`: `outputs/stable-audio-3-blacksmith-crisp-v3/checks.json`
- Create locally: reviewed final bundle below `outputs/stable-audio-3-blacksmith-crisp-v3/final/`
- Create: `assets/readme/stable-audio-3-small-sfx-blacksmith-strike.wav`
- Create: `assets/readme/stable-audio-3-small-sfx-blacksmith-strike-waveform.png`
- Create: `assets/readme/stable-audio-3-small-sfx-blacksmith-strike-spectrum.png`
- Modify: `README.md`
- Modify: `README.zh-CN.md`

**Interfaces:**
- Consumes: the exact candidate ID and six approvals supplied by the user in Task 5.
- Produces: a reviewed final WAV bundle and bilingual, reproducible README evidence.

- [ ] **Step 1: Record exactly the six approved checks**

Only after explicit user approval, create:

```json
{
  "prompt-and-action-match": true,
  "transient-and-impact-clarity": true,
  "noise-and-generation-artifacts": true,
  "unwanted-speech-or-music": true,
  "spatial-and-channel-suitability": true,
  "loop-or-tail-quality": true
}
```

- [ ] **Step 2: Record review and validate publication**

Set `$SelectedCandidate` to the exact user-approved ID (`candidate-01`, `candidate-02`, or `candidate-03`) and run:

```powershell
$SelectedCandidate = "candidate-01"
python skills/forge-text-audio/scripts/run.py audio sfx record-review --request "outputs/stable-audio-3-blacksmith-crisp-v3/request.json" --generation "outputs/stable-audio-3-blacksmith-crisp-v3/run/generation-result.json" --processing "outputs/stable-audio-3-blacksmith-crisp-v3/run/processing-result.json" --quality-report "outputs/stable-audio-3-blacksmith-crisp-v3/quality-report.json" --checks "outputs/stable-audio-3-blacksmith-crisp-v3/checks.json" --selected-candidate $SelectedCandidate --repo-root "." --out "outputs/stable-audio-3-blacksmith-crisp-v3/review.json" --now "2026-08-14T03:05:00Z"
python skills/forge-text-audio/scripts/run.py audio sfx validate --request "outputs/stable-audio-3-blacksmith-crisp-v3/request.json" --generation "outputs/stable-audio-3-blacksmith-crisp-v3/run/generation-result.json" --processing "outputs/stable-audio-3-blacksmith-crisp-v3/run/processing-result.json" --review "outputs/stable-audio-3-blacksmith-crisp-v3/review.json" --quality-report "outputs/stable-audio-3-blacksmith-crisp-v3/quality-report.json" --repo-root "." --final-dir "outputs/stable-audio-3-blacksmith-crisp-v3/final" --now "2026-08-14T03:06:00Z"
```

Replace the shown `candidate-01` value when the user approves candidate 02 or 03. Expected: review `approved: true`, validation `status: completed`, and quality `passed`.

- [ ] **Step 3: Add only the reviewed showcase artifacts**

Copy the validated selected WAV and its staging waveform/spectrum to the three `assets/readme/` names above. Do not copy raw candidates, failed candidates, request/state JSON, local configuration, model weights, or tokens.

- [ ] **Step 4: Update both READMEs**

Document the exact approved prompt, model, local GPU route, selected seed, 0.8-second format, `-1.0 dBFS` normalization, FFmpeg/FFprobe result, six-check listening approval, accepted SHA-256, WAV link, waveform, and spectrum. Keep the failed attempts out of the success showcase.

- [ ] **Step 5: Run final verification and commit**

```powershell
python -m unittest discover -s tests -q
python "C:\Users\QJX\.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills/forge-text-audio
git diff --check
git status --short
```

Review `git diff --name-status origin/main..main` and stage only the two READMEs plus the three accepted blacksmith showcase assets. Preserve the existing wooden UI click example and the unrelated Tilemap working-tree modification.

```powershell
git add README.md README.zh-CN.md assets/readme/stable-audio-3-small-sfx-blacksmith-strike.wav assets/readme/stable-audio-3-small-sfx-blacksmith-strike-waveform.png assets/readme/stable-audio-3-small-sfx-blacksmith-strike-spectrum.png
git diff --cached --check
git commit -m "docs: add verified stable audio showcases"
```
