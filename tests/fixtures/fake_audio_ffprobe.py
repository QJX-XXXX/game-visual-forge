from __future__ import annotations

import json
import sys


payload = {
    "streams": [{
        "codec_type": "audio",
        "codec_name": "pcm_s16le",
        "sample_rate": "44100",
        "channels": 1,
        "channel_layout": "mono",
        "sample_fmt": "s16",
        "duration": "1.0",
    }],
    "format": {"duration": "1.0"},
}
sys.stdout.write(json.dumps(payload, ensure_ascii=False))
