from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if sys.version_info < (3, 11):
    import json
    import runpy
    checker = runpy.run_path(str(ROOT / "install/check_environment.py"))
    print(json.dumps(checker["inspect_environment"](ROOT, "core"), ensure_ascii=False), file=sys.stderr)
    raise SystemExit(1)

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from game_visual_forge.cli.main import main


if __name__ == "__main__":
    raise SystemExit(main())
