from __future__ import annotations

import unittest

from tests.test_map_contract import make_map_request
from game_visual_forge.contracts import ExternalProvider, MapSourceType, ProviderPreflight, SourcePreference
from game_visual_forge.routing import MapSourceCapabilities, route_map


class MapRoutingTests(unittest.TestCase):
    def test_existing_file_is_selected_without_confirmation(self) -> None:
        decision = route_map(
            make_map_request(),
            MapSourceCapabilities(False, ()),
        )
        self.assertEqual(decision.source_type.value, "existing-file")
        self.assertFalse(decision.requires_paid_confirmation)
        self.assertFalse(decision.requires_user_selection)

    def test_native_is_selected_when_auto_and_capability_exists(self) -> None:
        request = make_map_request()
        request = request.__class__(**{**request.__dict__, "source_preference": SourcePreference.AUTO})
        decision = route_map(request, MapSourceCapabilities(True, ("text-to-image",)))
        self.assertEqual(decision.source_type.value, "agent-native")

    def test_paid_provider_requires_matching_preflight_and_confirmation(self) -> None:
        request = make_map_request()
        paid_request = request.__class__(**{**request.__dict__, "source_preference": SourcePreference.JIMENG})
        decision = route_map(
            request,
            MapSourceCapabilities(False, ()),
            selected_source=MapSourceType.EXISTING_FILE,
        )
        self.assertEqual(decision.source_type.value, "existing-file")
        with self.assertRaisesRegex(ValueError, "matching preflight"):
            route_map(paid_request, MapSourceCapabilities(False, ()), selected_source=MapSourceType.JIMENG)
        preflight = ProviderPreflight(1, ExternalProvider.JIMENG, True, True, "jimeng", "1.0", 100, "ready")
        paid = route_map(
            paid_request,
            MapSourceCapabilities(False, ()),
            selected_source=MapSourceType.JIMENG,
            provider_preflight=preflight,
        )
        self.assertTrue(paid.requires_paid_confirmation)


if __name__ == "__main__":
    unittest.main()
