from __future__ import annotations

from pathlib import Path

from game_visual_forge.contracts.job import JobState
from game_visual_forge.contracts.serialization import dump_json, load_json


def save_job(path: Path, state: JobState) -> None:
    dump_json(path, state.to_dict())


def load_job(path: Path) -> JobState:
    return JobState.from_dict(load_json(path))
