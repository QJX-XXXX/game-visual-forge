from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from game_visual_forge.providers.jimeng_video import run_command


if __name__ == "__main__":
    payload = json.load(sys.stdin)
    print(json.dumps(run_command(sys.argv[1], payload), ensure_ascii=False, sort_keys=True))
