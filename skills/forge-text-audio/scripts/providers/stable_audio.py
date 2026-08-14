from __future__ import annotations

import importlib
import importlib.metadata
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


MODEL_ID = "small-sfx"
MODEL_REPOSITORY = "stabilityai/stable-audio-3-small-sfx"


def _set_offline_environment() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"


def _read_json() -> dict[str, Any]:
    raw = getattr(sys.stdin, "buffer", sys.stdin).read()
    value = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    if not isinstance(value, dict):
        raise ValueError("provider payload must be a JSON object")
    return value


def _write_json(value: dict[str, Any]) -> None:
    raw = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    target = getattr(sys.stdout, "buffer", sys.stdout)
    target.write(raw)
    target.flush()


def _tool_path(payload: dict[str, Any], key: str, default: str) -> str | None:
    configured = payload.get(key)
    if configured:
        candidate = Path(str(configured))
        if candidate.is_file():
            return str(candidate)
        return shutil.which(str(configured))
    return shutil.which(default)


def _preflight(payload: dict[str, Any]) -> dict[str, Any]:
    _set_offline_environment()
    ffmpeg = _tool_path(payload, "ffmpeg_executable", "ffmpeg")
    ffprobe = _tool_path(payload, "ffprobe_executable", "ffprobe")
    package_version = None
    reason = None
    model_local = False
    try:
        package_version = importlib.metadata.version("stable-audio-tools")
        importlib.import_module("stable_audio_tools")
        importlib.import_module("torch")
        importlib.import_module("torchaudio")
        from huggingface_hub import snapshot_download

        snapshot_download(MODEL_REPOSITORY, local_files_only=True)
        model_local = True
    except Exception as error:  # noqa: BLE001 - preflight reports actionable absence
        reason = f"{type(error).__name__}: {error}"
    available = bool(package_version and model_local and ffmpeg and ffprobe)
    if not available and reason is None:
        reason = "stable-audio-tools, local model, ffmpeg, and ffprobe are required"
    return {
        "schema_version": 1,
        "provider": "stable-audio-local",
        "available": available,
        "python_executable": sys.executable,
        "package": "stable-audio-tools" if package_version else None,
        "package_version": package_version,
        "model_id": MODEL_ID,
        "model_repository": MODEL_REPOSITORY,
        "model_local": model_local,
        "ffmpeg_available": bool(ffmpeg),
        "ffprobe_available": bool(ffprobe),
        "reason": reason,
    }


def _load_audio(path: str, torchaudio: Any) -> tuple[int, Any]:
    sample_rate, audio = torchaudio.load(path)
    return int(sample_rate), audio


def _generate(payload: dict[str, Any]) -> dict[str, Any]:
    _set_offline_environment()
    import inspect
    import torch
    import torchaudio
    from stable_audio_tools import get_pretrained_model
    from stable_audio_tools.inference.generation import generate_diffusion_cond, generate_diffusion_cond_inpaint

    mode = str(payload["mode"])
    model, model_config = get_pretrained_model(MODEL_REPOSITORY)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device).eval()
    sample_rate = int(model_config.get("sample_rate", getattr(model, "sample_rate", 44100)))
    duration = float(payload["duration_seconds"])
    sample_size = int(round(duration * sample_rate))
    conditioning = [{"prompt": str(payload["prompt"]), "seconds_start": 0.0, "seconds_total": duration}]
    seed = int(payload["seed"])
    torch.manual_seed(seed)
    if mode in {"text-to-audio", "redraw"}:
        kwargs: dict[str, Any] = {
            "model": model,
            "conditioning": conditioning,
            "sample_size": sample_size,
            "seed": seed,
            "device": device,
            "batch_size": 1,
        }
        if mode == "redraw":
            source_rate, source_audio = _load_audio(str(payload["source_path"]), torchaudio)
            kwargs["init_audio"] = (source_rate, source_audio.to(device))
            kwargs["init_noise_level"] = float(payload["redraw_strength"])
        audio = generate_diffusion_cond(**kwargs)
    else:
        source_rate, source_audio = _load_audio(str(payload["source_path"]), torchaudio)
        kwargs = {
            "model": model,
            "conditioning": conditioning,
            "sample_size": sample_size,
            "seed": seed,
            "device": device,
            "batch_size": 1,
            "inpaint_audio": (source_rate, source_audio.to(device)),
        }
        if mode == "inpaint":
            kwargs["inpaint_mask_start_seconds"] = float(payload["edit_start_seconds"])
            kwargs["inpaint_mask_end_seconds"] = float(payload["edit_end_seconds"])
        else:
            source_duration = float(payload.get("source_duration_seconds", 0.0))
            join_guard = float(payload.get("join_guard_ms", 20)) / 1000.0
            kwargs["inpaint_mask_start_seconds"] = max(0.0, source_duration - join_guard)
            kwargs["inpaint_mask_end_seconds"] = duration
        audio = generate_diffusion_cond_inpaint(**kwargs)
    if audio.ndim == 3:
        audio = audio[0]
    output = Path(str(payload["output_path"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(output), audio.detach().cpu(), sample_rate, encoding="PCM_F", bits_per_sample=32)
    return {"schema_version": 1, "status": "completed", "path": str(output), "seed": seed, "sample_rate": sample_rate, "signature_checked": {"conditional": str(inspect.signature(generate_diffusion_cond)), "inpaint": str(inspect.signature(generate_diffusion_cond_inpaint))}}


def main() -> int:
    payload = _read_json()
    command = sys.argv[1] if len(sys.argv) > 1 else "preflight"
    if command == "models":
        _write_json({"schema_version": 1, "models": [MODEL_ID], "model_repository": MODEL_REPOSITORY})
        return 0
    if command == "preflight":
        _write_json(_preflight(payload))
        return 0
    if command == "generate":
        _write_json(_generate(payload))
        return 0
    raise ValueError(f"unsupported provider command: {command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # noqa: BLE001 - JSON boundary reports failure through stderr
        print(f"stable audio provider failed: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1)
