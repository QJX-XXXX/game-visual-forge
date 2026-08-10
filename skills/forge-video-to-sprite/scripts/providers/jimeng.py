from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from game_visual_forge.providers.jimeng_video import main


if __name__ == "__main__":
    raise SystemExit(main())
