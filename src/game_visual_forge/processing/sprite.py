from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from game_visual_forge.contracts import RawImageRecord, SpriteRequest
from game_visual_forge.processing.alignment import align_bottom_center
from game_visual_forge.processing.background import remove_background
from game_visual_forge.processing.export import export_frames, export_gif, export_sheet
from game_visual_forge.processing.frames import split_grid, trim_alpha
from game_visual_forge.processing.images import _load_pillow, verify_image_unchanged


@dataclass(frozen=True)
class ProcessingResult:
    schema_version: int
    staging_dir: str
    frame_paths: tuple[str, ...]
    sheet_path: str | None
    gif_path: str | None
    processing_steps: tuple[str, ...]
    needs_attention: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "staging_dir": self.staging_dir,
            "frame_paths": list(self.frame_paths),
            "sheet_path": self.sheet_path,
            "gif_path": self.gif_path,
            "processing_steps": list(self.processing_steps),
            "needs_attention": self.needs_attention,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ProcessingResult":
        if value.get("schema_version") != 1:
            raise ValueError("ProcessingResult schema_version must be 1")
        if not isinstance(value.get("frame_paths"), list) or not isinstance(value.get("processing_steps"), list):
            raise TypeError("ProcessingResult arrays must be JSON arrays")
        return cls(
            schema_version=1,
            staging_dir=str(value["staging_dir"]),
            frame_paths=tuple(str(item) for item in value["frame_paths"]),
            sheet_path=None if value.get("sheet_path") is None else str(value["sheet_path"]),
            gif_path=None if value.get("gif_path") is None else str(value["gif_path"]),
            processing_steps=tuple(str(item) for item in value["processing_steps"]),
            needs_attention=value["needs_attention"],
        )

    @classmethod
    def from_paths(
        cls,
        repo_root: Path,
        staging: Path,
        frame_paths: tuple[Path, ...],
        sheet_path: Path | None,
        gif_path: Path | None,
        *,
        processing_steps: tuple[str, ...],
        needs_attention: bool,
    ) -> "ProcessingResult":
        root = repo_root.resolve()
        staging_relative = PurePosixPath(staging.resolve().relative_to(root).as_posix()).as_posix()
        def relative(path: Path) -> str:
            return PurePosixPath(path.resolve().relative_to(staging.resolve()).as_posix()).as_posix()
        return cls(
            1,
            staging_relative,
            tuple(relative(path) for path in frame_paths),
            None if sheet_path is None else relative(sheet_path),
            None if gif_path is None else relative(gif_path),
            processing_steps,
            needs_attention,
        )


def process_sprite(
    repo_root: Path,
    request: SpriteRequest,
    record: RawImageRecord,
    output_dir: Path,
) -> ProcessingResult:
    verify_image_unchanged(repo_root, record)
    Image = _load_pillow()
    source = repo_root.resolve() / PurePosixPath(record.path)
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
    background = remove_background(image, request)
    frames = split_grid(background.image, rows=request.grid_rows, columns=request.grid_columns, frame_count=request.frame_count)
    aligned = align_bottom_center(tuple(trim_alpha(frame) for frame in frames))
    staging = output_dir.parent / f".{output_dir.name}.staging-{record.sha256[:12]}"
    staging.mkdir(parents=True, exist_ok=True)
    frame_paths = export_frames(aligned, staging)
    sheet_path = export_sheet(aligned, request, staging)
    gif_path = export_gif(aligned, request, staging)
    return ProcessingResult.from_paths(
        repo_root,
        staging,
        frame_paths,
        sheet_path,
        gif_path,
        processing_steps=("verify-source", background.method, "split-grid", "trim-alpha", "align-bottom-center"),
        needs_attention=background.needs_attention,
    )


def publish_verified_outputs(staging_dir: Path, final_dir: Path, report: Any) -> bool:
    from game_visual_forge.contracts.quality import QualityStatus
    from game_visual_forge.errors import ErrorCode, ForgeError
    from game_visual_forge.processing.images import sha256_file

    if report.deterministic_status is QualityStatus.FAILED:
        raise ForgeError(ErrorCode.QUALITY_FAILED, "deterministic sprite validation failed", recoverable=True, context={"asset_id": report.asset_id})
    if report.visual_status is not QualityStatus.PASSED:
        return False
    if final_dir.exists():
        existing = final_dir / "asset-manifest.json"
        staged = staging_dir / "asset-manifest.json"
        if existing.is_file() and staged.is_file() and sha256_file(existing) == sha256_file(staged):
            return True
        raise ForgeError(ErrorCode.INVALID_REQUEST, "final output directory exists with different artifacts", recoverable=True, context={"output_dir": final_dir.name})
    os.replace(staging_dir, final_dir)
    return True
