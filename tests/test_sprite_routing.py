from __future__ import annotations

import os
import unittest
from dataclasses import replace
from unittest.mock import patch

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import (
    BackgroundRemoval,
    ExternalProvider,
    ProviderPreflight,
    SourceType,
    SpriteSourcePreference,
)
from game_visual_forge.routing import (
    AgentImageCapabilities,
    NativeAttemptOutcome,
    build_prompt_package,
    route_sprite,
)
from tests.test_sprite_contract import make_request


class SpriteRoutingTests(unittest.TestCase):
    def test_existing_file_wins_before_native_capability(self) -> None:
        request = replace(make_request(), source_preference=SpriteSourcePreference.EXISTING_FILE)
        decision = route_sprite(request, AgentImageCapabilities(True, ("text-to-image",)))
        self.assertEqual(decision.source_type, SourceType.EXISTING_FILE)
        self.assertFalse(decision.requires_user_selection)

    def test_auto_uses_native_when_supported(self) -> None:
        decision = route_sprite(make_request(), AgentImageCapabilities(True, ("text-to-image",)))
        self.assertEqual(decision.source_type, SourceType.AGENT_NATIVE)

    def test_supported_native_precedes_provider_fallback(self) -> None:
        decision = route_sprite(
            make_request(),
            AgentImageCapabilities(True, ("text-to-image",)),
            selected_source=SourceType.DREAMINA,
        )
        self.assertEqual(decision.source_type, SourceType.AGENT_NATIVE)

    def test_unsupported_native_requires_user_selection(self) -> None:
        decision = route_sprite(make_request(), AgentImageCapabilities(False, ()))
        self.assertIsNone(decision.source_type)
        self.assertTrue(decision.requires_user_selection)
        self.assertEqual(decision.reason, "native-unsupported-user-selection-required")

    def test_preference_does_not_count_as_current_provider_selection(self) -> None:
        request = replace(make_request(), source_preference=SpriteSourcePreference.DREAMINA)
        decision = route_sprite(request, AgentImageCapabilities(False, ()))
        self.assertTrue(decision.requires_user_selection)

    def test_explicit_provider_selection_requires_paid_confirmation(self) -> None:
        preflight = ProviderPreflight(1, ExternalProvider.DREAMINA, True, True, "fake-provider", "1.0", None, None)
        decision = route_sprite(
            make_request(),
            AgentImageCapabilities(False, ()),
            selected_source=SourceType.DREAMINA,
            provider_preflight=preflight,
        )
        self.assertEqual(decision.selected_provider, ExternalProvider.DREAMINA)
        self.assertTrue(decision.requires_paid_confirmation)

    def test_native_quality_rejection_allows_provider_fallback(self) -> None:
        preflight = ProviderPreflight(1, ExternalProvider.DREAMINA, True, True, "fake-provider", "1.0", None, None)
        decision = route_sprite(
            make_request(),
            AgentImageCapabilities(True, ("text-to-image",)),
            native_outcome=NativeAttemptOutcome.QUALITY_REJECTED,
            selected_source=SourceType.DREAMINA,
            provider_preflight=preflight,
        )
        self.assertEqual(decision.source_type, SourceType.DREAMINA)

    def test_unavailable_provider_does_not_silently_fall_through(self) -> None:
        preflight = ProviderPreflight(1, ExternalProvider.WANXIANG, False, False, None, None, None, "not configured")
        decision = route_sprite(
            make_request(),
            AgentImageCapabilities(False, ()),
            selected_source=SourceType.WANXIANG,
            provider_preflight=preflight,
        )
        self.assertEqual(decision.reason, "selected-provider-unavailable")
        self.assertTrue(decision.requires_user_selection)

    def test_mismatched_preflight_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "matching preflight"):
            route_sprite(
                make_request(),
                AgentImageCapabilities(False, ()),
                selected_source=SourceType.DREAMINA,
                provider_preflight=ProviderPreflight(1, ExternalProvider.WANXIANG, True, True, "x", "1", None, None),
            )

    def test_environment_credentials_do_not_change_route(self) -> None:
        with patch.dict(os.environ, {"DREAMINA_API_KEY": "secret"}):
            decision = route_sprite(make_request(), AgentImageCapabilities(False, ()))
        self.assertTrue(decision.requires_user_selection)

    def test_prompt_package_contains_layout_and_order(self) -> None:
        package = build_prompt_package(make_request())
        self.assertEqual(package.expected_output_path, "outputs/hero-run/raw/source.png")
        self.assertEqual(package.frame_order[0], "right:00")
        self.assertEqual(package.frame_order[-1], "right:07")
        self.assertEqual(package.solid_background, "#ff00ff")

    def test_rembg_prompt_package_keeps_chroma_fallback_background(self) -> None:
        request = replace(make_request(), background_removal=BackgroundRemoval.REMBG)
        package = build_prompt_package(request)
        self.assertEqual(package.solid_background, "#ff00ff")

    def test_auto_prompt_package_requests_a_real_transparent_png(self) -> None:
        request = replace(
            make_request(),
            background_removal=BackgroundRemoval.AUTO,
            chroma_color=None,
        )

        package = build_prompt_package(request)

        self.assertTrue(package.transparent_background)
        self.assertIsNone(package.solid_background)
        self.assertIn("true transparent background", package.positive_prompt)
        self.assertIn("no white background", package.negative_constraints)
        self.assertIn("no checkerboard background", package.negative_constraints)

    def test_auto_prompt_package_owns_the_verbatim_background_removal_instruction(self) -> None:
        instruction = "移除此图像的背景。保持所有前景主体不变且完整，边缘干净平滑。将背景设为透明。"
        request = replace(
            make_request(),
            background_removal=BackgroundRemoval.AUTO,
            chroma_color=None,
        )

        package = build_prompt_package(request)

        self.assertEqual(package.transparent_background_prompt, instruction)
        self.assertIn(instruction, package.positive_prompt)
        self.assertEqual(
            package.to_dict()["transparent_background_prompt"],
            instruction,
        )

    def test_non_auto_prompt_package_does_not_add_background_removal_instruction(self) -> None:
        package = build_prompt_package(make_request())

        self.assertIsNone(package.transparent_background_prompt)


if __name__ == "__main__":
    unittest.main()
