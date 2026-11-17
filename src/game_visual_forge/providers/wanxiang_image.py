from __future__ import annotations

import os
import re
from urllib.parse import quote

from game_visual_forge.contracts.provider import ExternalProvider
from game_visual_forge.providers.image_http import (
    ImageApiError, ImageHttpTransport, boolean_parameters, check_parameters,
    image_data_uri, integer, preflight, response_task_id, safe_error_code,
)


MODELS = ("wan2.7-image", "wan2.7-image-pro")
OFFICIAL_SOURCE = "https://help.aliyun.com/zh/model-studio/wan-image-generation-and-editing-api-reference"


class WanxiangImageAdapter:
    provider = ExternalProvider.WANXIANG
    synchronous = False

    def __init__(self, *, transport=None):
        self.transport = transport or ImageHttpTransport()

    def models(self):
        return {"schema_version": 1, "provider": self.provider.value, "verified_at": "2026-11-17", "official_source": OFFICIAL_SOURCE, "models": [{"model": model, "modes": ["text-to-image", "reference-image"], "max_references": 9, "max_outputs": 4, "max_sequential_outputs": 12, "native_alpha": None, "synchronous": False} for model in MODELS]}

    def preflight(self):
        return preflight(self.provider, ("DASHSCOPE_API_KEY",))

    def normalize(self, model, parameters, quantity):
        if model not in MODELS:
            raise ValueError("unsupported Wan image model")
        value = check_parameters(parameters, {"region", "workspace_id", "size", "seed", "watermark", "thinking_mode", "enable_sequential"}, 5000, 9)
        value.setdefault("region", "cn-beijing")
        if value["region"] not in {"cn-beijing", "ap-southeast-1"}:
            raise ValueError("Wan 2.7 region must be cn-beijing or ap-southeast-1")
        workspace = value.get("workspace_id")
        if workspace is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", str(workspace)):
            raise ValueError("workspace_id must be a valid workspace domain label")
        boolean_parameters(value, ("watermark", "thinking_mode", "enable_sequential"))
        integer(quantity, 1, 12 if value.get("enable_sequential") else 4, "quantity")
        if "seed" in value:
            integer(value["seed"], 0, 2147483647, "seed")
        max_area = 4096 ** 2 if model == "wan2.7-image-pro" and not value["references"] and not value.get("enable_sequential") else 2048 ** 2
        size = value.setdefault("size", "2K")
        if size in {"1K", "2K", "4K"}:
            area = {"1K": 1024 ** 2, "2K": 2048 ** 2, "4K": 4096 ** 2}[size]
        else:
            match = re.fullmatch(r"([1-9][0-9]*)\*([1-9][0-9]*)", str(size))
            if not match:
                raise ValueError("Wan size must be 1K, 2K, 4K, or width*height")
            width, height = map(int, match.groups())
            area = width * height
            if not 1 / 8 <= width / height <= 8:
                raise ValueError("Wan aspect ratio must be within 1:8–8:1")
        if not 768 ** 2 <= area <= max_area:
            raise ValueError("Wan image size exceeds the model/mode bounds")
        return value

    @staticmethod
    def _host(parameters):
        region = parameters["region"]
        if parameters.get("workspace_id"):
            return f"https://{parameters['workspace_id']}.{region}.maas.aliyuncs.com"
        return "https://dashscope.aliyuncs.com" if region == "cn-beijing" else "https://dashscope-intl.aliyuncs.com"

    @staticmethod
    def _headers():
        key = os.environ.get("DASHSCOPE_API_KEY")
        if not key:
            raise ValueError("DASHSCOPE_API_KEY is required")
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def submit(self, model, parameters, quantity, reference_data):
        parameters = self.normalize(model, parameters, quantity)
        if len(reference_data) != len(parameters["references"]):
            raise ValueError("verified Wan reference bytes are required")
        content = [{"image": image_data_uri(data)} for data in reference_data]
        content.append({"text": parameters["prompt"]})
        options = {key: value for key, value in parameters.items() if key not in {"prompt", "references", "region", "workspace_id"}}
        options["n"] = quantity
        body = {"model": model, "input": {"messages": [{"role": "user", "content": content}]}, "parameters": options}
        response = self.transport.request("POST", self._host(parameters) + "/api/v1/services/aigc/image-generation/generation", body=body, headers={**self._headers(), "X-DashScope-Async": "enable"})
        task_id = response_task_id(response)
        if "code" in response:
            code = str(response["code"])
            rejected = code in {"InvalidApiKey", "invalid_api_key", "AccessDenied", "access_denied", "InvalidParameter", "Arrearage", "DataInspectionFailed"}
            raise ImageApiError(code, definite_rejection=rejected, external_task_id=task_id)
        if not isinstance(task_id, str) or not task_id:
            raise ImageApiError("missing_task_id")
        output = response["output"]
        status = output.get("task_status")
        if "task_status" in output and (not isinstance(status, str) or status not in {"PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED", "UNKNOWN"}):
            raise ImageApiError("invalid_task_status", external_task_id=task_id)
        return {"status": "submitted", "external_task_id": task_id}

    def query(self, task_id, model, parameters):
        response = self.transport.request("GET", self._host(parameters) + "/api/v1/tasks/" + quote(task_id, safe=""), headers=self._headers())
        if response.get("code"):
            raise ImageApiError(str(response["code"]))
        output = response.get("output", {})
        status = output.get("task_status")
        if status in {"FAILED", "CANCELED", "UNKNOWN"}:
            return {"status": "failed", "error_code": safe_error_code(output.get("code", status))}
        if status == "SUCCEEDED":
            urls = [item["image"] for choice in output.get("choices", []) for item in choice.get("message", {}).get("content", []) if item.get("type") == "image" and isinstance(item.get("image"), str)]
            if not urls:
                return {"status": "failed", "error_code": "missing_images"}
            return {"status": "completed", "result_urls": urls}
        return {"status": "running"}
