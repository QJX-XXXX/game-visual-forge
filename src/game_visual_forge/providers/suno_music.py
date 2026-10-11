from __future__ import annotations

from pathlib import Path


_MISSING = ("official API documentation", "authenticated request schema", "vocal/instrumental field", "task recovery", "API commercial rights")


def preflight(payload):
    return {"status": "needs_user_action", "reason": "Suno official API schema is gated by account access", "missing": list(_MISSING), "official_source": "https://platform.suno.com/"}


def _blocked():
    raise RuntimeError("Suno adapter is disabled until official API documentation and API commercial terms are verified")


def submit(payload, transport):
    _blocked()


def query(task_id, capability, transport):
    _blocked()


def download(task_id, capability, output_dir: Path, transport):
    _blocked()
