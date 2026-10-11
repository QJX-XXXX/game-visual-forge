from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import (
    ExternalProvider,
    MediaKind,
    ProviderCapabilities,
    ProviderPreflight,
)


class ProviderContractTests(unittest.TestCase):
    def test_preflight_never_contains_secret_fields(self) -> None:
        result = ProviderPreflight(
            schema_version=1,
            provider=ExternalProvider.JIMENG,
            available=True,
            authenticated=True,
            executable="dreamina",
            version="1.2.3",
            account_credit=42,
            reason=None,
        )
        serialized = result.to_dict()
        forbidden = {"token", "cookie", "api_key", "access_key", "secret"}
        self.assertTrue(forbidden.isdisjoint(serialized))

    def test_preflight_requires_schema_version_1(self) -> None:
        with self.assertRaisesRegex(ValueError, "schema_version"):
            ProviderPreflight(
                schema_version=2,
                provider=ExternalProvider.JIMENG,
                available=True,
                authenticated=False,
                executable=None,
                version=None,
                account_credit=None,
                reason=None,
            )

    def test_capabilities_are_media_specific(self) -> None:
        value = ProviderCapabilities(
            schema_version=1,
            provider=ExternalProvider.WANXIANG,
            media_kind=MediaKind.IMAGE,
            operations=("text-to-image", "image-to-image"),
            asynchronous=True,
            max_outputs=4,
        )
        self.assertEqual(value.media_kind, MediaKind.IMAGE)
        self.assertIn("text-to-image", value.operations)


if __name__ == "__main__":
    unittest.main()
