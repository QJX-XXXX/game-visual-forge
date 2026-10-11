from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .job import _validate_timestamp
from .pathing import normalize_repo_relative_path


class TilemapApprovalGate(StrEnum):
    STYLE_SAMPLE = "style-sample"
    ASSEMBLED_MAP = "assembled-map"


class ApprovalStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalArtifact:
    def __init__(self, role: str, path: str, sha256: str) -> None:
        self.role, self.path, self.sha256 = role, normalize_repo_relative_path(path, field_name="approval artifact path"), sha256
        if not role.strip() or len(sha256) != 64:
            raise ValueError("approval artifact role and sha256 are required")
        try:
            int(sha256, 16)
        except ValueError as error:
            raise ValueError("sha256 must be a SHA-256 hex digest") from error

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ApprovalArtifact) and (self.role, self.path, self.sha256) == (other.role, other.path, other.sha256)

    def __hash__(self) -> int:
        return hash((self.role, self.path, self.sha256))

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "path": self.path, "sha256": self.sha256.lower()}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ApprovalArtifact":
        return cls(str(value["role"]), str(value["path"]), str(value["sha256"]))


@dataclass(frozen=True)
class UserApprovalRecord:
    schema_version: int
    gate: TilemapApprovalGate
    status: ApprovalStatus
    reviewer: str
    approved_at: str
    artifacts: tuple[ApprovalArtifact, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if isinstance(self.gate, str):
            object.__setattr__(self, "gate", TilemapApprovalGate(self.gate))
        if isinstance(self.status, str):
            object.__setattr__(self, "status", ApprovalStatus(self.status))
        if self.reviewer != "user":
            raise ValueError("reviewer must be user")
        _validate_timestamp(self.approved_at, field_name="approved_at")
        if self.status is not ApprovalStatus.APPROVED:
            raise ValueError("only approved records may gate publication")
        if len({item.role for item in self.artifacts}) != len(self.artifacts):
            raise ValueError("approval artifact roles must be unique")

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "gate": self.gate.value, "status": self.status.value, "reviewer": self.reviewer, "approved_at": self.approved_at, "artifacts": [item.to_dict() for item in self.artifacts]}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "UserApprovalRecord":
        if int(value["schema_version"]) != 1:
            raise ValueError("unsupported UserApprovalRecord schema_version")
        return cls(1, TilemapApprovalGate(value["gate"]), ApprovalStatus(value["status"]), str(value["reviewer"]), str(value["approved_at"]), tuple(ApprovalArtifact.from_dict(item) for item in value["artifacts"]))


STYLE_APPROVAL_ROLES = ("style-sample", "art-direction")
ASSEMBLED_APPROVAL_ROLES = ("review-sheet", "tilemap-preview", "gameplay-crop", "tilemap-placement", "tilemap-objects", "tilemap-collision", "asset-set")


def record_user_approval(gate: TilemapApprovalGate, artifact_paths: tuple[tuple[str, Path], ...], repo_root: Path, approved_at: str) -> UserApprovalRecord:
    from game_visual_forge.processing.images import sha256_file
    artifacts = []
    for role, path in artifact_paths:
        absolute = path.resolve()
        relative = absolute.relative_to(repo_root.resolve()).as_posix()
        artifacts.append(ApprovalArtifact(role, relative, sha256_file(absolute)))
    record = UserApprovalRecord(1, gate, ApprovalStatus.APPROVED, "user", approved_at, tuple(artifacts))
    expected = STYLE_APPROVAL_ROLES if gate is TilemapApprovalGate.STYLE_SAMPLE else ASSEMBLED_APPROVAL_ROLES
    if tuple(item.role for item in record.artifacts) != expected:
        raise ValueError(f"{gate.value} approval must contain exact roles {expected}")
    return record


def validate_user_approval(record: UserApprovalRecord, gate: TilemapApprovalGate, expected_hashes: dict[str, str]) -> None:
    if record.gate is not gate or record.status is not ApprovalStatus.APPROVED or record.reviewer != "user":
        raise ValueError("approval gate, status, or reviewer is invalid")
    expected_roles = STYLE_APPROVAL_ROLES if gate is TilemapApprovalGate.STYLE_SAMPLE else ASSEMBLED_APPROVAL_ROLES
    if tuple(item.role for item in record.artifacts) != expected_roles:
        raise ValueError(f"{gate.value} approval must contain exact roles {expected_roles}")
    for item in record.artifacts:
        if item.role not in expected_hashes or item.sha256.lower() != expected_hashes[item.role].lower():
            raise ValueError(f"approval artifact hash mismatch for {item.role}")


def validate_user_approval_files(payload: dict[str, Any], gate: TilemapApprovalGate, repo_root: Path) -> UserApprovalRecord:
    from game_visual_forge.processing.images import sha256_file
    record = UserApprovalRecord.from_dict(payload)
    hashes = {}
    for item in record.artifacts:
        path = repo_root.resolve() / item.path
        if not path.is_file():
            raise ValueError(f"approval artifact is missing: {item.path}")
        hashes[item.role] = sha256_file(path)
    validate_user_approval(record, gate, hashes)
    return record
