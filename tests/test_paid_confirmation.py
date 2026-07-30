from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import CostEstimate, ExternalProvider, PaidConfirmation


class PaidConfirmationTests(unittest.TestCase):
    def make_confirmation(self) -> PaidConfirmation:
        return PaidConfirmation.create(
            attempt_id="attempt-001",
            provider=ExternalProvider.DREAMINA,
            model="dreamina-image-v1",
            parameters={"width": 1024, "height": 1024},
            quantity=1,
            estimate=CostEstimate(1, ExternalProvider.DREAMINA, "CNY", "0.50", True, "estimated"),
            request_fingerprint="a" * 64,
            confirmed_at="2026-07-30T01:00:00Z",
        )

    def authorized(self, confirmation: PaidConfirmation, **changes: object) -> dict[str, object]:
        values: dict[str, object] = {
            "attempt_id": confirmation.attempt_id,
            "provider": confirmation.provider,
            "model": confirmation.model,
            "parameters": confirmation.parameters,
            "quantity": confirmation.quantity,
            "estimate": confirmation.estimate,
            "request_fingerprint": confirmation.request_fingerprint,
        }
        values.update(changes)
        return values

    def test_exact_payload_is_authorized_once_and_round_trips(self) -> None:
        confirmation = self.make_confirmation()
        confirmation.assert_authorizes(**self.authorized(confirmation))
        consumed = confirmation.authorize_attempt(**self.authorized(confirmation), now="2026-07-30T01:01:00Z")
        self.assertEqual(PaidConfirmation.from_dict(consumed.to_dict()), consumed)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            consumed.assert_authorizes(**self.authorized(consumed))

    def test_changed_binding_value_is_stale(self) -> None:
        confirmation = self.make_confirmation()
        for changes in (
            {"model": "other-model"},
            {"parameters": {"width": 512, "height": 512}},
            {"quantity": 2},
            {"request_fingerprint": "b" * 64},
        ):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, "does not match"):
                    confirmation.assert_authorizes(**self.authorized(confirmation, **changes))

    def test_secret_fields_and_unverified_estimate_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "secret field"):
            PaidConfirmation.create(
                attempt_id="attempt-001", provider=ExternalProvider.DREAMINA, model="m",
                parameters={"token": "secret"}, quantity=1,
                estimate=CostEstimate(1, ExternalProvider.DREAMINA, "CNY", "1", True, "ok"),
                request_fingerprint="a" * 64, confirmed_at="2026-07-30T01:00:00Z",
            )
        with self.assertRaisesRegex(ValueError, "verified"):
            PaidConfirmation.create(
                attempt_id="attempt-001", provider=ExternalProvider.DREAMINA, model="m",
                parameters={}, quantity=1,
                estimate=CostEstimate(1, ExternalProvider.DREAMINA, "CNY", "1", False, "unknown"),
                request_fingerprint="a" * 64, confirmed_at="2026-07-30T01:00:00Z",
            )


if __name__ == "__main__":
    unittest.main()
