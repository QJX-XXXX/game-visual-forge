from __future__ import annotations

import json
import sys


command = sys.argv[1]
payload = json.loads(sys.stdin.read())
if payload.get("mode") == "stderr-secret":
    print("token=should-not-be-exposed", file=sys.stderr)
    raise SystemExit(1)
if payload.get("mode") == "invalid-json":
    print("not json")
    raise SystemExit(0)
if payload.get("mode") == "stdout-secret":
    print(json.dumps({"schema_version": 1, "token": "secret"}))
    raise SystemExit(0)

responses = {
    "capabilities": {"schema_version": 1, "provider": "dreamina", "media_kind": "image", "operations": ["text-to-image"], "asynchronous": True, "max_outputs": 1},
    "preflight": {"schema_version": 1, "provider": "dreamina", "available": True, "authenticated": True, "executable": "fake-provider", "version": "1.0", "account_credit": None, "reason": None},
    "estimate": {"schema_version": 1, "provider": "dreamina", "currency": "CNY", "amount": "0.50", "verified": True, "notice": "estimated"},
    "prepare": {"schema_version": 1, "status": "prepared"},
    "submit": {"schema_version": 1, "status": "submitted", "external_task_id": "task-001"},
    "query": {"schema_version": 1, "status": "completed", "external_task_id": "task-001"},
    "download": {"schema_version": 1, "status": "downloaded", "paths": ["raw/source.png"]},
}
print(json.dumps(responses[command]))
