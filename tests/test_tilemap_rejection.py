from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from game_visual_forge.cli.tilemap import run_tilemap_reject
from game_visual_forge.contracts import JobRejectionRecord, JobState, JobStatus, load_json
from game_visual_forge.jobs import load_job, save_job, transition_job


class TilemapRejectionTests(unittest.TestCase):
    def test_completed_run_can_be_rejected_with_hashed_immutable_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_root = root / "run"
            final = run_root / "final" / "tilemap-preview.png"
            final.parent.mkdir(parents=True)
            final.write_bytes(b"retained evidence")
            state_path = run_root / "job-state.json"
            state = JobState(
                1,
                "job-village",
                "village",
                JobStatus.COMPLETED,
                "2026-08-07T05:00:00Z",
                "2026-08-07T05:00:00Z",
                "a" * 64,
            )
            save_job(state_path, state)
            out = run_root / "rejection.json"

            result = run_tilemap_reject(
                state_path,
                run_root,
                out,
                "unusable-visual-composition",
                "Repeated façade mosaics made the map unusable.",
                "2026-08-07T06:00:00Z",
            )

            self.assertEqual(result["status"], "rejected")
            self.assertEqual(load_job(state_path).status, JobStatus.REJECTED)
            record = JobRejectionRecord.from_dict(load_json(out))
            self.assertEqual(record.reason_code, "unusable-visual-composition")
            artifact = next(item for item in record.artifacts if item.path == "final/tilemap-preview.png")
            self.assertEqual(artifact.sha256, hashlib.sha256(final.read_bytes()).hexdigest())

    def test_rejected_state_is_terminal(self) -> None:
        state = JobState(
            1,
            "job-village",
            "village",
            JobStatus.REJECTED,
            "2026-08-07T05:00:00Z",
            "2026-08-07T05:00:00Z",
            "a" * 64,
        )
        with self.assertRaises(ValueError):
            transition_job(state, JobStatus.READY, now="2026-08-07T06:00:00Z")


if __name__ == "__main__":
    unittest.main()
