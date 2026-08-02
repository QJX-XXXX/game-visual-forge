from __future__ import annotations

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
    TileMapRequest,
)
from game_visual_forge.contracts.serialization import load_json
from game_visual_forge.processing.images import _load_pillow, sha256_file
from game_visual_forge.processing.tilemap import TileMapProcessingResult


TILEMAP_VISUAL_CHECK_IDS = (
    "tileset-seams",
    "tilemap-readability",
    "layer-order",
    "collision-layer",
    "unwanted-text-or-watermark",
)


def _check(check_id: str, status: QualityStatus, message: str, paths: tuple[str, ...] = ()) -> QualityCheck:
    return QualityCheck(check_id, status, message, paths)


def _paths(processing: TileMapProcessingResult) -> tuple[str, ...]:
    return (
        processing.tileset_path,
        processing.slices_path,
        processing.placement_path,
        processing.unity_manifest_path,
        processing.preview_path,
    )


def validate_tilemap_outputs(
    staging_dir: Path,
    request: TileMapRequest,
    record: RawImageRecord,
    processing: TileMapProcessingResult,
) -> QualityReport:
    Image = _load_pillow()
    checks: list[QualityCheck] = []
    checks.append(_check(
        "source-dimensions",
        QualityStatus.PASSED if (record.width, record.height) == request.expected_atlas_size else QualityStatus.FAILED,
        "source dimensions match the declared atlas grid",
    ))

    unreadable: list[str] = []
    for path in _paths(processing):
        target = staging_dir / PurePosixPath(path)
        if not target.is_file():
            unreadable.append(path)
            continue
        try:
            if path.endswith(".json"):
                load_json(target)
            else:
                with Image.open(target) as image:
                    image.verify()
        except (OSError, ValueError, TypeError):
            unreadable.append(path)
    checks.append(_check(
        "tilemap-artifacts-readable",
        QualityStatus.FAILED if unreadable else QualityStatus.PASSED,
        "tilemap artifacts are readable" if not unreadable else "tilemap artifacts are missing or unreadable",
        tuple(unreadable),
    ))

    wrong_size: list[str] = []
    raster_sizes = {
        processing.tileset_path: request.expected_atlas_size,
        processing.preview_path: (request.map_width * request.tile_width, request.map_height * request.tile_height),
    }
    for path, expected in raster_sizes.items():
        try:
            with Image.open(staging_dir / PurePosixPath(path)) as image:
                if image.size != expected:
                    wrong_size.append(path)
        except OSError:
            wrong_size.append(path)
    checks.append(_check(
        "tilemap-raster-dimensions",
        QualityStatus.FAILED if wrong_size else QualityStatus.PASSED,
        "tilemap raster dimensions match the request" if not wrong_size else "tilemap raster dimensions do not match the request",
        tuple(wrong_size),
    ))

    try:
        slices = load_json(staging_dir / processing.slices_path)
        placement = load_json(staging_dir / processing.placement_path)
        unity = load_json(staging_dir / processing.unity_manifest_path)
        metadata_valid = (
            len(slices["tiles"]) == len(request.tiles)
            and len(placement["layers"]) == len(request.layers)
            and unity["engine_target"] == "Unity_Tilemap"
            and unity["generated_root"].startswith("Assets/")
        )
    except (OSError, ValueError, TypeError, KeyError):
        metadata_valid = False
    checks.append(_check(
        "unity-bundle-contract",
        QualityStatus.PASSED if metadata_valid else QualityStatus.FAILED,
        "Unity bundle metadata matches the request" if metadata_valid else "Unity bundle metadata is incomplete or inconsistent",
    ))

    deterministic = QualityStatus.FAILED if any(item.status is QualityStatus.FAILED for item in checks) else QualityStatus.NEEDS_ATTENTION if processing.needs_attention else QualityStatus.PASSED
    visual = tuple(_check(check_id, QualityStatus.NEEDS_VISUAL_REVIEW, "manual visual review required") for check_id in TILEMAP_VISUAL_CHECK_IDS)
    return QualityReport(1, request.asset_id, record.request_fingerprint, deterministic, QualityStatus.NEEDS_VISUAL_REVIEW, tuple(checks), visual)


def apply_tilemap_visual_review(report: QualityReport, payload: dict[str, Any]) -> QualityReport:
    if payload.get("schema_version") != 1 or not isinstance(payload.get("checks"), dict):
        raise ValueError("visual review must be a versioned checks object")
    checks = payload["checks"]
    if set(checks) != set(TILEMAP_VISUAL_CHECK_IDS):
        raise ValueError("tilemap visual review must contain every required check exactly once")
    reviewed = tuple(_check(check_id, QualityStatus(checks[check_id]), "manual visual review") for check_id in TILEMAP_VISUAL_CHECK_IDS)
    if any(item.status not in {QualityStatus.PASSED, QualityStatus.FAILED} for item in reviewed):
        raise ValueError("manual tilemap visual checks must be passed or failed")
    visual_status = QualityStatus.FAILED if any(item.status is QualityStatus.FAILED for item in reviewed) else QualityStatus.PASSED
    return replace(report, visual_status=visual_status, visual_checks=reviewed)


def build_tilemap_asset_manifest(
    staging_dir: Path,
    request: TileMapRequest,
    record: RawImageRecord,
    processing: TileMapProcessingResult,
    report: QualityReport,
) -> AssetManifest:
    roles = {
        processing.tileset_path: "tileset",
        processing.slices_path: "sprite-slices",
        processing.placement_path: "tilemap-placement",
        processing.unity_manifest_path: "unity-import-manifest",
        processing.preview_path: "tilemap-preview",
    }
    outputs = tuple(
        ArtifactRecord(role=roles[path], path=f"{request.output_dir}/{path}", sha256=sha256_file(staging_dir / PurePosixPath(path)))
        for path in _paths(processing)
    )
    artifacts = (ArtifactRecord(role="source", path=record.path, sha256=record.sha256), *outputs)
    quality_status = "failed" if report.deterministic_status is QualityStatus.FAILED or report.visual_status is QualityStatus.FAILED else "passed" if report.deterministic_status is QualityStatus.PASSED and report.visual_status is QualityStatus.PASSED else "needs_attention"
    return AssetManifest(1, request.asset_id, record.source_type.value, record.provider.value if record.provider else None, record.model, artifacts, processing.processing_steps, quality_status)
