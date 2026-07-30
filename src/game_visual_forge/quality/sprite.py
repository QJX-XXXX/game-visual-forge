from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any

from game_visual_forge.contracts import (
    ArtifactRecord,
    AssetManifest,
    QualityCheck,
    QualityReport,
    QualityStatus,
    RawImageRecord,
    SpriteRequest,
)
from game_visual_forge.processing.images import _load_pillow, sha256_file
from game_visual_forge.processing.sprite import ProcessingResult


VISUAL_CHECK_IDS = (
    "character-identity-consistency",
    "action-and-direction-correctness",
    "equipment-continuity",
    "anatomy-and-silhouette",
    "unwanted-text-or-watermark",
    "semantic-duplicate-frames",
)


def _check(check_id: str, status: QualityStatus, message: str, paths: tuple[str, ...] = ()) -> QualityCheck:
    return QualityCheck(check_id, status, message, paths)


def _frame_paths(processing: ProcessingResult) -> tuple[str, ...]:
    return processing.frame_paths


def check_source_dimensions(request: SpriteRequest, record: RawImageRecord) -> QualityCheck:
    status = QualityStatus.PASSED if (record.width, record.height) == (request.canvas_width, request.canvas_height) else QualityStatus.FAILED
    return _check("source-dimensions", status, "source dimensions match request" if status is QualityStatus.PASSED else "source dimensions do not match request")


def check_frame_count(request: SpriteRequest, processing: ProcessingResult) -> QualityCheck:
    status = QualityStatus.PASSED if len(processing.frame_paths) == request.frame_count else QualityStatus.FAILED
    return _check("frame-count", status, "frame count matches request")


def check_frame_readability(staging_dir: Path, processing: ProcessingResult) -> QualityCheck:
    Image = _load_pillow()
    for path in _frame_paths(processing):
        try:
            with Image.open(staging_dir / PurePosixPath(path)) as image:
                image.verify()
        except OSError:
            return _check("frame-readability", QualityStatus.FAILED, "frame is unreadable", (path,))
    return _check("frame-readability", QualityStatus.PASSED, "all frames are readable")


def check_frame_dimensions(staging_dir: Path, processing: ProcessingResult) -> QualityCheck:
    Image = _load_pillow()
    sizes = set()
    for path in _frame_paths(processing):
        with Image.open(staging_dir / PurePosixPath(path)) as image:
            sizes.add(image.size)
    status = QualityStatus.PASSED if len(sizes) <= 1 else QualityStatus.FAILED
    return _check("frame-dimensions", status, "output dimensions are consistent")


def check_alpha_coverage(staging_dir: Path, processing: ProcessingResult, *, minimum: float, maximum: float) -> QualityCheck:
    Image = _load_pillow()
    for path in _frame_paths(processing):
        with Image.open(staging_dir / PurePosixPath(path)).convert("RGBA") as image:
            alpha = image.getchannel("A")
            pixels = alpha.load()
            nonzero = sum(1 for y in range(alpha.height) for x in range(alpha.width) if pixels[x, y] > 0)
            coverage = nonzero / (image.width * image.height)
            if not minimum <= coverage <= maximum:
                return _check("alpha-coverage", QualityStatus.FAILED, "alpha coverage is outside configured limits", (path,))
    return _check("alpha-coverage", QualityStatus.PASSED, "alpha coverage is within configured limits")


def check_exact_duplicates(staging_dir: Path, processing: ProcessingResult) -> QualityCheck:
    hashes: dict[str, list[str]] = {}
    for path in _frame_paths(processing):
        digest = sha256_file(staging_dir / PurePosixPath(path))
        hashes.setdefault(digest, []).append(path)
    duplicate_paths = tuple(path for group in hashes.values() if len(group) > 1 for path in group)
    if duplicate_paths:
        return _check("exact-duplicate-frames", QualityStatus.NEEDS_ATTENTION, "exact duplicate frames were found", duplicate_paths)
    return _check("exact-duplicate-frames", QualityStatus.PASSED, "no exact duplicate frames were found")


def validate_sprite_outputs(staging_dir: Path, request: SpriteRequest, record: RawImageRecord, processing: ProcessingResult) -> QualityReport:
    checks = (
        check_source_dimensions(request, record),
        check_frame_count(request, processing),
        check_frame_readability(staging_dir, processing),
        check_frame_dimensions(staging_dir, processing),
        check_alpha_coverage(staging_dir, processing, minimum=0.001, maximum=1.0),
        check_exact_duplicates(staging_dir, processing),
    )
    deterministic = QualityStatus.FAILED if any(item.status is QualityStatus.FAILED for item in checks) else QualityStatus.NEEDS_ATTENTION if processing.needs_attention or any(item.status is QualityStatus.NEEDS_ATTENTION for item in checks) else QualityStatus.PASSED
    visual = tuple(_check(check_id, QualityStatus.NEEDS_VISUAL_REVIEW, "manual visual review required") for check_id in VISUAL_CHECK_IDS)
    return QualityReport(1, request.asset_id, record.request_fingerprint, deterministic, QualityStatus.NEEDS_VISUAL_REVIEW, checks, visual)


def apply_visual_review(report: QualityReport, payload: dict[str, Any]) -> QualityReport:
    if payload.get("schema_version") != 1 or not isinstance(payload.get("checks"), dict):
        raise ValueError("visual review must be a versioned checks object")
    checks = payload["checks"]
    if set(checks) != set(VISUAL_CHECK_IDS):
        raise ValueError("visual review must contain every required check exactly once")
    reviewed = tuple(_check(check_id, QualityStatus(checks[check_id]), "manual visual review") for check_id in VISUAL_CHECK_IDS)
    if any(item.status not in {QualityStatus.PASSED, QualityStatus.FAILED} for item in reviewed):
        raise ValueError("manual visual checks must be passed or failed")
    visual_status = QualityStatus.FAILED if any(item.status is QualityStatus.FAILED for item in reviewed) else QualityStatus.PASSED
    return replace(report, visual_status=visual_status, visual_checks=reviewed)


def artifact_role(path: str) -> str:
    if path.startswith("frames/"):
        return "frame"
    if path == "sprite-sheet.png":
        return "sheet"
    if path == "preview.gif":
        return "gif-preview"
    raise ValueError(f"unsupported sprite artifact path: {path}")


def build_asset_manifest(staging_dir: Path, request: SpriteRequest, record: RawImageRecord, processing: ProcessingResult, report: QualityReport) -> AssetManifest:
    paths = (*processing.frame_paths, *((processing.sheet_path,) if processing.sheet_path else ()), *((processing.gif_path,) if processing.gif_path else ()))
    output_artifacts = tuple(ArtifactRecord(role=artifact_role(path), path=f"{request.output_dir}/{path}", sha256=sha256_file(staging_dir / PurePosixPath(path))) for path in paths)
    artifacts = (ArtifactRecord(role="source", path=record.path, sha256=record.sha256), *output_artifacts)
    quality_status = "failed" if report.deterministic_status is QualityStatus.FAILED or report.visual_status is QualityStatus.FAILED else "passed" if report.deterministic_status is QualityStatus.PASSED and report.visual_status is QualityStatus.PASSED else "needs_attention"
    return AssetManifest(1, request.asset_id, record.source_type.value, record.provider.value if record.provider else None, record.model, artifacts, processing.processing_steps, quality_status)
