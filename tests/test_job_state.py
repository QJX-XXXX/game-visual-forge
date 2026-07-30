from __future__ import annotations

import tempfile
import unittest
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

    def test_submission_unknown_cannot_transition_to_submitting(self) -> None:
        ready = transition_job(
            self.make_state(),
            JobStatus.READY,
            now="2026-07-30T00:01:00Z",
        )
        submitting = transition_job(
            ready,
            JobStatus.SUBMITTING,
            now="2026-07-30T00:02:00Z",
        )
        state = transition_job(
            submitting,
            JobStatus.SUBMISSION_UNKNOWN,
            now="2026-07-30T00:03:00Z",
        )
        with self.assertRaisesRegex(ValueError, "illegal transition"):
            transition_job(
                state,
                JobStatus.SUBMITTING,
                now="2026-07-30T00:04:00Z",
            )

    def test_job_round_trip_preserves_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "job.json"
            save_job(path, self.make_state())
            restored = load_job(path)
        self.assertEqual(restored, self.make_state())

    def test_fingerprint_is_key_order_independent(self) -> None:
        left = fingerprint_request({"model": "x", "count": 1})
        right = fingerprint_request({"count": 1, "model": "x"})
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
