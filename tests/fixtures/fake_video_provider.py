from __future__ import annotations

import json
import os
import sys
from pathlib import Path


payload = json.load(sys.stdin)
log = os.environ.get("GAME_VISUAL_FORGE_FAKE_PROVIDER_LOG")
if log:
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(sys.argv[1] + "\n")
command = sys.argv[1]
if command == "submit":
    print(json.dumps({"schema_version": 1, "external_task_id": "task-1", "status": "submitted"}))
elif command == "query":
    print(json.dumps({"schema_version": 1, "external_task_id": payload["external_task_id"], "status": "completed"}))
elif command == "download":
    target = Path(payload["output_path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"video-bytes")
    print(json.dumps({"schema_version": 1, "path": str(target)}))
else:
    print(json.dumps({"schema_version": 1, "status": "ok"}))
