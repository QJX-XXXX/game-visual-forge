from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import (
    AtlasNormalizationPageRecord,
    AtlasNormalizationReport,
    AtlasNormalizationStatus,
    MapSourceType,
)


class AtlasNormalizationContractTests(unittest.TestCase):
    def test_report_round_trip_preserves_page_order_and_hashes(self) -> None:
        page = AtlasNormalizationPageRecord(
            "page-01",
            AtlasNormalizationStatus.NORMALIZED,
            "runs/raw/page-01.png",
            "a" * 64,
            1024,
            1024,
            4,
            4,
            32,
            32,
            0,
            0,
            "nearest",
            "runs/normalized/page-01.png",
            "b" * 64,
            128,
            128,
        )
        report = AtlasNormalizationReport(
            1,
            "c" * 64,
            MapSourceType.AGENT_NATIVE,
            AtlasNormalizationStatus.NORMALIZED,
            (page,),
        )

        self.assertEqual(AtlasNormalizationReport.from_dict(report.to_dict()), report)

    def test_report_rejects_duplicate_pages_and_bad_hashes(self) -> None:
        page = AtlasNormalizationPageRecord(
            "page-01",
            AtlasNormalizationStatus.NOT_REQUIRED,
            "runs/raw/page-01.png",
            "a" * 64,
            128,
            128,
            4,
            4,
            32,
            32,
            0,
            0,
            "none",
            "runs/raw/page-01.png",
            "a" * 64,
            128,
            128,
        )
        with self.assertRaises(ValueError):
            AtlasNormalizationReport(
                1,
                "bad",
                MapSourceType.AGENT_NATIVE,
                AtlasNormalizationStatus.NOT_REQUIRED,
                (page,),
            )
        with self.assertRaises(ValueError):
            AtlasNormalizationReport(
                1,
                "c" * 64,
                MapSourceType.AGENT_NATIVE,
                AtlasNormalizationStatus.NOT_REQUIRED,
                (page, page),
            )


if __name__ == "__main__":
    unittest.main()
