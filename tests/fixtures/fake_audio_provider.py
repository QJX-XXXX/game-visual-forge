from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import wave
from pathlib import Path


def read_payload() -> dict:
    raw = getattr(sys.stdin, "buffer", sys.stdin).read()
    return json.loads(raw.decode("utf-8"))


def write_result(value: dict) -> None:
    target = getattr(sys.stdout, "buffer", sys.stdout)
    target.write((json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8"))
    target.flush()


def main() -> int:
    payload = read_payload()
    command = sys.argv[1]
    log_path = payload.get("log_path")
    if log_path:
        with Path(log_path).open("a", encoding="utf-8") as handle:
            handle.write(command + "\n")
    if payload.get("env_log_path"):
        Path(payload["env_log_path"]).write_text(
            json.dumps({"python": sys.executable, "environment": {"GVF_TEST_CHILD": os.environ.get("GVF_TEST_CHILD")}}, ensure_ascii=False),
            encoding="utf-8",
        )
    if payload.get("sleep_seconds"):
        time.sleep(float(payload["sleep_seconds"]))
    if payload.get("invalid_utf8"):
        getattr(sys.stdout, "buffer", sys.stdout).write(b"\xff\xfe\n")
        return 0
    if payload.get("returncode"):
        sys.stderr.write("definite fake provider failure\n")
        return int(payload["returncode"])
    if command == "models":
        write_result({"schema_version": 1, "models": ["small-sfx"]})
        return 0
    if command == "preflight":
        write_result({
            "schema_version": 1,
            "provider": "stable-audio-local",
            "available": True,
            "python_executable": sys.executable,
            "package": "stable-audio-3",
            "package_version": "fake",
            "model_id": "small-sfx",
            "model_repository": "stabilityai/stable-audio-3-small-sfx",
            "model_local": True,
            "ffmpeg_available": True,
            "ffprobe_available": True,
            "reason": None,
        })
        return 0
    if command == "generate":
        target = Path(payload["output_path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(target), "wb") as handle:
            handle.setnchannels(2)
            handle.setsampwidth(2)
            handle.setframerate(44100)
            frames = max(1, int(round(float(payload.get("duration_seconds", 0.1)) * 44100)))
            handle.writeframes(b"\x00\x00\x00\x00" * frames)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        write_result({"schema_version": 1, "status": "completed", "path": str(target), "sha256": digest, "seed": payload["seed"]})
        return 0
    write_result({"schema_version": 1, "status": "failed", "reason": "unknown command"})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
