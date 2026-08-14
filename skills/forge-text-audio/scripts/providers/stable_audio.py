from __future__ import annotations

import contextlib
import importlib.metadata
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


MODEL_ID = "small-sfx"
MODEL_REPOSITORY = "stabilityai/stable-audio-3-small-sfx"
PACKAGE_NAME = "stable-audio-3"


def _set_offline_environment() -> None:
    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
        }
    )


def _read_json() -> dict[str, Any]:
    raw = getattr(sys.stdin, "buffer", sys.stdin).read()
    value = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    if not isinstance(value, dict):
        raise ValueError("provider payload must be a JSON object")
    return value


def _write_json(value: dict[str, Any]) -> None:
    raw = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    target = getattr(sys.stdout, "buffer", sys.stdout)
    try:
        target.write(raw)
    except TypeError:
        target.write(raw.decode("utf-8"))
    target.flush()


def _tool_path(payload: dict[str, Any], key: str, default: str) -> str | None:
    configured = payload.get(key)
    if configured:
        candidate = Path(str(configured))
        if candidate.is_file():
            return str(candidate)
        return shutil.which(str(configured))
    return shutil.which(default)


def _load_backend() -> tuple[Any, Any, Any]:
    import torch
    import torchaudio
    from stable_audio_3 import StableAudioModel

    return StableAudioModel, torch, torchaudio


def _preflight(payload: dict[str, Any]) -> dict[str, Any]:
    _set_offline_environment()
    ffmpeg = _tool_path(payload, "ffmpeg_executable", "ffmpeg")
    ffprobe = _tool_path(payload, "ffprobe_executable", "ffprobe")
    package_version = None
    reason = None
    model_local = False
    cuda_available: bool | None = None
    device_name: str | None = None
    model_cache = os.environ.get("HUGGINGFACE_HUB_CACHE") or os.environ.get("HF_HOME")
    try:
        package_version = importlib.metadata.version(PACKAGE_NAME)
        _, torch, _ = _load_backend()
        cuda_available = bool(torch.cuda.is_available())
        if cuda_available:
            device_name = str(torch.cuda.get_device_name(0))
        from huggingface_hub import snapshot_download

        snapshot = Path(snapshot_download(MODEL_REPOSITORY, local_files_only=True))
        model_local = (snapshot / "model_config.json").is_file() and (snapshot / "model.safetensors").is_file()
        if not model_local:
            reason = "local Stable Audio 3 snapshot is incomplete"
    except Exception as error:  # noqa: BLE001 - preflight reports actionable absence
        reason = f"{type(error).__name__}: {error}"
    available = bool(package_version and model_local and ffmpeg and ffprobe)
    if not available and reason is None:
        reason = "stable-audio-3, local model, ffmpeg, and ffprobe are required"
    return {
        "schema_version": 1,
        "provider": "stable-audio-local",
        "available": available,
        "python_executable": sys.executable,
        "package": PACKAGE_NAME if package_version else None,
        "package_version": package_version,
        "model_id": MODEL_ID,
        "model_repository": MODEL_REPOSITORY,
        "model_local": model_local,
        "ffmpeg_available": bool(ffmpeg),
        "ffprobe_available": bool(ffprobe),
        "reason": reason,
        "runtime_root": payload.get("runtime_root"),
        "model_cache": model_cache,
        "cuda_available": cuda_available,
        "device_name": device_name,
    }


def _load_audio(path: str, torchaudio: Any) -> tuple[int, Any]:
    sample_rate, audio = torchaudio.load(path)
    return int(sample_rate), audio


def _generate(payload: dict[str, Any]) -> dict[str, Any]:
    _set_offline_environment()
    StableAudioModel, _, torchaudio = _load_backend()
    mode = str(payload["mode"])
    model = StableAudioModel.from_pretrained(MODEL_ID)
    duration = float(payload["duration_seconds"])
    seed = int(payload["seed"])
    kwargs: dict[str, Any] = {
        "prompt": str(payload["prompt"]),
        "duration": duration,
        "steps": 8,
        "cfg_scale": 1.0,
        "batch_size": 1,
        "sample_size": int(model.model_config["sample_size"]),
        "seed": seed,
    }
    if mode == "redraw":
        kwargs["init_audio"] = _load_audio(str(payload["source_path"]), torchaudio)
        kwargs["init_noise_level"] = float(payload["redraw_strength"])
    elif mode in {"inpaint", "continue"}:
        kwargs["inpaint_audio"] = _load_audio(str(payload["source_path"]), torchaudio)
        if mode == "inpaint":
            kwargs["inpaint_mask_start_seconds"] = float(payload["edit_start_seconds"])
            kwargs["inpaint_mask_end_seconds"] = float(payload["edit_end_seconds"])
        else:
            source_duration = float(payload.get("source_duration_seconds") or 0.0)
            join_guard = float(payload.get("join_guard_ms", 20)) / 1000.0
            kwargs["inpaint_mask_start_seconds"] = max(0.0, source_duration - join_guard)
            kwargs["inpaint_mask_end_seconds"] = duration
    audio = model.generate(**kwargs)
    if getattr(audio, "ndim", 0) == 3:
        audio = audio[0]
    output = Path(str(payload["output_path"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(output), audio.cpu(), int(model.model.sample_rate), encoding="PCM_F", bits_per_sample=32)
    return {
        "schema_version": 1,
        "status": "completed",
        "path": str(output),
        "seed": seed,
        "sample_rate": int(model.model.sample_rate),
    }


def main() -> int:
    payload = _read_json()
    command = sys.argv[1] if len(sys.argv) > 1 else "preflight"
    if command == "models":
        _write_json({"schema_version": 1, "models": [MODEL_ID], "model_repository": MODEL_REPOSITORY})
        return 0
    with contextlib.redirect_stdout(sys.stderr):
        if command == "preflight":
            result = _preflight(payload)
        elif command == "generate":
            result = _generate(payload)
        else:
            raise ValueError(f"unsupported provider command: {command}")
    _write_json(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # noqa: BLE001 - JSON boundary reports failure through stderr
        print(f"stable audio provider failed: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1)
