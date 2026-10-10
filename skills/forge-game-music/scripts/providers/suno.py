from __future__ import annotations

import json
import sys

from game_visual_forge.providers.suno_music import preflight


if __name__ == "__main__":
    payload = json.load(sys.stdin)
    print(json.dumps(preflight(payload), ensure_ascii=False))
