from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .map import MapSourceType
from .pathing import normalize_repo_relative_path


_SLUG_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class AtlasNormalizationStatus(StrEnum):
    NORMALIZED = "normalized"
    NOT_REQUIRED = "not_required"


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _sha256(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
    return value


def _path(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must not be empty")
    return normalize_repo_relative_path(value, field_name=field_name)


@dataclass(frozen=True)
class AtlasNormalizationPageRecord:
    atlas_id: str
    status: AtlasNormalizationStatus
    source_path: str
    source_sha256: str
    source_width: int
    source_height: int
    columns: int
    rows: int
    tile_width: int
    tile_height: int
    margin: int
    spacing: int
    resampling: str
    output_path: str
    output_sha256: str
    output_width: int
    output_height: int

    def __post_init__(self) -> None:
        if not _SLUG_PATTERN.fullmatch(self.atlas_id):
            raise ValueError("atlas_id must be a lowercase slug")
        if not isinstance(self.status, AtlasNormalizationStatus):
            raise TypeError("status must be AtlasNormalizationStatus")
        _path(self.source_path, "source_path")
        _path(self.output_path, "output_path")
        _sha256(self.source_sha256, "source_sha256")
        _sha256(self.output_sha256, "output_sha256")
        for field_name in (
            "source_width",
            "source_height",
            "columns",
            "rows",
            "tile_width",
            "tile_height",
            "output_width",
            "output_height",
        ):
            _positive_int(getattr(self, field_name), field_name)
        _non_negative_int(self.margin, "margin")
        _non_negative_int(self.spacing, "spacing")
        if not isinstance(self.resampling, str) or not self.resampling.strip():
            raise ValueError("resampling must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "atlas_id": self.atlas_id,
            "status": self.status.value,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "source_size": [self.source_width, self.source_height],
            "columns": self.columns,
            "rows": self.rows,
            "tile_size": [self.tile_width, self.tile_height],
            "margin": self.margin,
            "spacing": self.spacing,
            "resampling": self.resampling,
            "output_path": self.output_path,
            "output_sha256": self.output_sha256,
            "output_size": [self.output_width, self.output_height],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AtlasNormalizationPageRecord":
        if not isinstance(value, dict):
            raise TypeError("atlas normalization page must be an object")
        source_size = value.get("source_size")
        tile_size = value.get("tile_size")
        output_size = value.get("output_size")
        for name, item in (("source_size", source_size), ("tile_size", tile_size), ("output_size", output_size)):
            if not isinstance(item, list) or len(item) != 2:
                raise ValueError(f"{name} must contain width and height")
        return cls(
            atlas_id=str(value["atlas_id"]),
            status=AtlasNormalizationStatus(value["status"]),
            source_path=str(value["source_path"]),
            source_sha256=str(value["source_sha256"]),
            source_width=int(source_size[0]),
            source_height=int(source_size[1]),
            columns=int(value["columns"]),
            rows=int(value["rows"]),
            tile_width=int(tile_size[0]),
            tile_height=int(tile_size[1]),
            margin=int(value["margin"]),
            spacing=int(value["spacing"]),
            resampling=str(value["resampling"]),
            output_path=str(value["output_path"]),
            output_sha256=str(value["output_sha256"]),
            output_width=int(output_size[0]),
            output_height=int(output_size[1]),
        )


@dataclass(frozen=True)
class AtlasNormalizationReport:
    schema_version: int
    request_fingerprint: str
    source_type: MapSourceType
    status: AtlasNormalizationStatus
    pages: tuple[AtlasNormalizationPageRecord, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("atlas normalization report schema_version must be 1")
        _sha256(self.request_fingerprint, "request_fingerprint")
        if not isinstance(self.source_type, MapSourceType):
            raise TypeError("source_type must be MapSourceType")
        if not isinstance(self.status, AtlasNormalizationStatus):
            raise TypeError("status must be AtlasNormalizationStatus")
        if not self.pages or not all(isinstance(page, AtlasNormalizationPageRecord) for page in self.pages):
            raise ValueError("atlas normalization report must contain pages")
        page_ids = [page.atlas_id for page in self.pages]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("atlas normalization page ids must be unique")
        expected_status = AtlasNormalizationStatus.NOT_REQUIRED if all(page.status is AtlasNormalizationStatus.NOT_REQUIRED for page in self.pages) else AtlasNormalizationStatus.NORMALIZED
        if self.status is not expected_status:
            raise ValueError("atlas normalization report status does not match page statuses")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "request_fingerprint": self.request_fingerprint,
            "source_type": self.source_type.value,
            "status": self.status.value,
            "pages": [page.to_dict() for page in self.pages],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AtlasNormalizationReport":
        if not isinstance(value, dict):
            raise TypeError("atlas normalization report must be an object")
        pages = value.get("pages")
        if not isinstance(pages, list):
            raise TypeError("atlas normalization report pages must be an array")
        return cls(
            schema_version=int(value["schema_version"]),
            request_fingerprint=str(value["request_fingerprint"]),
            source_type=MapSourceType(value["source_type"]),
            status=AtlasNormalizationStatus(value["status"]),
            pages=tuple(AtlasNormalizationPageRecord.from_dict(item) for item in pages),
        )
