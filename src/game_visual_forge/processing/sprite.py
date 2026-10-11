from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from game_visual_forge.contracts import RawImageRecord, SpriteRequest
from game_visual_forge.errors import ErrorCode, ForgeError
from game_visual_forge.processing.alignment import align_bottom_center
from game_visual_forge.processing.background import remove_background
from game_visual_forge.processing.delivery import normalize_delivery_frames
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
    delivery_frame_paths: tuple[str, ...] = ()
    delivery_sheet_path: str | None = None
    delivery_gif_path: str | None = None
    delivery_metadata: dict[str, Any] | None = None
    background_alpha: dict[str, Any] | None = None
    generation_metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "staging_dir": self.staging_dir,
            "frame_paths": list(self.frame_paths),
            "sheet_path": self.sheet_path,
            "gif_path": self.gif_path,
            "processing_steps": list(self.processing_steps),
            "needs_attention": self.needs_attention,
            "delivery_frame_paths": list(self.delivery_frame_paths),
            "delivery_sheet_path": self.delivery_sheet_path,
            "delivery_gif_path": self.delivery_gif_path,
            "delivery_metadata": self.delivery_metadata,
            "background_alpha": self.background_alpha,
            "generation_metadata": self.generation_metadata,
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
            delivery_frame_paths=tuple(str(item) for item in value.get("delivery_frame_paths", [])),
            delivery_sheet_path=None if value.get("delivery_sheet_path") is None else str(value["delivery_sheet_path"]),
            delivery_gif_path=None if value.get("delivery_gif_path") is None else str(value["delivery_gif_path"]),
            delivery_metadata=value.get("delivery_metadata"),
            background_alpha=value.get("background_alpha"),
            generation_metadata=value.get("generation_metadata"),
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
        delivery_frame_paths: tuple[Path, ...] = (),
        delivery_sheet_path: Path | None = None,
        delivery_gif_path: Path | None = None,
        delivery_metadata: dict[str, Any] | None = None,
        background_alpha: dict[str, Any] | None = None,
        generation_metadata: dict[str, Any] | None = None,
    ) -> "ProcessingResult":
        root = repo_root.resolve()
        staging_relative = PurePosixPath(staging.resolve().relative_to(root).as_posix()).as_posix()
        def relative(path: Path) -> str:
            return PurePosixPath(path.resolve().relative_to(staging.resolve()).as_posix()).as_posix()
        return cls(
            schema_version=1,
            staging_dir=staging_relative,
            frame_paths=tuple(relative(path) for path in frame_paths),
            sheet_path=None if sheet_path is None else relative(sheet_path),
            gif_path=None if gif_path is None else relative(gif_path),
            processing_steps=processing_steps,
            needs_attention=needs_attention,
            delivery_frame_paths=tuple(relative(path) for path in delivery_frame_paths),
            delivery_sheet_path=None if delivery_sheet_path is None else relative(delivery_sheet_path),
            delivery_gif_path=None if delivery_gif_path is None else relative(delivery_gif_path),
            delivery_metadata=delivery_metadata,
            background_alpha=background_alpha,
            generation_metadata=generation_metadata,
        )


def _seed_reference_path(request: SpriteRequest) -> str | None:
    if request.seed_frame_path is not None:
        return request.seed_frame_path
    if request.frame_count > 1 and request.reference_paths:
        return request.reference_paths[0]
    return None


def _load_seed_frame(
    repo_root: Path,
    request: SpriteRequest,
    Image: Any,
) -> tuple[Any, bool, dict[str, Any] | None]:
    if request.seed_frame_path is None:
        raise ForgeError(
            ErrorCode.INVALID_REQUEST,
            "lock_frame1 requires an explicit seed frame path",
            recoverable=True,
            context={"field": "seed_frame_path"},
        )
    seed_path = repo_root.resolve() / PurePosixPath(request.seed_frame_path)
    try:
        with Image.open(seed_path) as opened:
            seed_background = remove_background(opened, request)
    except (OSError, ValueError) as error:
        raise ForgeError(
            ErrorCode.IMAGE_UNREADABLE,
            "seed frame cannot be decoded",
            recoverable=True,
            context={"path": request.seed_frame_path},
        ) from error
    return trim_alpha(seed_background.image), seed_background.needs_attention, seed_background.alpha_report


