from __future__ import annotations

import base64
import io
import os
import unittest
from unittest.mock import patch

from tests._bootstrap import ROOT  # noqa: F401
from PIL import Image

from game_visual_forge.providers.image_http import ImageApiError, json_bytes
from game_visual_forge.providers.minimax_image import MiniMaxImageAdapter
from game_visual_forge.providers.jimeng_image import JimengImageAdapter
from game_visual_forge.providers.wanxiang_image import WanxiangImageAdapter


def png_bytes(size=(256, 256), color="red"):
    target = io.BytesIO()
    Image.new("RGB", size, color).save(target, format="PNG")
    return target.getvalue()


class FakeImageTransport:
    def __init__(self, responses=(), images=None):
        self.responses = list(responses)
        self.images = images or {}
        self.calls = []

    def request(self, method, url, *, body=None, headers=None, timeout=120):
        self.calls.append((method, url, body, headers, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def read_image(self, url):
        value = self.images[url]
        if isinstance(value, Exception):
            raise value
        return value

    def download(self, url, path):
        path.write_bytes(self.read_image(url))
        return path


class ImageApiProviderTests(unittest.TestCase):
    def test_preflight_requires_pillow_before_paid_generation(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "secret"}), patch.dict("sys.modules", {"PIL": None}):
            result = MiniMaxImageAdapter().preflight()
        self.assertFalse(result["available"])
        self.assertFalse(result["authentication_verified"])
        self.assertNotIn("secret", str(result))

    def test_minimax_png_response_uses_current_endpoint_and_long_timeout(self):
        image = png_bytes()
        transport = FakeImageTransport([{"data": [{"b64_json": base64.b64encode(image).decode()}], "output_format": "png"}])
        adapter = MiniMaxImageAdapter(transport=transport)
        parameters = adapter.normalize("MiniMax-H3-Image", {"prompt": "a sprite", "size": "1024x1024", "region": "cn"}, 1)
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-secret"}):
            result = adapter.submit("MiniMax-H3-Image", parameters, 1, [])
        self.assertEqual(result["images"], [image])
        method, url, body, headers, timeout = transport.calls[0]
        self.assertEqual((method, url), ("POST", "https://api.minimax.cn/v1/images/generations"))
        self.assertEqual(body["response_format"], "b64_json")
        self.assertEqual(body["output_format"], "png")
        self.assertEqual(body["n"], 1)
        self.assertEqual(headers["Authorization"], "Bearer test-secret")
        self.assertGreaterEqual(timeout, 600)

    def test_minimax_local_reference_uses_edit_json_in_memory(self):
        transport = FakeImageTransport([{"data": [{"b64_json": base64.b64encode(png_bytes()).decode()}]}])
        adapter = MiniMaxImageAdapter(transport=transport)
        parameters = adapter.normalize("MiniMax-H3-Image-Highspeed", {"prompt": "walk", "size": "1024x1024", "references": [{"path": "inputs/hero.png", "sha256": "a" * 64}]}, 1)
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "secret"}):
            adapter.submit("MiniMax-H3-Image-Highspeed", parameters, 1, [png_bytes()])
        self.assertTrue(transport.calls[0][1].endswith("/v1/images/edits"))
        self.assertTrue(transport.calls[0][2]["images"][0]["image_url"].startswith("data:image/png;base64,"))
        self.assertNotIn("base64", str(parameters))

    def test_minimax_enforces_png_total_area_and_option_limits(self):
        adapter = MiniMaxImageAdapter(transport=FakeImageTransport())
        for parameters, quantity in [({"prompt": "sprite", "size": "4096x4096"}, 2), ({"prompt": "sprite", "seed": 1}, 1), ({"prompt": "sprite", "size": "1024x1024", "area": "1K"}, 1)]:
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                adapter.normalize("MiniMax-H3-Image", parameters, quantity)

    def test_jimeng_submit_uses_force_single_and_v4(self):
        transport = FakeImageTransport([{"code": 10000, "data": {"task_id": "jimeng-task"}}])
        adapter = JimengImageAdapter(transport=transport)
        parameters = adapter.normalize("jimeng_t2i_v40", {"prompt": "角色精灵图", "width": 1024, "height": 1024}, 1)
        with patch.dict(os.environ, {"JIMENG_ACCESS_KEY": "test-ak", "JIMENG_SECRET_KEY": "test-sk"}):
            receipt = adapter.submit("jimeng_t2i_v40", parameters, 1, [])
        self.assertEqual(receipt["external_task_id"], "jimeng-task")
        method, url, body, headers, _ = transport.calls[0]
        self.assertIn("Action=CVSync2AsyncSubmitTask&Version=2022-08-31", url)
        self.assertTrue(body["force_single"])
        self.assertEqual(body["req_key"], "jimeng_t2i_v40")
        self.assertEqual(headers["X-Content-Sha256"], __import__("hashlib").sha256(json_bytes(body)).hexdigest())
        self.assertIn("Credential=test-ak/", headers["Authorization"])

    def test_jimeng_query_requests_urls_and_handles_expired(self):
        transport = FakeImageTransport([{"code": 10000, "data": {"status": "expired"}}])
        adapter = JimengImageAdapter(transport=transport)
        with patch.dict(os.environ, {"JIMENG_ACCESS_KEY": "ak", "JIMENG_SECRET_KEY": "sk"}):
            receipt = adapter.query("task", "jimeng_t2i_v40", {})
        self.assertEqual(receipt["status"], "failed")
        self.assertIn('"return_url":true', transport.calls[0][2]["req_json"])

    def test_wan_async_has_workspace_and_bearer_on_recovery(self):
        transport = FakeImageTransport([
            {"output": {"task_id": "wan-task", "task_status": "PENDING"}},
            {"output": {"task_status": "SUCCEEDED", "choices": [{"message": {"content": [{"type": "image", "image": "https://cdn.invalid/image.png?Signature=secret"}]}}]}},
        ])
        adapter = WanxiangImageAdapter(transport=transport)
        parameters = adapter.normalize("wan2.7-image", {"prompt": "sprite", "size": "1K", "region": "cn-beijing", "workspace_id": "workspace-1"}, 1)
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "wan-secret"}):
            adapter.submit("wan2.7-image", parameters, 1, [])
            result = adapter.query("wan-task", "wan2.7-image", parameters)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(transport.calls[0][3]["X-DashScope-Async"], "enable")
        self.assertIn("workspace-1.cn-beijing.maas.aliyuncs.com", transport.calls[0][1])
        self.assertEqual(transport.calls[0][2]["parameters"]["n"], 1)
        self.assertEqual(transport.calls[1][3]["Authorization"], "Bearer wan-secret")

    def test_wan_pro_4k_rejected_for_reference_edit(self):
        with self.assertRaises(ValueError):
            WanxiangImageAdapter(transport=FakeImageTransport()).normalize("wan2.7-image-pro", {"prompt": "edit", "size": "4K", "references": [{"url": "https://public.invalid/ref.png"}]}, 1)

    def test_business_rejection_is_definite_and_sanitized(self):
        adapter = JimengImageAdapter(transport=FakeImageTransport([{"code": 50413, "message": "contains sensitive raw content", "data": None}]))
        with patch.dict(os.environ, {"JIMENG_ACCESS_KEY": "ak", "JIMENG_SECRET_KEY": "sk"}):
            with self.assertRaises(ImageApiError) as captured:
                adapter.submit("jimeng_t2i_v40", adapter.normalize("jimeng_t2i_v40", {"prompt": "sprite"}, 1), 1, [])
        self.assertTrue(captured.exception.definite_rejection)
        self.assertNotIn("sensitive", str(captured.exception))

    def test_malformed_error_code_does_not_leak_response_data(self):
        adapter = JimengImageAdapter(transport=FakeImageTransport([{"code": {"token": "private-secret"}, "data": {"task_id": "task-1"}}]))
        with patch.dict(os.environ, {"JIMENG_ACCESS_KEY": "ak", "JIMENG_SECRET_KEY": "sk"}):
            with self.assertRaises(ImageApiError) as captured:
                adapter.submit("jimeng_t2i_v40", adapter.normalize("jimeng_t2i_v40", {"prompt": "sprite"}, 1), 1, [])
        self.assertEqual(captured.exception.external_task_id, "task-1")
        self.assertNotIn("private-secret", captured.exception.code)


if __name__ == "__main__":
    unittest.main()
