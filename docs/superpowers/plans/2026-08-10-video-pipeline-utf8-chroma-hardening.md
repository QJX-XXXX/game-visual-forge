# Video Pipeline UTF-8 and Chroma Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `forge-video-to-sprite` provider subprocesses deterministic on Windows and prevent codec-shifted chroma-key pixels or resize fringes from reaching published sprite frames.

**Architecture:** Add one binary UTF-8 JSON process-protocol module shared by provider entry points and parent orchestrators, while keeping provider-specific submission recovery semantics in the existing callers. Centralize video chroma tolerance and transparent-pixel normalization in background processing, use premultiplied-alpha HD scaling, and assess every delivered frame density before publication.

**Tech Stack:** Python 3.12, standard-library `subprocess`/`json`/`io`, Pillow, NumPy, `unittest`, existing game-visual-forge contracts and quality reports.

## Global Constraints

- Provider stdin and stdout are strict UTF-8 JSON bytes; successful responses end with exactly one newline.
- Provider stderr is diagnostic-only and is decoded with UTF-8 replacement so a non-UTF-8 diagnostic cannot crash orchestration.
- Invalid UTF-8 stdout is a protocol failure; MiniMax/Jimeng submit paths retain the existing `submission_unknown` recovery semantics.
- Do not automatically retry a paid request or switch provider/backend after a task has been created.
- Chroma cleanup uses the request's configured RGB key color and a shared video tolerance of `80`; it must not contain magenta-specific channel rules.
- Every fully transparent output pixel has RGB `(0, 0, 0)`.
- HD delivery scaling is premultiplied-alpha-safe; pixel-mode scaling remains nearest-neighbor.
- `chroma-residue` fails when any delivered frame in any requested density has more than `1.0%` visible near-key pixels, and a failed deterministic check blocks publication.
- Preserve `preserve` and `rembg` behavior except for transparent-pixel RGB normalization at the shared delivery boundary.
- Add no runtime dependency and make no paid or live provider request in tests.
- Stage and commit only the files listed by each task; do not stage the unrelated adaptive-map evidence or README report files already present in the worktree.

---

### Task 1: Binary UTF-8 JSON process protocol

**Files:**
- Create: `src/game_visual_forge/providers/stdio.py`
- Create: `tests/test_provider_stdio.py`

**Interfaces:**
- Consumes: Python binary streams with `read() -> bytes` / `write(bytes)`, an argv sequence, a JSON-object payload, and a timeout.
- Produces: `read_utf8_json(stream: BinaryIO | TextIO | None = None) -> dict[str, Any]`, `write_utf8_json(value: dict[str, Any], stream: BinaryIO | TextIO | None = None) -> None`, `Utf8JsonProcessResult(returncode: int, stdout: str, stderr: str)`, and `run_utf8_json_process(argv: Sequence[str], payload: dict[str, Any], *, timeout_seconds: int) -> Utf8JsonProcessResult`.

- [ ] **Step 1: Write focused failing tests for strict child I/O and byte-mode parent execution**

```python
from __future__ import annotations

import io
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from tests._bootstrap import ROOT

from game_visual_forge.providers.stdio import (
    read_utf8_json,
    run_utf8_json_process,
    write_utf8_json,
)


class ProviderStdioTests(unittest.TestCase):
    def test_child_protocol_round_trips_unicode_as_utf8_bytes(self) -> None:
        request = read_utf8_json(io.BytesIO('{"prompt":"白发少女“向右”挥剑—三连斩"}'.encode("utf-8")))
        output = io.BytesIO()
        write_utf8_json({"schema_version": 1, "echo": request["prompt"]}, output)
        self.assertEqual(
            output.getvalue(),
            '{"schema_version":1,"echo":"白发少女“向右”挥剑—三连斩"}\n'.encode("utf-8"),
        )

    def test_child_protocol_rejects_non_object_json(self) -> None:
        with self.assertRaisesRegex(ValueError, "JSON object"):
            read_utf8_json(io.BytesIO(b"[]"))

    def test_child_protocol_retains_text_stream_fallback_for_in_process_tests(self) -> None:
        request = read_utf8_json(io.StringIO('{"prompt":"白发少女"}'))
        output = io.StringIO()
        write_utf8_json({"schema_version": 1, "prompt": request["prompt"]}, output)
        self.assertEqual(json.loads(output.getvalue())["prompt"], "白发少女")

    def test_parent_uses_bytes_and_replaces_invalid_stderr(self) -> None:
        completed = subprocess.CompletedProcess(
            ["provider"], 0, b'{"schema_version":1}\n', b"diagnostic:\x81",
        )
        with patch("game_visual_forge.providers.stdio.subprocess.run", return_value=completed) as run:
            result = run_utf8_json_process(
                ["provider", "preflight"],
                {"prompt": "白发少女"},
                timeout_seconds=30,
            )
        self.assertIsInstance(run.call_args.kwargs["input"], bytes)
        self.assertFalse(run.call_args.kwargs["text"])
        self.assertIn("白发少女".encode("utf-8"), run.call_args.kwargs["input"])
        self.assertEqual(result.stdout, '{"schema_version":1}\n')
        self.assertEqual(result.stderr, "diagnostic:\ufffd")

    def test_parent_rejects_invalid_utf8_stdout(self) -> None:
        completed = subprocess.CompletedProcess(["provider"], 0, b"\x81", b"")
        with patch("game_visual_forge.providers.stdio.subprocess.run", return_value=completed):
            with self.assertRaises(UnicodeDecodeError):
                run_utf8_json_process(["provider"], {}, timeout_seconds=30)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new tests and verify the module is missing**

Run: `python -m unittest tests.test_provider_stdio -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'game_visual_forge.providers.stdio'`.

- [ ] **Step 3: Implement the shared binary protocol**

```python
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, BinaryIO, Sequence, TextIO


