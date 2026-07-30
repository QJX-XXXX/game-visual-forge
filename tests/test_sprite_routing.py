from __future__ import annotations

import os
import unittest
from dataclasses import replace
from unittest.mock import patch

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import (
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


if __name__ == "__main__":
    unittest.main()
