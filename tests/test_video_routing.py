from __future__ import annotations

import unittest

from tests._bootstrap import ROOT

from game_visual_forge.contracts.video import VideoSourcePreference
from game_visual_forge.contracts.video_provider import VideoProviderBackend
from game_visual_forge.routing.video import route_video
from tests.test_video_contract import valid_request
from game_visual_forge.contracts.video import VideoSpriteRequest


class VideoRoutingTests(unittest.TestCase):
    def test_existing_file_skips_paid_confirmation(self) -> None:
        request = VideoSpriteRequest.from_dict(valid_request())
        decision = route_video(request)
        self.assertFalse(decision.requires_user_selection)
        self.assertFalse(decision.requires_paid_confirmation)
        self.assertEqual(decision.source_preference, VideoSourcePreference.EXISTING_FILE)

    def test_generated_route_requires_explicit_provider_and_backend(self) -> None:
        request = VideoSpriteRequest.from_dict(valid_request(source_preference="minimax", existing_video_path=None))
        decision = route_video(request)
        self.assertTrue(decision.requires_user_selection)
        self.assertIsNone(decision.backend)

    def test_preflight_does_not_choose_backend(self) -> None:
        request = VideoSpriteRequest.from_dict(valid_request(source_preference="minimax", existing_video_path=None))
        decision = route_video(request, available_backends={"minimax": ("api", "cli")})
        self.assertTrue(decision.requires_user_selection)
        self.assertIsNone(decision.backend)

    def test_explicit_api_route_requires_paid_confirmation(self) -> None:
        request = VideoSpriteRequest.from_dict(valid_request(source_preference="minimax", existing_video_path=None, backend="api"))
        decision = route_video(request, available_backends={"minimax": ("api",)})
        self.assertFalse(decision.requires_user_selection)
        self.assertTrue(decision.requires_paid_confirmation)
        self.assertEqual(decision.backend, VideoProviderBackend.API)

    def test_explicit_local_comfyui_h3_route_is_ready_without_paid_confirmation(self) -> None:
        request = VideoSpriteRequest.from_dict(
            valid_request(
                source_preference="comfyui-h3",
                existing_video_path=None,
                backend="comfy-mcp",
            )
        )
        try:
            decision = route_video(
                request,
                available_backends={"comfyui-h3": ("comfy-mcp",)},
            )
        except ValueError as error:
            self.fail(f"the local Comfy MCP route should be supported: {error}")
        self.assertFalse(decision.requires_user_selection)
        self.assertFalse(decision.requires_paid_confirmation)
        self.assertIsNone(decision.provider)
        self.assertEqual(decision.backend, "comfy-mcp")
        self.assertEqual(decision.reason, "explicit-local-comfyui-h3-route")


if __name__ == "__main__":
    unittest.main()
