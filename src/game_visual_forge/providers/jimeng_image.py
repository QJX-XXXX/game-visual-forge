from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from game_visual_forge.contracts.provider import ExternalProvider
from game_visual_forge.providers.image_http import ImageApiError, ImageHttpTransport, check_parameters, integer, preflight, response_task_id
from game_visual_forge.providers.jimeng_video import sign_volcengine_request


MODEL = "jimeng_t2i_v40"
BASE_URL = "https://visual.volcengineapi.com"
OFFICIAL_SOURCE = "https://docs.volcengine.com/docs/jimeng-ai/jimeng-ai-image-generation-40-interface-documentation?lang=zh"


class JimengImageAdapter:
    synchronous = False

    def __init__(self, *, transport=None, provider=ExternalProvider.JIMENG):
        self.transport = transport or ImageHttpTransport()
        self.provider = provider

    def models(self):
        return {"schema_version": 1, "provider": self.provider.value, "verified_at": "2026-11-17", "official_source": OFFICIAL_SOURCE, "models": [{"model": MODEL, "modes": ["text-to-image", "reference-image"], "max_references": 10, "max_outputs": 1, "native_alpha": None, "synchronous": False}]}

    def preflight(self):
        return preflight(self.provider, ("JIMENG_ACCESS_KEY", "JIMENG_SECRET_KEY"))

    def normalize(self, model, parameters, quantity):
        if model != MODEL:
            raise ValueError("unsupported Jimeng image model")
        integer(quantity, 1, 1, "Jimeng quantity")
        value = check_parameters(parameters, {"region", "width", "height", "size", "scale", "force_single", "min_ratio", "max_ratio"}, 800, 10)
        value.setdefault("region", "cn-north-1")
        if value["region"] != "cn-north-1":
            raise ValueError("Jimeng image API requires region cn-north-1")
        if value.get("force_single", True) is not True:
            raise ValueError("Jimeng fixed-quantity generation requires force_single=true")
        value["force_single"] = True
        if "width" in value or "height" in value:
            if "size" in value:
                raise ValueError("use width/height or size exclusively")
            width = integer(value.get("width"), 1, 16777216, "width")
            height = integer(value.get("height"), 1, 16777216, "height")
            if not 1024 ** 2 <= width * height <= 4096 ** 2:
                raise ValueError("Jimeng image area must be 1024²–4096²")
        else:
            value["size"] = integer(value.get("size", 2048 ** 2), 1024 ** 2, 4096 ** 2, "size")
        for name, default in (("scale", 0.5), ("min_ratio", 1 / 3), ("max_ratio", 3)):
            number = value.setdefault(name, default)
            if isinstance(number, bool) or not isinstance(number, (int, float)):
                raise ValueError(f"{name} must be numeric")
        if not 0 <= value["scale"] <= 1 or not 1 / 16 <= value["min_ratio"] <= value["max_ratio"] < 16:
            raise ValueError("Jimeng scale or aspect-ratio bounds are invalid")
        if "width" in value and not value["min_ratio"] <= value["width"] / value["height"] <= value["max_ratio"]:
            raise ValueError("Jimeng dimensions conflict with min_ratio/max_ratio")
        if any(not item.get("url") for item in value["references"]):
            raise ValueError("Jimeng references require public URLs")
        return value

    def _request(self, action, body):
        access_key, secret_key = os.environ.get("JIMENG_ACCESS_KEY"), os.environ.get("JIMENG_SECRET_KEY")
        if not access_key or not secret_key:
            raise ValueError("JIMENG_ACCESS_KEY and JIMENG_SECRET_KEY are required")
        url = BASE_URL + f"/?Action={action}&Version=2022-08-31"
        signed = sign_volcengine_request(method="POST", url=url, headers={"Content-Type": "application/json"}, body=body, access_key=access_key, secret_key=secret_key, now=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        response = self.transport.request("POST", url, body=body, headers={**signed.headers, "Region": "cn-north-1", "Service": "cv"})
        task_id = response_task_id(response)
        code = str(response.get("code", "invalid_response"))
        if code != "10000":
            # Documented input rejection and throttle codes are definite only
            # when no task was admitted. Unknown/server codes remain uncertain.
            rejected = code in {"50411", "50412", "50413", "50429", "50430"}
            raise ImageApiError(code, definite_rejection=rejected, external_task_id=task_id)
        data = response.get("data")
        if not isinstance(data, dict):
            raise ImageApiError("invalid_response")
        return data

    def submit(self, model, parameters, quantity, reference_data):
        parameters = self.normalize(model, parameters, quantity)
        body = {key: value for key, value in parameters.items() if key not in {"region", "references"}}
        body["req_key"] = model
        if parameters["references"]:
            body["image_urls"] = [item["url"] for item in parameters["references"]]
        data = self._request("CVSync2AsyncSubmitTask", body)
        if not isinstance(data.get("task_id"), str) or not data["task_id"]:
            raise ImageApiError("missing_task_id")
        return {"status": "submitted", "external_task_id": data["task_id"]}

    def query(self, task_id, model, parameters):
        body = {"req_key": model, "task_id": task_id, "req_json": json.dumps({"return_url": True}, separators=(",", ":"))}
        data = self._request("CVSync2AsyncGetResult", body)
        status = data.get("status")
        if status in {"expired", "not_found"}:
            return {"status": "failed", "error_code": status}
        if status == "done":
            urls = data.get("image_urls")
            if not isinstance(urls, list) or not urls:
                return {"status": "failed", "error_code": "missing_images"}
            return {"status": "completed", "result_urls": urls}
        return {"status": "running"}
