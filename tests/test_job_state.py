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