def _merge_alpha_reports(
    primary: dict[str, Any] | None,
    seed: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if seed is None:
        return primary
    merged = dict(primary or {})
    merged["seed"] = seed
    primary_output = merged.get("output")
    seed_output = seed.get("output") if isinstance(seed, dict) else None
    if isinstance(primary_output, dict) and isinstance(seed_output, dict):
        output = dict(primary_output)
        output["transparent_background_valid"] = (
            output.get("transparent_background_valid") is True
            and seed_output.get("transparent_background_valid") is True
        )
        merged["output"] = output
    return merged


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
        background = remove_background(opened, request)
    frames = split_grid(background.image, rows=request.grid_rows, columns=request.grid_columns, frame_count=request.frame_count)
    trimmed_frames = tuple(trim_alpha(frame) for frame in frames)
    seed_needs_attention = False
    seed_alpha_report: dict[str, Any] | None = None
    processing_steps = [
        "verify-source",
        background.method,
        "split-grid",
        "trim-alpha",
    ]
    if request.lock_frame1:
        seed_frame, seed_needs_attention, seed_alpha_report = _load_seed_frame(
            repo_root,
            request,
            Image,
        )
        trimmed_frames = (seed_frame, *trimmed_frames[1:])
        processing_steps.append("lock-frame1-to-seed")
    aligned = align_bottom_center(trimmed_frames)
    staging = output_dir.parent / f".{output_dir.name}.staging-{record.sha256[:12]}"
    staging.mkdir(parents=True, exist_ok=True)
    frame_paths = export_frames(aligned, staging)
    sheet_path = export_sheet(aligned, request, staging)
    gif_path = export_gif(aligned, request, staging)
    delivery_frame_paths: tuple[Path, ...] = ()
    delivery_sheet_path: Path | None = None
    delivery_gif_path: Path | None = None
    delivery_metadata: dict[str, Any] | None = None
    processing_steps.append("align-bottom-center")
    if request.delivery_normalization is not None:
        delivery = normalize_delivery_frames(aligned, request.delivery_normalization)
        delivery_dir = staging / "delivery"
        delivery_frame_paths = export_frames(delivery.frames, delivery_dir)
        delivery_sheet_path = export_sheet(delivery.frames, request, delivery_dir)
        delivery_gif_path = export_gif(delivery.frames, request, delivery_dir)
        delivery_metadata = {
            "canvas_width": request.delivery_normalization.canvas_width,
            "canvas_height": request.delivery_normalization.canvas_height,
            "anchor": request.delivery_normalization.anchor.value,
            "fit_scale": request.delivery_normalization.fit_scale,
            "scale": delivery.scale,
            "source_bounds": [list(bounds) for bounds in delivery.source_bounds],
        }
        processing_steps.append(
            f"delivery-normalize-{request.delivery_normalization.anchor.value}"
        )
    return ProcessingResult.from_paths(
        repo_root,
        staging,
        frame_paths,
        sheet_path,
        gif_path,
        processing_steps=tuple(processing_steps),
        needs_attention=background.needs_attention or seed_needs_attention,
        delivery_frame_paths=delivery_frame_paths,
        delivery_sheet_path=delivery_sheet_path,
        delivery_gif_path=delivery_gif_path,
        delivery_metadata=delivery_metadata,
        background_alpha=_merge_alpha_reports(background.alpha_report, seed_alpha_report),
        generation_metadata={
            "route": (
                "seeded-whole-strip"
                if request.frame_count > 1 and _seed_reference_path(request) is not None
                else "whole-strip"
                if request.frame_count > 1
                else "single-frame"
            ),
            "seed_frame_path": _seed_reference_path(request),
            "whole_strip": request.frame_count > 1,
            "lock_frame1": request.lock_frame1,
        },
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