def _encode(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def read_utf8_json(stream: BinaryIO | TextIO | None = None) -> dict[str, Any]:
    source = stream if stream is not None else sys.stdin.buffer
    raw = source.read()
    value = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    if not isinstance(value, dict):
        raise ValueError("provider command payload must be a JSON object")
    return value


def write_utf8_json(value: dict[str, Any], stream: BinaryIO | TextIO | None = None) -> None:
    target = stream if stream is not None else sys.stdout.buffer
    encoded = _encode(value)
    try:
        target.write(encoded)
    except TypeError:
        target.write(encoded.decode("utf-8"))
    target.flush()


@dataclass(frozen=True)
class Utf8JsonProcessResult:
    returncode: int
    stdout: str
    stderr: str


def run_utf8_json_process(
    argv: Sequence[str],
    payload: dict[str, Any],
    *,
    timeout_seconds: int,
) -> Utf8JsonProcessResult:
    completed = subprocess.run(
        list(argv),
        input=_encode(payload),
        capture_output=True,
        text=False,
        timeout=timeout_seconds,
        shell=False,
        check=False,
    )
    return Utf8JsonProcessResult(
        completed.returncode,
        completed.stdout.decode("utf-8", errors="strict"),
        completed.stderr.decode("utf-8", errors="replace"),
    )
```

- [ ] **Step 4: Run the focused tests and verify all protocol cases pass**

Run: `python -m unittest tests.test_provider_stdio -v`

Expected: 5 tests PASS.

- [ ] **Step 5: Commit the shared protocol independently**

```powershell
git add -- src/game_visual_forge/providers/stdio.py tests/test_provider_stdio.py
git commit -m "fix: standardize provider utf8 subprocess protocol"
```

---

### Task 2: MiniMax and Jimeng provider entry points

**Files:**
- Modify: `src/game_visual_forge/providers/minimax_video.py`
- Modify: `src/game_visual_forge/providers/jimeng_video.py`
- Modify: `skills/forge-video-to-sprite/scripts/providers/minimax.py`
- Modify: `skills/forge-video-to-sprite/scripts/providers/jimeng.py`
- Modify: `tests/test_minimax_video_provider.py`
- Modify: `tests/test_jimeng_video_provider.py`
- Modify: `tests/test_skill_contracts.py`

**Interfaces:**
- Consumes: Task 1 `read_utf8_json` and `write_utf8_json`; existing `run_command(command: str, payload: dict[str, Any]) -> dict[str, Any]` functions.
- Produces: both provider modules expose `main(argv: list[str] | None = None, input_stream: BinaryIO | TextIO | None = None, output_stream: BinaryIO | TextIO | None = None) -> int`; both skill launchers delegate to that `main()` without parsing text-mode JSON themselves.

- [ ] **Step 1: Add failing Unicode main tests for both providers**

```python
# tests/test_minimax_video_provider.py
import io
from unittest.mock import patch

from game_visual_forge.providers.minimax_video import main


def test_main_round_trips_unicode_through_shared_binary_protocol(self) -> None:
    source = io.BytesIO('{"schema_version":1,"prompt":"白发少女三连斩"}'.encode("utf-8"))
    target = io.BytesIO()
    with patch(
        "game_visual_forge.providers.minimax_video.run_command",
        return_value={"schema_version": 1, "message": "提交成功"},
    ):
        self.assertEqual(main(["preflight"], source, target), 0)
    self.assertEqual(json.loads(target.getvalue().decode("utf-8"))["message"], "提交成功")
```

```python
# tests/test_jimeng_video_provider.py
import io

from game_visual_forge.providers.jimeng_video import main


def test_main_round_trips_unicode_through_shared_binary_protocol(self) -> None:
    source = io.BytesIO('{"schema_version":1,"prompt":"白发少女三连斩"}'.encode("utf-8"))
    target = io.BytesIO()
    with patch(
        "game_visual_forge.providers.jimeng_video.run_command",
        return_value={"schema_version": 1, "message": "提交成功"},
    ):
        self.assertEqual(main(["preflight"], source, target), 0)
    self.assertEqual(json.loads(target.getvalue().decode("utf-8"))["message"], "提交成功")
```

Add a skill-contract assertion that both launcher files import `main` from their repository provider module and contain `raise SystemExit(main())`.

- [ ] **Step 2: Run provider and contract tests to expose Jimeng text-mode divergence**

Run: `python -m unittest tests.test_minimax_video_provider tests.test_jimeng_video_provider tests.test_skill_contracts -v`

Expected: the Jimeng `main` import/test FAILS; the MiniMax behavior either fails on the new injectable stream signature or passes only after using the shared helper.

- [ ] **Step 3: Refactor both provider modules and launchers onto the shared protocol**

Use this exact MiniMax entry point after importing `BinaryIO`, `TextIO`, `read_utf8_json`, and `write_utf8_json`:

```python
def main(
    argv: list[str] | None = None,
    input_stream: BinaryIO | TextIO | None = None,
    output_stream: BinaryIO | TextIO | None = None,
) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        raise SystemExit("usage: minimax_video.py <command>")
    payload = read_utf8_json(input_stream)
    try:
        result = run_command(arguments[0], payload)
    except urllib.error.HTTPError as error:
        result = _http_rejection(error) if 400 <= error.code < 500 else _transport_unknown(error)
    except Exception as error:
        if arguments[0] != "submit":
            raise
        result = _transport_unknown(error)
    write_utf8_json(result, output_stream)
    return 0
```

Use this exact Jimeng entry point after importing `BinaryIO`, `TextIO`, `read_utf8_json`, and `write_utf8_json`:

```python
def main(
    argv: list[str] | None = None,
    input_stream: BinaryIO | TextIO | None = None,
    output_stream: BinaryIO | TextIO | None = None,
) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        raise SystemExit("usage: jimeng_video.py <command>")
    payload = read_utf8_json(input_stream)
    write_utf8_json(run_command(arguments[0], payload), output_stream)
    return 0
```

Reduce the MiniMax launcher after its existing `sys.path` bootstrap to:

```python
from game_visual_forge.providers.minimax_video import main


if __name__ == "__main__":
    raise SystemExit(main())
```

Reduce the Jimeng launcher after its existing `sys.path` bootstrap to:

```python
from game_visual_forge.providers.jimeng_video import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run provider and skill-contract tests**

Run: `python -m unittest tests.test_minimax_video_provider tests.test_jimeng_video_provider tests.test_skill_contracts -v`

Expected: all tests PASS, including MiniMax rejection/transport recovery tests and both Unicode round trips.

- [ ] **Step 5: Commit provider entry-point convergence**

```powershell
git add -- src/game_visual_forge/providers/minimax_video.py src/game_visual_forge/providers/jimeng_video.py skills/forge-video-to-sprite/scripts/providers/minimax.py skills/forge-video-to-sprite/scripts/providers/jimeng.py tests/test_minimax_video_provider.py tests/test_jimeng_video_provider.py tests/test_skill_contracts.py
git commit -m "fix: unify video provider utf8 entrypoints"
```

---

### Task 3: Parent orchestration protocol and recovery semantics

**Files:**
- Create: `tests/fixtures/fake_utf8_provider.py`
- Modify: `src/game_visual_forge/providers/video.py`
- Modify: `src/game_visual_forge/providers/cli.py`
- Modify: `tests/test_provider_stdio.py`
- Modify: `tests/test_video_provider_orchestration.py`
- Modify: `tests/test_provider_cli.py`

**Interfaces:**
- Consumes: Task 1 `run_utf8_json_process(...) -> Utf8JsonProcessResult`; existing `_argv`, `_assert_safe`, `ForgeError`, `ErrorCode`, and `ProviderCommand` behavior.
- Produces: generic and video parent orchestrators send byte-mode UTF-8 requests; strict stdout protocol failures are mapped without altering paid-submit recovery state.

- [ ] **Step 1: Create a local zero-network provider fixture and failing end-to-end tests**

```python
# tests/fixtures/fake_utf8_provider.py
from __future__ import annotations

import json
import sys


payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
mode = payload.get("fixture_mode")
if mode == "invalid-stdout":
    sys.stdout.buffer.write(b"\x81")
elif mode == "invalid-stderr":
    sys.stderr.buffer.write(b"provider:\x81")
    sys.stdout.buffer.write(b'{"schema_version":1,"available":true}\n')
else:
    sys.stdout.buffer.write(
        (json.dumps({"schema_version": 1, "prompt": payload.get("prompt")}, ensure_ascii=False) + "\n").encode("utf-8")
    )
```

```python
# tests/test_provider_stdio.py
def test_real_local_subprocess_round_trips_unicode(self) -> None:
    fixture = ROOT / "tests" / "fixtures" / "fake_utf8_provider.py"
    result = run_utf8_json_process(
        [sys.executable, str(fixture), "preflight"],
        {"prompt": "白发少女", "fixture_mode": "invalid-stderr"},
        timeout_seconds=30,
    )
    self.assertEqual(json.loads(result.stdout)["available"], True)
    self.assertEqual(result.stderr, "provider:\ufffd")
```

In `tests/test_video_provider_orchestration.py`, patch `run_utf8_json_process` to raise `UnicodeDecodeError("utf-8", b"\x81", 0, 1, "invalid start byte")` and add this complete state-machine test:

```python
def test_invalid_utf8_submit_stdout_becomes_submission_unknown(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        root = Path(directory)
        attempt_path, confirmation_path, _ = self.setup_paths(root)
        decode_error = UnicodeDecodeError("utf-8", b"\x81", 0, 1, "invalid start byte")
        with patch("game_visual_forge.providers.video.run_utf8_json_process", side_effect=decode_error):
            result = submit_video_attempt(attempt_path, confirmation_path, FAKE, now=NOW)
        self.assertEqual(result.status, VideoAttemptStatus.SUBMISSION_UNKNOWN)
        self.assertEqual(result.error_code, ErrorCode.SUBMISSION_UNKNOWN.value)
```

In `tests/test_provider_cli.py`, add these exact cases:

```python
UTF8_FAKE = ROOT / "tests" / "fixtures" / "fake_utf8_provider.py"


def test_invalid_utf8_stdout_is_recoverable_provider_failure(self) -> None:
    decode_error = UnicodeDecodeError("utf-8", b"\x81", 0, 1, "invalid start byte")
    with patch("game_visual_forge.providers.cli.run_utf8_json_process", side_effect=decode_error):
        with self.assertRaises(ForgeError) as caught:
            run_provider_command(FAKE, ProviderCommand.PREFLIGHT, {"schema_version": 1})
    self.assertEqual(caught.exception.code, ErrorCode.PROVIDER_UNAVAILABLE)
    self.assertTrue(caught.exception.recoverable)

def test_non_utf8_stderr_does_not_hide_valid_stdout(self) -> None:
    result = run_provider_command(
        UTF8_FAKE,
        ProviderCommand.PREFLIGHT,
        {"schema_version": 1, "fixture_mode": "invalid-stderr"},
    )
    self.assertTrue(result["available"])
```

Import `patch` from `unittest.mock` in this test module.

- [ ] **Step 2: Run the focused parent-process tests**

Run: `python -m unittest tests.test_provider_stdio tests.test_video_provider_orchestration tests.test_provider_cli -v`

Expected: FAIL because both parent modules still invoke text-mode `subprocess.run` with `encoding="utf-8"` directly and do not consistently map `UnicodeDecodeError`.

- [ ] **Step 3: Route both parent callers through the binary helper**

Replace direct subprocess calls with:

```python
result = run_utf8_json_process(
    _argv(executable, command),
    payload,
    timeout_seconds=timeout_seconds,
)
```

In `providers/video.py`, add the strict-decode branch beside the existing timeout/launch branches:

```python
except UnicodeDecodeError as error:
    if command is ProviderCommand.SUBMIT:
        raise ForgeError(
            ErrorCode.SUBMISSION_UNKNOWN,
            "provider submit outcome is unknown",
            recoverable=True,
            context={"command": command.value},
        ) from error
    raise ForgeError(
        ErrorCode.PROVIDER_UNAVAILABLE,
        "provider returned invalid UTF-8",
        recoverable=True,
        context={"command": command.value},
    ) from error
```

Leave the existing `json.loads(result.stdout)` and response-schema validation after return-code handling. Its `JSONDecodeError` branch already maps submit to `SUBMISSION_UNKNOWN`; do not combine submit and non-submit messages.

In `providers/cli.py`, add:

```python
except UnicodeDecodeError as error:
    raise ForgeError(
        ErrorCode.PROVIDER_UNAVAILABLE,
        f"provider command returned invalid UTF-8: {command.value}",
        recoverable=True,
        context={"command": command.value},
    ) from error
```

Continue scanning replacement-decoded `result.stderr` and strict-decoded `result.stdout` for sensitive output.

- [ ] **Step 4: Run the parent-process tests and existing paid-state tests**

Run: `python -m unittest tests.test_provider_stdio tests.test_video_provider_orchestration tests.test_provider_cli tests.test_video_provider_contract -v`

Expected: all tests PASS; the real subprocess test proves the Windows-relevant byte boundary and the paid-submit tests prove there is no automatic retry.

- [ ] **Step 5: Commit the parent protocol integration**

```powershell
git add -- src/game_visual_forge/providers/video.py src/game_visual_forge/providers/cli.py tests/fixtures/fake_utf8_provider.py tests/test_provider_stdio.py tests/test_video_provider_orchestration.py tests/test_provider_cli.py
git commit -m "fix: harden provider subprocess decoding"
```

---

### Task 4: Generic chroma cleanup and alpha-safe delivery scaling

**Files:**
- Modify: `src/game_visual_forge/processing/background.py`
- Modify: `src/game_visual_forge/processing/video_sprite.py`
- Modify: `tests/test_video_processing.py`

**Interfaces:**
- Consumes: Pillow RGBA images, NumPy, `VideoSpriteRequest.chroma_color`, and `VideoProcessingMode`.
- Produces: `VIDEO_CHROMA_TOLERANCE = 80`, `clear_transparent_rgb(image: Any) -> Any`, and `resize_rgba_alpha_safe(image: Any, size: tuple[int, int], *, resample: Any) -> Any`; `remove_chroma` zeroes hidden RGB whenever it clears alpha.

- [ ] **Step 1: Add failing cleanup, key-color, and scaling regression tests**

```python
def test_chroma_cleanup_supports_non_magenta_codec_drift(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        root = Path(directory)
        request = VideoSpriteRequest.from_dict(valid_request(
            background_mode="chroma",
            chroma_color="#00ff00",
            processing_mode="hd",
            frame_counts=[4],
            canvas_width=64,
            canvas_height=64,
            output_dir="outputs/green-key",
        ))
        result = process_video_sprite(
            root,
            request,
            source_record(root),
            make_raw_frames(root, background=(3, 252, 5, 255)),
            frame_counts=(4,),
        )
        with Image.open(root / result.artifacts["frames:4"] / "frame-000.png").convert("RGBA") as image:
            visible_green = sum(
                1 for red, green, blue, alpha in image.getdata()
                if alpha >= 8 and green > 180 and green > red + 60 and green > blue + 60
            )
        self.assertEqual(visible_green, 0)

def test_hd_scaling_does_not_bleed_hidden_key_rgb(self) -> None:
    image = Image.new("RGBA", (8, 8), (255, 0, 255, 0))
    for x in range(2, 6):
        for y in range(2, 6):
            image.putpixel((x, y), (240, 240, 240, 255))
    scaled = resize_rgba_alpha_safe(image, (31, 31), resample=Image.Resampling.LANCZOS)
    self.assertTrue(all(pixel[:3] == (0, 0, 0) for pixel in scaled.getdata() if pixel[3] == 0))
    self.assertFalse(any(red > 120 and blue > 120 and green < 80 and alpha > 0 for red, green, blue, alpha in scaled.getdata()))

def test_pixel_mode_still_uses_nearest_neighbor(self) -> None:
    image = Image.new("RGBA", (2, 2), (0, 0, 0, 255))
    image.putpixel((0, 0), (255, 255, 255, 255))
    scaled = resize_rgba_alpha_safe(image, (8, 8), resample=Image.Resampling.NEAREST)
    visible_rgb = {pixel[:3] for pixel in scaled.getdata() if pixel[3] > 0}
    self.assertEqual(visible_rgb, {(255, 255, 255), (0, 0, 0)})

def test_preserve_mode_keeps_opaque_source_background(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        root = Path(directory)
        request = VideoSpriteRequest.from_dict(valid_request(
            background_mode="preserve",
            processing_mode="hd",
            frame_counts=[4],
            canvas_width=48,
            canvas_height=48,
            output_dir="outputs/preserve-regression",
        ))
        result = process_video_sprite(root, request, source_record(root), make_raw_frames(root), frame_counts=(4,))
        with Image.open(root / result.artifacts["frames:4"] / "frame-000.png").convert("RGBA") as image:
            self.assertEqual(image.getchannel("A").getextrema(), (255, 255))

def test_rembg_callback_contract_is_unchanged(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        root = Path(directory)
        request = VideoSpriteRequest.from_dict(valid_request(
            background_mode="rembg",
            chroma_color=None,
            processing_mode="hd",
            frame_counts=[4],
            output_dir="outputs/rembg-regression",
        ))

        def remover(image, request):
            cleaned = image.convert("RGBA")
            cleaned.putalpha(128)
            return cleaned, "test-rembg", False

        result = process_video_sprite(
            root,
            request,
            source_record(root),
            make_raw_frames(root),
            frame_counts=(4,),
            remover=remover,
        )
        self.assertFalse(result.needs_attention)
        self.assertEqual(set(result.cleanup_methods), {"test-rembg"})
```

- [ ] **Step 2: Run processing tests and verify the current magenta-specific post-filter fails**

Run: `python -m unittest tests.test_video_processing -v`

Expected: the green-key and hidden-RGB assertions FAIL; the current `_clear_resampled_chroma_residue` only recognizes magenta-like channels.

- [ ] **Step 3: Centralize tolerance, zero transparent RGB, and use premultiplied alpha**

Add to `background.py`:

```python
VIDEO_CHROMA_TOLERANCE = 80


def clear_transparent_rgb(image: Any) -> Any:
    import numpy as np
    from PIL import Image

    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    rgba[rgba[:, :, 3] == 0, :3] = 0
    return Image.fromarray(rgba, mode="RGBA")


def resize_rgba_alpha_safe(image: Any, size: tuple[int, int], *, resample: Any) -> Any:
    from PIL import Image

    rgba = image.convert("RGBA")
    if resample == Image.Resampling.NEAREST:
        return clear_transparent_rgb(rgba.resize(size, resample=resample))
    premultiplied = rgba.convert("RGBa")
    return clear_transparent_rgb(premultiplied.resize(size, resample=resample).convert("RGBA"))
```

Update both NumPy and Pillow branches of `remove_chroma` so every pixel whose alpha becomes zero also receives RGB `(0, 0, 0)`. In `video_sprite.py`, use `VIDEO_CHROMA_TOLERANCE` in `_video_background`, call `resize_rgba_alpha_safe` in `_delivery_frames`, and replace `_clear_resampled_chroma_residue` with a generic post-resize `remove_chroma(scaled, request.chroma_color or "#ff00ff", tolerance=VIDEO_CHROMA_TOLERANCE)` call only for chroma mode. Do not add any channel-order rule for a particular key color.

- [ ] **Step 4: Run processing and existing background-removal tests**

Run: `python -m unittest tests.test_video_processing tests.test_sprite_processing -v`

Expected: all tests PASS, including codec drift, green key, HD fringe, pixel nearest-neighbor, rembg failure reporting, and preserve-background coverage.

- [ ] **Step 5: Commit generic cleanup and alpha-safe scaling**

```powershell
git add -- src/game_visual_forge/processing/background.py src/game_visual_forge/processing/video_sprite.py tests/test_video_processing.py
git commit -m "fix: prevent chroma bleed in video sprite frames"
```

---

### Task 5: Every-density chroma quality gate

**Files:**
- Modify: `src/game_visual_forge/quality/video.py`
- Modify: `tests/test_video_quality.py`

**Interfaces:**
- Consumes: Task 4 `VIDEO_CHROMA_TOLERANCE`, `processing.artifacts` entries named `frames:<density>`, `request.frame_counts`, and `MAX_VIDEO_CHROMA_RESIDUE_PERCENT = 1.0`.
- Produces: `_delivery_frame_paths(root: Path, processing: Any) -> dict[int, tuple[Path, ...]]`; deterministic frame-count/readability/dimension/transparency/chroma checks cover every delivered density, while temporal metrics continue to use the highest-density timeline.

- [ ] **Step 1: Add failing all-density and threshold-boundary tests**

```python
def test_chroma_residue_checks_lower_density_not_only_highest(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        root = Path(directory)
        source = source_record(root)
        request = VideoSpriteRequest.from_dict(valid_request(
            background_mode="chroma",
            chroma_color="#ff00ff",
            frame_counts=[2, 4],
            canvas_width=48,
            canvas_height=48,
            output_dir="outputs/all-density-residue",
        ))
        processing = process_video_sprite(
            root,
            request,
            source,
            make_raw_frames(root),
            frame_counts=(2, 4),
        )
        low_path = root / processing.artifacts["frames:2"] / "frame-000.png"
        Image.new("RGBA", (48, 48), (255, 0, 255, 255)).save(low_path)
        report = assess_video_outputs(root, request, source, processing)
        check = next(item for item in report.deterministic_checks if item.check_id == "chroma-residue")
        self.assertEqual(check.status, QualityStatus.FAILED)
        self.assertIn("density 2", check.message)

def test_chroma_residue_uses_configured_non_magenta_key(self) -> None:
    image = Image.new("RGBA", (10, 10), (0, 255, 0, 255))
    self.assertEqual(_visible_chroma_residue_percent(image, "#00ff00"), 100.0)

def test_chroma_residue_threshold_allows_one_percent_and_rejects_more(self) -> None:
    image = Image.new("RGBA", (10, 10), (255, 255, 255, 255))
    image.putpixel((0, 0), (254, 0, 253, 255))
    self.assertEqual(_visible_chroma_residue_percent(image, "#ff00ff"), 1.0)
    image.putpixel((1, 0), (254, 0, 253, 255))
    self.assertGreater(_visible_chroma_residue_percent(image, "#ff00ff"), 1.0)

def test_failed_chroma_residue_prevents_publication(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        root = Path(directory)
        source = source_record(root)
        request = VideoSpriteRequest.from_dict(valid_request(
            background_mode="chroma",
            chroma_color="#ff00ff",
            frame_counts=[4],
            canvas_width=48,
            canvas_height=48,
            output_dir="outputs/publication-block",
        ))
        processing = process_video_sprite(root, request, source, make_raw_frames(root), frame_counts=(4,))
        frame_path = root / processing.artifacts["frames:4"] / "frame-000.png"
        Image.new("RGBA", (48, 48), (255, 0, 255, 255)).save(frame_path)
        report = assess_video_outputs(root, request, source, processing)
        manifest = build_video_asset_manifest(root, request, source, processing, report)
        self.assertEqual(report.deterministic_status, QualityStatus.FAILED)
        self.assertFalse(publish_video_outputs(root / processing.staging_dir, root / request.output_dir, report, manifest))
```

Import Pillow `Image` and `_visible_chroma_residue_percent` explicitly at the top of `tests/test_video_quality.py`; reuse the file's existing `source_record`, `make_raw_frames`, `valid_request`, and manifest imports.

- [ ] **Step 2: Run the quality tests and verify only-highest-density behavior is exposed**

Run: `python -m unittest tests.test_video_quality -v`

Expected: the lower-density test FAILS because `assess_video_outputs` currently iterates only `max(request.frame_counts)`.

- [ ] **Step 3: Collect and validate all density directories**

Implement:

```python
def _delivery_frame_paths(root: Path, processing: Any) -> dict[int, tuple[Path, ...]]:
    result: dict[int, tuple[Path, ...]] = {}
    for role, relative in processing.artifacts.items():
        if not role.startswith("frames:"):
            continue
        density = int(role.split(":", 1)[1])
        result[density] = tuple(sorted((root / relative).glob("frame-*.png")))
    return result
```

Use `VIDEO_CHROMA_TOLERANCE` and Euclidean RGB distance in `_visible_chroma_residue_percent` so QA matches Task 4 cleanup. Iterate every path in the collected density mapping for frame count, readability, dimensions, transparency, and residue. Track `(ratio, density, path)` and report the maximum, for example `visible chroma residue is at most 1.0% (measured 2.0000% at density 2 frame-000.png)`. Keep `>` rather than `>=` so exactly `1.0%` passes. Load only the highest-density frames for temporal metrics.

The collection and maximum-selection body must use these concrete values:

```python
delivery_paths = _delivery_frame_paths(root, processing)
expected_counts = set(request.frame_counts)
counts_match = set(delivery_paths) == expected_counts and all(
    len(delivery_paths[density]) == density for density in expected_counts
)
all_density_paths = tuple(
    (density, path)
    for density in sorted(delivery_paths)
    for path in delivery_paths[density]
)

def measure_path(path: Path, color: str) -> float:
    with Image.open(path) as opened:
        return _visible_chroma_residue_percent(
            opened,
            color,
            tolerance=VIDEO_CHROMA_TOLERANCE,
        )

residue_measurements = tuple(
    (measure_path(path, request.chroma_color), density, path)
    for density, path in all_density_paths
)
maximum_residue, residue_density, residue_path = max(
    residue_measurements,
    default=(0.0, max(request.frame_counts), Path("no-frame")),
)
residue_status = (
    QualityStatus.FAILED
    if maximum_residue > MAX_VIDEO_CHROMA_RESIDUE_PERCENT
    else QualityStatus.PASSED
)
residue_message = (
    f"visible chroma residue is at most {MAX_VIDEO_CHROMA_RESIDUE_PERCENT:.1f}% "
    f"(measured {maximum_residue:.4f}% at density {residue_density} {residue_path.name})"
)
```

Implement `_visible_chroma_residue_percent` with squared Euclidean RGB distance:

```python
rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
target = np.asarray([int(color[index:index + 2], 16) for index in (1, 3, 5)], dtype=np.int32)
distance_squared = np.sum((rgba[:, :, :3].astype(np.int32) - target) ** 2, axis=2)
visible = rgba[:, :, 3] >= 8
visible_count = int(np.count_nonzero(visible))
if visible_count == 0:
    return 0.0
residue_count = int(np.count_nonzero(visible & (distance_squared <= int(tolerance) ** 2)))
return round(100.0 * residue_count / visible_count, 4)
```

Set `highest_paths = delivery_paths.get(max(request.frame_counts), ())` and pass only those context-managed RGBA copies to `calculate_temporal_metrics`.

- [ ] **Step 4: Verify gate behavior and publication blocking**

Run: `python -m unittest tests.test_video_quality tests.test_video_processing -v`

Expected: all tests PASS. The new publication test proves `publish_video_outputs` returns `False` for a deterministic `chroma-residue` failure.

- [ ] **Step 5: Commit the all-density quality gate**

```powershell
git add -- src/game_visual_forge/quality/video.py tests/test_video_quality.py
git commit -m "fix: gate chroma residue across video frame densities"
```

---

### Task 6: Skill guidance and repository-wide verification

**Files:**
- Modify: `skills/forge-video-to-sprite/SKILL.md`
- Modify: `skills/forge-video-to-sprite/references/provider-workflow.md`
- Modify: `skills/forge-video-to-sprite/references/processing-and-quality.md`
- Modify: `tests/test_skill_contracts.py`

**Interfaces:**
- Consumes: Tasks 1-5 final protocol and quality behavior.
- Produces: concise user-facing skill rules plus detailed provider/processing reference documentation that matches the executable behavior.

- [ ] **Step 1: Add failing skill-contract assertions for the new guarantees**

```python
def test_video_skill_documents_utf8_and_all_density_chroma_gate(self) -> None:
    skill = (ROOT / "skills" / "forge-video-to-sprite" / "SKILL.md").read_text(encoding="utf-8")
    provider = (ROOT / "skills" / "forge-video-to-sprite" / "references" / "provider-workflow.md").read_text(encoding="utf-8")
    quality = (ROOT / "skills" / "forge-video-to-sprite" / "references" / "processing-and-quality.md").read_text(encoding="utf-8")
    self.assertIn("UTF-8", skill)
    self.assertIn("binary UTF-8 JSON", provider)
    self.assertIn("every requested density", quality)
    self.assertIn("1.0%", quality)
```

- [ ] **Step 2: Run the contract test and verify the guarantees are not yet documented**

Run: `python -m unittest tests.test_skill_contracts -v`

Expected: FAIL on one or more new documentation assertions.

- [ ] **Step 3: Add concise skill text and exact reference details**

Add one concise invariant to `SKILL.md`:

```markdown
- Provider subprocesses use binary UTF-8 JSON, and chroma delivery must pass the all-density residue gate before publication.
```

Add to `references/provider-workflow.md`:

```markdown
## Local subprocess protocol

Repository provider launchers and their parent orchestrators exchange one JSON
object over binary UTF-8 stdin/stdout. Successful stdout ends with one newline.
Stdout decoding is strict; stderr is diagnostic-only and uses replacement for
invalid bytes. A malformed submit response remains `submission_unknown` and is
recovered only through query/download—never by automatic resubmission.
```

Add to `references/processing-and-quality.md`:

```markdown
Direct chroma cleanup uses the declared RGB key with tolerance 80 to absorb
codec drift, clears hidden RGB on transparent pixels, and uses premultiplied
alpha for HD resampling. Pixel mode remains nearest-neighbor. The deterministic
`chroma-residue` check examines every delivered frame at every requested density;
more than 1.0% visible near-key pixels in any frame fails publication.
```

- [ ] **Step 4: Run focused and full repository verification**

Run:

```powershell
python -m unittest tests.test_provider_stdio tests.test_minimax_video_provider tests.test_jimeng_video_provider tests.test_provider_cli tests.test_video_provider_orchestration tests.test_video_processing tests.test_video_quality tests.test_skill_contracts -v
python -m unittest discover -s tests -q
python "C:\Users\QJX\.codex\skills\.system\skill-creator\scripts\quick_validate.py" "skills\forge-video-to-sprite"
```

Expected: every command exits `0`; the full suite reports no failures/errors; skill validation reports the skill is valid.

- [ ] **Step 5: Inspect scope, commit the documentation, and record the verification**

Run:

```powershell
git diff --check
git status --short
git add -- skills/forge-video-to-sprite/SKILL.md skills/forge-video-to-sprite/references/provider-workflow.md skills/forge-video-to-sprite/references/processing-and-quality.md tests/test_skill_contracts.py
git commit -m "docs: document video protocol and chroma quality gate"
```

Expected: `git diff --check` is clean. The staged/committed scope excludes `assets/readme/adaptive-river-crossing-map-*` and any bridge-connectivity evidence.
