from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, BinaryIO, Mapping, Sequence, TextIO


def _encode(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def read_utf8_json(stream: BinaryIO | TextIO | None = None) -> dict[str, Any]:
    source = stream if stream is not None else getattr(sys.stdin, "buffer", sys.stdin)
    raw = source.read()
    value = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    if not isinstance(value, dict):
        raise ValueError("provider command payload must be a JSON object")
    return value


def write_utf8_json(value: dict[str, Any], stream: BinaryIO | TextIO | None = None) -> None:
    target = stream if stream is not None else getattr(sys.stdout, "buffer", sys.stdout)
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
    return Utf8JsonProcessResult(
        completed.returncode,
        completed.stdout.decode("utf-8", errors="strict"),
        completed.stderr.decode("utf-8", errors="replace"),
    )
