from __future__ import annotations

import json
import sys


payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
mode = payload.get("fixture_mode")
if mode == "invalid-stdout":
    sys.stdout.buffer.write(b"\x81")
elif mode == "invalid-stderr":
    sys.stderr.buffer.write(b"provider:\x81")
    sys.stdout.buffer.write(b'{"schema_version":1,"available":true}\n')
else:
    sys.stdout.buffer.write(
        (json.dumps({"schema_version": 1, "prompt": payload.get("prompt")}, ensure_ascii=False) + "\n").encode("utf-8")
    )
