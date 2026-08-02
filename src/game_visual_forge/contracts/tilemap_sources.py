from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .sprite import RawImageRecord
from .tilemap import TileMapRequest


@dataclass(frozen=True)
class TileAtlasSourceRecord:
    atlas_id: str
    image: RawImageRecord

    def __post_init__(self) -> None:
        if not self.atlas_id or not isinstance(self.atlas_id, str):
            raise ValueError("atlas_id must not be empty")
        if not isinstance(self.image, RawImageRecord):
            raise TypeError("image must be RawImageRecord")

    def to_dict(self) -> dict[str, Any]:
        return {"atlas_id": self.atlas_id, "image": self.image.to_dict()}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TileAtlasSourceRecord":
        return cls(str(value["atlas_id"]), RawImageRecord.from_dict(value["image"]))


@dataclass(frozen=True)
class TileMapSourceSet:
    schema_version: int
    pages: tuple[TileAtlasSourceRecord, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("TileMapSourceSet schema_version must be 1")
        if not self.pages or not all(isinstance(page, TileAtlasSourceRecord) for page in self.pages):
            raise ValueError("TileMapSourceSet must contain atlas page sources")
        ids = [page.atlas_id for page in self.pages]
        if len(ids) != len(set(ids)):
            raise ValueError("atlas page sources must have unique ids")

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "pages": [page.to_dict() for page in self.pages]}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TileMapSourceSet":
        pages = value["pages"]
        if not isinstance(pages, list):
            raise TypeError("TileMapSourceSet pages must be a JSON array")
        return cls(1, tuple(TileAtlasSourceRecord.from_dict(item) for item in pages))


def load_tilemap_source_set(payload: dict[str, Any], request: TileMapRequest) -> TileMapSourceSet:
    if "pages" in payload:
        source_set = TileMapSourceSet.from_dict(payload)
    else:
        source_set = TileMapSourceSet(1, (TileAtlasSourceRecord("page-01", RawImageRecord.from_dict(payload)),))
    expected_ids = tuple(page.atlas_id for page in request.resolved_atlas_pages)
    actual_ids = tuple(page.atlas_id for page in source_set.pages)
    if actual_ids != expected_ids:
        raise ValueError(f"atlas page sources must match request pages: expected {expected_ids}, got {actual_ids}")
    fingerprints = {page.image.request_fingerprint for page in source_set.pages}
    if fingerprints != {next(iter(fingerprints))}:
        raise ValueError("atlas page sources must share one request fingerprint")
    return source_set


def parse_atlas_page_argument(value: str) -> tuple[str, Path]:
    atlas_id, separator, path = value.partition("=")
    if not separator or not atlas_id or not path:
        raise ValueError("--atlas-page must use atlas-id=path syntax")
    return atlas_id, Path(path)
