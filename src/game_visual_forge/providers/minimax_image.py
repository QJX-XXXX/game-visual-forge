from __future__ import annotations

import base64
import os
import re

from game_visual_forge.contracts.provider import ExternalProvider
from game_visual_forge.providers.image_http import (
    ImageApiError, ImageHttpTransport, boolean_parameters, check_parameters,
    image_data_uri, integer, json_bytes, preflight, safe_error_code,
)


MODELS = ("MiniMax-H3-Image", "MiniMax-H3-Image-Highspeed")
OFFICIAL_SOURCE = "https://platform.minimax.cn/docs/api-reference/image-generation-h3-generations"
MAX_REQUEST_BYTES = 64 * 1024 * 1024


class MiniMaxImageAdapter:
    provider = ExternalProvider.MINIMAX
    synchronous = True

    def __init__(self, *, transport=None):
        self.transport = transport or ImageHttpTransport()

    def models(self):
        return {"schema_version": 1, "provider": self.provider.value, "verified_at": "2026-11-17", "official_source": OFFICIAL_SOURCE, "models": [{"model": model, "modes": ["text-to-image", "reference-image"], "max_references": 16, "max_outputs": 10, "native_alpha": False, "synchronous": True} for model in MODELS]}

    def preflight(self):
        return preflight(self.provider, ("MINIMAX_API_KEY",))

    def normalize(self, model, parameters, quantity):
        if model not in MODELS:
            raise ValueError("unsupported MiniMax image model")
        integer(quantity, 1, 10, "quantity")
        value = check_parameters(parameters, {"region", "size", "aspect_ratio", "area", "disable_prompt_enhanced", "aigc_watermark"}, 32000, 16)
        value.setdefault("region", "cn")
        if value["region"] not in {"cn", "global"}:
            raise ValueError("MiniMax region must be cn or global")
        size = value.setdefault("size", "auto")
        if size == "auto":
            area = value.setdefault("area", "1K")
            if area not in {"1K", "2K", "4K"}:
                raise ValueError("MiniMax area must be 1K, 2K, or 4K")
            pixels = {"1K": 1024 ** 2, "2K": 2048 ** 2, "4K": 4096 ** 2}[area]
            ratio = value.setdefault("aspect_ratio", "auto")
            if ratio != "auto":
                match = re.fullmatch(r"([1-9][0-9]{0,2}):([1-9][0-9]{0,2})", str(ratio))
                if not match:
                    raise ValueError("MiniMax aspect_ratio must use X:Y")
                x, y = map(int, match.groups())
                if max(x, y) > 300 or not 1 / 3 <= x / y <= 3:
                    raise ValueError("MiniMax aspect_ratio is outside 1:3–3:1")
            if value.get("disable_prompt_enhanced") and ratio == "auto":
                raise ValueError("disabling prompt enhancement requires an explicit size or ratio")
        else:
            match = re.fullmatch(r"([1-9][0-9]*)x([1-9][0-9]*)", str(size))
            if not match or "aspect_ratio" in value or "area" in value:
                raise ValueError("MiniMax size must use widthxheight exclusively")
            width, height = map(int, match.groups())
            pixels = width * height
            if not 655360 <= pixels <= 20000000 or not 1 / 3 <= width / height <= 3:
                raise ValueError("MiniMax size exceeds the documented area or ratio bounds")
        if pixels * quantity > 20000000:
            raise ValueError("MiniMax PNG response total area exceeds 20,000,000 pixels")
        boolean_parameters(value, ("disable_prompt_enhanced", "aigc_watermark"))
        if value["references"] and "disable_prompt_enhanced" in value:
            raise ValueError("MiniMax image editing always enables prompt enhancement")
        return value

    def build_body(self, model, parameters, quantity, reference_data):
        parameters = self.normalize(model, parameters, quantity)
        body = {name: value for name, value in parameters.items() if name not in {"region", "references"}}
        body.update(model=model, n=quantity, output_format="png", response_format="b64_json", stream=False)
        if parameters["references"]:
            if len(reference_data) != len(parameters["references"]):
                raise ValueError("verified MiniMax reference bytes are required")
            body["images"] = [{"image_url": image_data_uri(data)} for data in reference_data]
        if len(json_bytes(body)) > MAX_REQUEST_BYTES:
            raise ValueError("MiniMax request exceeds 64 MiB")
        return body

    def submit(self, model, parameters, quantity, reference_data):
        body = self.build_body(model, parameters, quantity, reference_data)
        key = os.environ.get("MINIMAX_API_KEY")
        if not key:
            raise ValueError("MINIMAX_API_KEY is required")
        endpoint = "/v1/images/edits" if body.get("images") else "/v1/images/generations"
        host = "https://api.minimax.cn" if parameters["region"] == "cn" else "https://api.minimax.io"
        response = self.transport.request("POST", host + endpoint, body=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, timeout=600)
        items = response.get("data")
        if not isinstance(items, list):
            raise ImageApiError("invalid_image_response")
        uncertain = len(items) != quantity
        images, errors = [], []
        for index in range(quantity):
            item = items[index] if index < len(items) else None
            if not isinstance(item, dict):
                errors.append({"index": index + 1, "code": "invalid_image_result"})
                images.append(None)
                uncertain = True
                continue
            if isinstance(item.get("error"), dict):
                errors.append({"index": index + 1, "code": safe_error_code(item["error"].get("code", "image_failed"))})
                images.append(None)
                continue
            try:
                images.append(base64.b64decode(item["b64_json"], validate=True))
            except (KeyError, ValueError, TypeError):
                errors.append({"index": index + 1, "code": "invalid_image_data"})
                images.append(None)
                uncertain = True
        return {"status": "completed", "images": images, "errors": errors, "uncertain": uncertain}

    def query(self, task_id, model, parameters):
        raise ValueError("MiniMax image generation is synchronous; recover saved local results or resolve an unknown submit in the provider account")
