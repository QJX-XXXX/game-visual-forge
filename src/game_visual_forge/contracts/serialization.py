from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, TypeVar, overload


_Decoded = TypeVar("_Decoded")


def dump_json(path: Path, value: Any) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


@overload
def load_json(path: Path) -> dict[str, Any]: ...


@overload
def load_json(path: Path, decode: Callable[[dict[str, Any]], _Decoded]) -> _Decoded: ...


def load_json(path: Path, decode: Callable[[dict[str, Any]], _Decoded] | None = None) -> dict[str, Any] | _Decoded:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON document must be an object")
    if decode is None:
        return value
    try:
        return decode(value)
    except KeyError as error:
        raise ValueError(f"JSON input is missing a required field: {error}") from error
    except TypeError as error:
        raise ValueError("JSON input has an invalid field type") from error
