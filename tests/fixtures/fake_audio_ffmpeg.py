from __future__ import annotations

import shutil
import sys
from pathlib import Path


args = sys.argv[1:]
output = Path(args[-1])
output.parent.mkdir(parents=True, exist_ok=True)
if output.suffix.lower() == ".png":
    output.write_bytes(bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000000020001e221bc330000000049454e44ae426082"))
else:
    source = Path(args[args.index("-i") + 1])
    shutil.copyfile(source, output)
