from __future__ import annotations

import sys
from pathlib import Path


output = Path(sys.argv[-1])
timestamp = "unknown"
if "-ss" in sys.argv:
    timestamp = sys.argv[sys.argv.index("-ss") + 1]
output.parent.mkdir(parents=True, exist_ok=True)
output.write_bytes(f"frame:{timestamp}".encode("ascii"))
