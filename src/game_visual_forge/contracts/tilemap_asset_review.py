from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from pathlib import Path, PurePosixPath
import hashlib

from .quality import QualityCheck, QualityStatus


class CandidateAssetKind(StrEnum):
    FOUNDATION = "foundation"
    ATLAS = "atlas"
    BRIDGE = "bridge"
    OBJECT = "object"


class PreassemblyReviewStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class CandidateAsset:
    asset_id: str
    kind: CandidateAssetKind
    path: str
    sha256: str
    width: int
    height: int

    def to_dict(self) -> dict[str, Any]:
        return {"asset_id": self.asset_id, "kind": self.kind.value, "path": self.path, "sha256": self.sha256, "width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CandidateAsset":
        return cls(str(value["asset_id"]), CandidateAssetKind(value["kind"]), str(value["path"]), str(value["sha256"]), int(value["width"]), int(value["height"]))


@dataclass(frozen=True)
class CriticalAssetCheck:
    check_id: str
    status: QualityStatus
    message: str
    asset_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "status": self.status.value, "message": self.message, "asset_ids": list(self.asset_ids)}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CriticalAssetCheck":
        return cls(str(value["check_id"]), QualityStatus(value["status"]), str(value["message"]), tuple(str(item) for item in value.get("asset_ids", [])))


@dataclass(frozen=True)
class TilemapCriticalAssetReport:
    schema_version: int
    request_fingerprint: str
    architecture_sha256: str
    candidates: tuple[CandidateAsset, ...]
    checks: tuple[CriticalAssetCheck, ...]
    deterministic_status: QualityStatus
    visual_status: QualityStatus
    review_sheet_path: str
    focus_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "request_fingerprint": self.request_fingerprint,
            "architecture_sha256": self.architecture_sha256,
            "candidates": [item.to_dict() for item in self.candidates],
            "checks": [item.to_dict() for item in self.checks],
            "deterministic_status": self.deterministic_status.value,
            "visual_status": self.visual_status.value,
            "review_sheet_path": self.review_sheet_path,
            "focus_paths": list(self.focus_paths),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TilemapCriticalAssetReport":
        return cls(int(value["schema_version"]), str(value["request_fingerprint"]), str(value["architecture_sha256"]), tuple(CandidateAsset.from_dict(item) for item in value["candidates"]), tuple(CriticalAssetCheck.from_dict(item) for item in value["checks"]), QualityStatus(value["deterministic_status"]), QualityStatus(value["visual_status"]), str(value["review_sheet_path"]), tuple(str(item) for item in value.get("focus_paths", [])))


@dataclass(frozen=True)
class PreassemblyAssetDecision:
    asset_id: str
    status: PreassemblyReviewStatus
    reason_code: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"asset_id": self.asset_id, "status": self.status.value, "reason_code": self.reason_code, "reason": self.reason}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PreassemblyAssetDecision":
        return cls(str(value["asset_id"]), PreassemblyReviewStatus(value["status"]), str(value["reason_code"]), str(value["reason"]))


@dataclass(frozen=True)
class TilemapPreassemblyReview:
    schema_version: int
    request_fingerprint: str
    architecture_sha256: str
    candidate_ids: tuple[str, ...]
    candidate_sha256: tuple[str, ...]
    decisions: tuple[PreassemblyAssetDecision, ...]
    status: PreassemblyReviewStatus
    reviewed_at: str

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "request_fingerprint": self.request_fingerprint, "architecture_sha256": self.architecture_sha256, "candidate_ids": list(self.candidate_ids), "candidate_sha256": list(self.candidate_sha256), "decisions": [item.to_dict() for item in self.decisions], "status": self.status.value, "reviewed_at": self.reviewed_at}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TilemapPreassemblyReview":
        return cls(int(value["schema_version"]), str(value["request_fingerprint"]), str(value["architecture_sha256"]), tuple(str(item) for item in value["candidate_ids"]), tuple(str(item) for item in value["candidate_sha256"]), tuple(PreassemblyAssetDecision.from_dict(item) for item in value["decisions"]), PreassemblyReviewStatus(value["status"]), str(value["reviewed_at"]))


def record_preassembly_review(report: TilemapCriticalAssetReport, decisions: tuple[PreassemblyAssetDecision, ...], reviewed_at: str) -> TilemapPreassemblyReview:
    by_id = {item.asset_id: item for item in decisions}
    if set(by_id) != {item.asset_id for item in report.candidates}:
        raise ValueError("preassembly review must decide every candidate exactly once")
    accepted = report.deterministic_status is QualityStatus.PASSED and all(by_id[item.asset_id].status is PreassemblyReviewStatus.ACCEPTED for item in report.candidates)
    return TilemapPreassemblyReview(1, report.request_fingerprint, report.architecture_sha256, tuple(item.asset_id for item in report.candidates), tuple(item.sha256 for item in report.candidates), tuple(by_id[item.asset_id] for item in report.candidates), PreassemblyReviewStatus.ACCEPTED if accepted else PreassemblyReviewStatus.REJECTED, reviewed_at)


def validate_preassembly_review(report: TilemapCriticalAssetReport, review: TilemapPreassemblyReview) -> None:
    if review.status is not PreassemblyReviewStatus.ACCEPTED:
        raise ValueError("preassembly review is not accepted")
    if review.request_fingerprint != report.request_fingerprint or review.architecture_sha256 != report.architecture_sha256:
        raise ValueError("preassembly review does not match request or architecture")
    if review.candidate_ids != tuple(item.asset_id for item in report.candidates) or review.candidate_sha256 != tuple(item.sha256 for item in report.candidates):
        raise ValueError("candidate hashes or ordering changed after preassembly review")
    if report.deterministic_status is not QualityStatus.PASSED:
        raise ValueError("candidate deterministic checks are not passed")


def validate_preassembly_candidate_files(report: TilemapCriticalAssetReport, repo_root: Path) -> None:
    for candidate in report.candidates:
        path = repo_root.resolve() / PurePosixPath(candidate.path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != candidate.sha256:
            raise ValueError("candidate hashes changed after preassembly review")
