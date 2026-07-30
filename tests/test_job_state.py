from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import JobState, JobStatus
from game_visual_forge.jobs import (
    fingerprint_request,
    load_job,
    save_job,
    transition_job,
)


class JobStateTests(unittest.TestCase):
    def make_state(self) -> JobState:
        return JobState(
            schema_version=1,
            job_id="job-hero-run",
            asset_id="hero-run",
            status=JobStatus.PLANNED,
            created_at="2026-07-30T00:00:00Z",
            updated_at="2026-07-30T00:00:00Z",
            request_fingerprint="a" * 64,
        )

    def test_fractional_second_utc_timestamps_are_accepted(self) -> None:
        state = JobState(
            schema_version=1,
            job_id="job-hero-run",
            asset_id="hero-run",
            status=JobStatus.PLANNED,
            created_at="2026-07-30T00:00:00.123Z",
            updated_at="2026-07-30T00:00:00.123456Z",
            request_fingerprint="a" * 64,
        )
        self.assertEqual(state.created_at, "2026-07-30T00:00:00.123Z")
        self.assertEqual(state.updated_at, "2026-07-30T00:00:00.123456Z")

    def test_non_utc_or_malformed_timestamps_are_rejected(self) -> None:
        invalid_values = (
            "2026-07-30T00:00:00",
            "2026-07-30T00:00:00+00:00",
            "2026-07-30T00:00:00.123+00:00",
            "2026-07-30 00:00:00Z",
            "2026-07-30T00:00Z",
            "2026-07-30T00:00:00.z",
        )

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "timestamp|timestamps"):
                    JobState(
                        schema_version=1,
                        job_id="job-hero-run",
                        asset_id="hero-run",
                        status=JobStatus.PLANNED,
                        created_at=value,
                        updated_at="2026-07-30T00:00:00Z",
                        request_fingerprint="a" * 64,
                    )

    def test_artifact_paths_are_normalized_to_posix(self) -> None:
        state = JobState(
            schema_version=1,
            job_id="job-hero-run",
            asset_id="hero-run",
            status=JobStatus.PLANNED,
            created_at="2026-07-30T00:00:00Z",
            updated_at="2026-07-30T00:00:00Z",
            request_fingerprint="a" * 64,
            artifact_paths=(r"outputs\hero-run\sheet.png",),
        )
        self.assertEqual(state.artifact_paths, ("outputs/hero-run/sheet.png",))

    def test_artifact_paths_reject_escapes_and_absolute_paths(self) -> None:
        invalid_paths = (
            "../escape.png",
            "outputs/hero-run/../escape.png",
            "/abs/path.png",
            "C:/abs/path.png",
        )

        for path in invalid_paths:
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "artifact_paths"):
                    JobState(
                        schema_version=1,
                        job_id="job-hero-run",
                        asset_id="hero-run",
                        status=JobStatus.PLANNED,
                        created_at="2026-07-30T00:00:00Z",
                        updated_at="2026-07-30T00:00:00Z",
                        request_fingerprint="a" * 64,
                        artifact_paths=(path,),
                    )

    def test_happy_path_transition_is_immutable(self) -> None:
        original = self.make_state()
        updated = transition_job(
            original,
            JobStatus.AWAITING_CONFIRMATION,
            now="2026-07-30T00:01:00Z",
        )
        self.assertEqual(original.status, JobStatus.PLANNED)
        self.assertEqual(updated.status, JobStatus.AWAITING_CONFIRMATION)

    def test_paid_provider_job_requires_confirmation_marker_before_ready_or_submitting(
        self,
    ) -> None:
        provider_state = replace(self.make_state(), provider="jimeng")
        with self.assertRaisesRegex(ValueError, "confirmation"):
            transition_job(
                provider_state,
                JobStatus.READY,
                now="2026-07-30T00:01:00Z",
            )

        bypass_ready = replace(
            provider_state,
            status=JobStatus.READY,
            updated_at="2026-07-30T00:01:00Z",
        )
        with self.assertRaisesRegex(ValueError, "confirmation"):
            transition_job(
                bypass_ready,
                JobStatus.SUBMITTING,
                now="2026-07-30T00:02:00Z",
            )

        awaiting = transition_job(
            provider_state,
            JobStatus.AWAITING_CONFIRMATION,
            now="2026-07-30T00:03:00Z",
        )
        confirmed_ready = transition_job(
            awaiting,
            JobStatus.READY,
            now="2026-07-30T00:04:00Z",
        )
        self.assertEqual(
            confirmed_ready.ready_provenance,
            JobStatus.AWAITING_CONFIRMATION.value,
        )

        submitting = transition_job(
            confirmed_ready,
            JobStatus.SUBMITTING,
            now="2026-07-30T00:05:00Z",
        )
        self.assertEqual(submitting.status, JobStatus.SUBMITTING)

    def test_submission_unknown_cannot_reenter_submitting_via_needs_attention_ready(
        self,
    ) -> None:
        provider_state = replace(self.make_state(), provider="jimeng")
        awaiting = transition_job(
            provider_state,
            JobStatus.AWAITING_CONFIRMATION,
            now="2026-07-30T00:01:00Z",
        )
        ready = transition_job(
            awaiting,
            JobStatus.READY,
            now="2026-07-30T00:02:00Z",
        )
        submitting = transition_job(
            ready,
            JobStatus.SUBMITTING,
            now="2026-07-30T00:03:00Z",
        )
        state = transition_job(
            submitting,
            JobStatus.SUBMISSION_UNKNOWN,
            now="2026-07-30T00:04:00Z",
        )
        needs_attention = transition_job(
            state,
            JobStatus.NEEDS_ATTENTION,
            now="2026-07-30T00:05:00Z",
        )
        ready_again = transition_job(
            needs_attention,
            JobStatus.READY,
            now="2026-07-30T00:06:00Z",
        )
        self.assertEqual(
            ready_again.ready_provenance,
            JobStatus.NEEDS_ATTENTION.value,
        )

        with self.assertRaisesRegex(ValueError, "confirmation"):
            transition_job(
                ready_again,
                JobStatus.SUBMITTING,
                now="2026-07-30T00:07:00Z",
            )

    def test_job_round_trip_preserves_schema(self) -> None:
        state = transition_job(
            transition_job(
                replace(self.make_state(), provider="jimeng"),
                JobStatus.AWAITING_CONFIRMATION,
                now="2026-07-30T00:01:00Z",
            ),
            JobStatus.READY,
            now="2026-07-30T00:02:00Z",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "job.json"
            save_job(path, state)
            restored = load_job(path)
        self.assertEqual(restored, state)

    def test_fingerprint_is_key_order_independent(self) -> None:
        left = fingerprint_request({"model": "x", "count": 1})
        right = fingerprint_request({"count": 1, "model": "x"})
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
