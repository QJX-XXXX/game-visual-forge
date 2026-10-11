from __future__ import annotations

import json
import os
import sys


payload_path = os.environ.get("GAME_VISUAL_FORGE_FAKE_FFPROBE_JSON")
if payload_path is None:
    raise SystemExit("GAME_VISUAL_FORGE_FAKE_FFPROBE_JSON is required")
sys.stdout.write(open(payload_path, encoding="utf-8").read())
