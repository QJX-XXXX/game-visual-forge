from __future__ import annotations

from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any

from game_visual_forge.contracts import (
    ArtifactRecord,
    AssetManifest,
    MapRequest,
    QualityCheck,
    QualityReport,
    QualityStatus,
    RawImageRecord,
)
from game_visual_forge.contracts.serialization import load_json
from game_visual_forge.processing.images import _load_pillow, sha256_file
from game_visual_forge.processing.map import MapProcessingResult


MAP_VISUAL_CHECK_IDS = (
    "base-map-readability",
    "walkable-route-continuity",
    "collision-boundaries",
    "spawn-and-zones",
    "layer-separation",
    "unwanted-text-or-watermark",
)


def _check(check_id: str, status: QualityStatus, message: str, paths: tuple[str, ...] = ()) -> QualityCheck:
    return QualityCheck(check_id, status, message, paths)


def _paths(processing: MapProcessingResult) -> tuple[str, ...]:
    return (
        processing.base_map_path,
        processing.runtime_path,
        processing.walkable_mask_path,
        processing.collision_mask_path,
        processing.preview_path,
    )


def validate_map_outputs(
    staging_dir: Path,
    request: MapRequest,
    record: RawImageRecord,
    processing: MapProcessingResult,
) -> QualityReport:
    Image = _load_pillow()
    checks: list[QualityCheck] = []
    checks.append(_check(
        "source-dimensions",
        QualityStatus.PASSED if (record.width, record.height) == (request.canvas_width, request.canvas_height) else QualityStatus.FAILED,
        "source dimensions match map canvas",
    ))
    unreadable = []
    wrong_size = []
    for path in _paths(processing):
        target = staging_dir / PurePosixPath(path)
        if not target.is_file():
            unreadable.append(path)
            continue
        if path.endswith(".json"):
            try:
                load_json(target)
            except (OSError, ValueError, TypeError):
                unreadable.append(path)
            continue
        try:
            with Image.open(target) as image:
                if image.size != (request.canvas_width, request.canvas_height):
                    wrong_size.append(path)
                image.verify()
        except OSError:
            unreadable.append(path)
    checks.append(_check("map-artifacts-readable", QualityStatus.FAILED if unreadable else QualityStatus.PASSED, "map artifacts are readable" if not unreadable else "map artifacts are missing or unreadable", tuple(unreadable)))
    checks.append(_check("map-artifact-dimensions", QualityStatus.FAILED if wrong_size else QualityStatus.PASSED, "map raster artifacts match canvas dimensions" if not wrong_size else "map raster artifact dimensions do not match canvas", tuple(wrong_size)))

    try:
        with Image.open(staging_dir / processing.walkable_mask_path) as walkable_image, Image.open(staging_dir / processing.collision_mask_path) as collision_image:
            walkable = walkable_image.convert("L")
            collision = collision_image.convert("L")
            spawn_walkable = walkable.getpixel((request.spawn.x, request.spawn.y)) > 0
            spawn_clear = collision.getpixel((request.spawn.x, request.spawn.y)) == 0
            walkable_pixels = sum(walkable.histogram()[1:])
    except (OSError, ValueError):
        spawn_walkable = False
        spawn_clear = False
        walkable_pixels = 0
    spawn_status = QualityStatus.PASSED if spawn_walkable and spawn_clear else QualityStatus.FAILED
    checks.append(_check("spawn-is-walkable", spawn_status, "spawn is inside walkable space and outside blockers" if spawn_status is QualityStatus.PASSED else "spawn is not walkable or is blocked"))
    checks.append(_check("walkable-area-present", QualityStatus.PASSED if walkable_pixels else QualityStatus.FAILED, "walkable area is non-empty" if walkable_pixels else "walkable area is empty"))
    deterministic = QualityStatus.FAILED if any(check.status is QualityStatus.FAILED for check in checks) else QualityStatus.NEEDS_ATTENTION if processing.needs_attention else QualityStatus.PASSED
    visual = tuple(_check(check_id, QualityStatus.NEEDS_VISUAL_REVIEW, "manual visual review required") for check_id in MAP_VISUAL_CHECK_IDS)
    return QualityReport(1, request.asset_id, record.request_fingerprint, deterministic, QualityStatus.NEEDS_VISUAL_REVIEW, tuple(checks), visual)


def apply_map_visual_review(report: QualityReport, payload: dict[str, Any]) -> QualityReport:
    if payload.get("schema_version") != 1 or not isinstance(payload.get("checks"), dict):
        raise ValueError("visual review must be a versioned checks object")
    checks = payload["checks"]
    if set(checks) != set(MAP_VISUAL_CHECK_IDS):
        raise ValueError("map visual review must contain every required check exactly once")
    reviewed = tuple(_check(check_id, QualityStatus(checks[check_id]), "manual visual review") for check_id in MAP_VISUAL_CHECK_IDS)
    if any(item.status not in {QualityStatus.PASSED, QualityStatus.FAILED} for item in reviewed):
        raise ValueError("manual map visual checks must be passed or failed")
    visual_status = QualityStatus.FAILED if any(item.status is QualityStatus.FAILED for item in reviewed) else QualityStatus.PASSED
    return replace(report, visual_status=visual_status, visual_checks=reviewed)


def build_map_asset_manifest(
    staging_dir: Path,
    request: MapRequest,
    record: RawImageRecord,
    processing: MapProcessingResult,
    report: QualityReport,
) -> AssetManifest:
    roles = {
        processing.base_map_path: "base-map",
        processing.runtime_path: "map-runtime",
        processing.walkable_mask_path: "walkable-mask",
        processing.collision_mask_path: "collision-mask",
        processing.preview_path: "debug-preview",
    }
    outputs = tuple(
        ArtifactRecord(
            role=roles[path],
            path=f"{request.output_dir}/{path}",
            sha256=sha256_file(staging_dir / PurePosixPath(path)),
        )
        for path in _paths(processing)
    )
    artifacts = (ArtifactRecord(role="source", path=record.path, sha256=record.sha256), *outputs)
    quality_status = "failed" if report.deterministic_status is QualityStatus.FAILED or report.visual_status is QualityStatus.FAILED else "passed" if report.deterministic_status is QualityStatus.PASSED and report.visual_status is QualityStatus.PASSED else "needs_attention"
    return AssetManifest(1, request.asset_id, record.source_type.value, record.provider.value if record.provider else None, record.model, artifacts, processing.processing_steps, quality_status)
