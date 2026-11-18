from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path

SRC = Path(__file__).resolve().parents[4] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from game_visual_forge.contracts.music_provider import MusicHttpResponse
from game_visual_forge.providers.stable_audio_music import (
    download,
    preflight,
    query,
    submit,
)


class UrllibTransport:
    def __call__(self, method: str, url: str, headers: dict[str, str], body: bytes | None) -> MusicHttpResponse:
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return MusicHttpResponse(response.status, {str(k).lower(): str(v) for k, v in response.headers.items()}, response.read())
        except urllib.error.HTTPError as error:
            return MusicHttpResponse(error.code, {str(k).lower(): str(v) for k, v in error.headers.items()}, error.read())


def run(payload: dict) -> dict:
    operation = str(payload.get("operation", "preflight"))
    if operation == "preflight":
        return preflight(dict(payload))
    transport = UrllibTransport()
    if operation == "submit":
        parameters = dict(payload.get("parameters", payload))
        return submit(parameters, transport).to_dict()
    task_id = str(payload.get("external_task_id", ""))
    credential = os.environ.get("STABILITY_API_KEY")
    if operation == "query":
        return query(task_id, None, transport, credential=credential).to_dict()
    if operation == "download":
        files = download(task_id, None, Path(str(payload["output_dir"])), transport, credential=credential)
        return {
            "status": "completed",
            "external_task_id": task_id,
            "candidate_ids": [item.provider_candidate_id for item in files],
            "returned_candidate_count": len(files),
            "downloaded_files": [asdict(item) for item in files],
        }
    raise ValueError(f"unsupported Stable Audio operation: {operation}")


if __name__ == "__main__":
    try:
        value = run(json.load(sys.stdin))
    except Exception as error:
        print(json.dumps({"error_code": type(error).__name__}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from error
    else:
        print(json.dumps(value, ensure_ascii=False))
