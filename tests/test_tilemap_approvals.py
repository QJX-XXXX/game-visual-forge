from __future__ import annotations

import hashlib
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from game_visual_forge.contracts import ApprovalArtifact, ApprovalStatus, TilemapApprovalGate, UserApprovalRecord, validate_user_approval


class TileMapApprovalTests(unittest.TestCase):
    def test_user_approval_round_trips(self) -> None:
        record = UserApprovalRecord(1, TilemapApprovalGate.STYLE_SAMPLE, ApprovalStatus.APPROVED, "user", "2026-08-07T04:00:00Z", (ApprovalArtifact("style-sample", "source/style-sample.png", "a" * 64), ApprovalArtifact("art-direction", "source/art-direction.json", "b" * 64)))
        self.assertEqual(UserApprovalRecord.from_dict(record.to_dict()).to_dict(), record.to_dict())

    def test_agent_reviewer_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "reviewer"):
            UserApprovalRecord(1, TilemapApprovalGate.STYLE_SAMPLE, ApprovalStatus.APPROVED, "agent", "2026-08-07T04:00:00Z", ())

    def test_changed_preview_invalidates_assembled_approval(self) -> None:
        record = UserApprovalRecord(1, TilemapApprovalGate.ASSEMBLED_MAP, ApprovalStatus.APPROVED, "user", "2026-08-07T04:00:00Z", tuple(ApprovalArtifact(role, f"source/{role}.bin", "a" * 64) for role in ("review-sheet", "tilemap-preview", "gameplay-crop", "tilemap-placement", "tilemap-objects", "tilemap-collision", "asset-set")))
        with self.assertRaisesRegex(ValueError, "hash"):
            validate_user_approval(record, TilemapApprovalGate.ASSEMBLED_MAP, {item.role: ("b" * 64 if item.role == "tilemap-preview" else "a" * 64) for item in record.artifacts})


if __name__ == "__main__":
    unittest.main()
