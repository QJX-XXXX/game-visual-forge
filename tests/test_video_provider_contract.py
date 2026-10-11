from __future__ import annotations

import unittest

from tests._bootstrap import ROOT

from game_visual_forge.contracts.provider import CostEstimate, ExternalProvider, ProviderCommand
from game_visual_forge.contracts.video import VideoGenerationMode
from game_visual_forge.contracts.video_provider import (
    VideoGenerationAttempt,
    VideoAttemptStatus,
    VideoModelCatalogSnapshot,
    VideoModelProfile,
    VideoModelSupport,
    VideoPaidConfirmation,
    VideoProviderBackend,
)


NOW = "2026-08-09T00:00:00Z"


def estimate(*, verified: bool = True) -> CostEstimate:
    return CostEstimate(1, ExternalProvider.MINIMAX, "USD", "0.10", verified, "test estimate")


def profile(model: str = "MiniMax-H3") -> VideoModelProfile:
    return VideoModelProfile(
        schema_version=1,
        provider=ExternalProvider.MINIMAX,
        model=model,
        endpoint_generation="v2",
        endpoint="/v2/video_generation",
        supported_modes=(VideoGenerationMode.T2V, VideoGenerationMode.I2V_FIRST),
        reference_roles=("first_frame",),
        durations=(6,),
        resolutions=("768P",),
        aspect_ratios=("16:9",),
        audio_supported=False,
        supported_backends=(VideoProviderBackend.API, VideoProviderBackend.CLI),
        profile_revision="2026-08-09",
    )


class VideoProviderContractTests(unittest.TestCase):
    def test_minimax_and_models_command_are_public(self) -> None:
        self.assertEqual(ExternalProvider.MINIMAX.value, "minimax")
        self.assertEqual(ProviderCommand.MODELS.value, "models")

    def test_snapshot_hash_is_canonical_and_unknown_model_is_visible(self) -> None:
        snapshot = VideoModelCatalogSnapshot.create(
            provider=ExternalProvider.MINIMAX,
            backend=VideoProviderBackend.API,
            region="global",
            refreshed_at=NOW,
            adapter_version="1.0",
            models=(profile(), {"model": "MiniMax-Future"}),
            source="fake-http",
        )
        self.assertEqual(snapshot.model("MiniMax-H3").support, VideoModelSupport.PROFILED)
        self.assertEqual(snapshot.model("MiniMax-Future").support, VideoModelSupport.DISCOVERED_UNPROFILED)
        self.assertEqual(len(snapshot.snapshot_sha256), 64)
        self.assertEqual(VideoModelCatalogSnapshot.from_dict(snapshot.to_dict()), snapshot)

    def test_unverified_estimate_requires_explicit_acknowledgement(self) -> None:
        values = dict(
            attempt_id="attempt-1", provider=ExternalProvider.MINIMAX,
            backend=VideoProviderBackend.API, region="global", model="MiniMax-H3",
            model_snapshot_sha256="a" * 64, mode=VideoGenerationMode.T2V,
            parameters={"duration": 6}, reference_sha256=(), quantity=1,
            estimate=estimate(verified=False), request_fingerprint="b" * 64,
            confirmed_at=NOW,
        )
        with self.assertRaisesRegex(ValueError, "acknowledgement"):
            VideoPaidConfirmation.create(**values)
        confirmation = VideoPaidConfirmation.create(**values, estimate_acknowledged=True)
        consumed = confirmation.authorize_attempt(now=NOW, **{key: values[key] for key in (
            "attempt_id", "provider", "backend", "region", "model", "model_snapshot_sha256",
            "mode", "parameters", "reference_sha256", "quantity", "estimate", "request_fingerprint")})
        self.assertEqual(consumed.consumed_at, NOW)
        with self.assertRaisesRegex(ValueError, "consumed"):
            consumed.authorize_attempt(now=NOW, **{key: values[key] for key in (
                "attempt_id", "provider", "backend", "region", "model", "model_snapshot_sha256",
                "mode", "parameters", "reference_sha256", "quantity", "estimate", "request_fingerprint")})

    def test_snapshot_change_breaks_confirmation_binding(self) -> None:
        confirmation = VideoPaidConfirmation.create(
            attempt_id="attempt-1", provider=ExternalProvider.MINIMAX,
            backend=VideoProviderBackend.API, region="global", model="MiniMax-H3",
            model_snapshot_sha256="a" * 64, mode=VideoGenerationMode.T2V,
            parameters={"duration": 6}, reference_sha256=(), quantity=1,
            estimate=estimate(), request_fingerprint="b" * 64, confirmed_at=NOW,
        )
        with self.assertRaisesRegex(ValueError, "binding"):
            confirmation.assert_binding_matches(
                attempt_id="attempt-1", provider=ExternalProvider.MINIMAX,
                backend=VideoProviderBackend.API, region="global", model="MiniMax-H3",
                model_snapshot_sha256="c" * 64, mode=VideoGenerationMode.T2V,
                parameters={"duration": 6}, reference_sha256=(), quantity=1,
                estimate=estimate(), request_fingerprint="b" * 64,
            )

    def test_attempt_cannot_change_backend_after_preparation(self) -> None:
        attempt = VideoGenerationAttempt(
            schema_version=1, attempt_id="attempt-1", request_fingerprint="b" * 64,
            provider=ExternalProvider.MINIMAX, backend=VideoProviderBackend.API,
            region="global", model="MiniMax-H3", model_snapshot_sha256="a" * 64,
            parameters={"duration": 6}, status=VideoAttemptStatus.PREPARED,
            created_at=NOW, updated_at=NOW,
        )
        with self.assertRaisesRegex(ValueError, "backend"):
            attempt.replace(backend=VideoProviderBackend.CLI)


if __name__ == "__main__":
    unittest.main()
