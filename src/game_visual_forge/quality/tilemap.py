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
    TileMapSourceSet,
    load_tilemap_source_set,
)
from game_visual_forge.contracts.serialization import load_json
from game_visual_forge.processing.images import _load_pillow, sha256_file
from game_visual_forge.processing.tilemap import TileMapProcessingResult
from game_visual_forge.processing.tilemap_quality import SEAM_ATTENTION_THRESHOLD, TileMapQualityMetrics


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
        *processing.tileset_paths,
        processing.slices_path,
        processing.placement_path,
        processing.unity_manifest_path,
        processing.preview_path,
        *(path for path in (processing.quality_metrics_path, processing.seam_preview_path, processing.usage_preview_path) if path),
    )


def _sources(record: RawImageRecord | TileMapSourceSet, request: TileMapRequest) -> TileMapSourceSet:
    return load_tilemap_source_set(record.to_dict(), request) if isinstance(record, RawImageRecord) else record


def validate_tilemap_outputs(
    staging_dir: Path,
    request: TileMapRequest,
    record: RawImageRecord | TileMapSourceSet,
    processing: TileMapProcessingResult,
) -> QualityReport:
    Image = _load_pillow()
    sources = _sources(record, request)
    checks: list[QualityCheck] = []
    expected_pages = request.expected_atlas_sizes
    source_dimensions_ok = all((page.image.width, page.image.height) == expected_pages[page.atlas_id] for page in sources.pages)
    checks.append(_check(
        "tileset-pages",
        QualityStatus.PASSED if source_dimensions_ok and tuple(page.atlas_id for page in sources.pages) == tuple(expected_pages) else QualityStatus.FAILED,
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
        processing.preview_path: (request.map_width * request.tile_width, request.map_height * request.tile_height),
    }
    for page, path in zip(sources.pages, processing.tileset_paths):
        raster_sizes[path] = expected_pages[page.atlas_id]
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
        metrics = TileMapQualityMetrics.from_dict(load_json(staging_dir / processing.quality_metrics_path))
        metadata_valid = (
            len(slices["tiles"]) == len(request.tiles)
            and len(placement["layers"]) == len(request.layers)
            and unity["engine_target"] == "Unity_Tilemap"
            and unity["generated_root"].startswith("Assets/")
        )
    except (OSError, ValueError, TypeError, KeyError):
        metadata_valid = False
        metrics = None
    checks.append(_check(
        "unity-bundle-contract",
        QualityStatus.PASSED if metadata_valid else QualityStatus.FAILED,
        "Unity bundle metadata matches the request" if metadata_valid else "Unity bundle metadata is incomplete or inconsistent",
    ))

    if metrics is None:
        checks.extend((_check("tile-seams", QualityStatus.FAILED, "Tile quality metrics are missing"), _check("tile-clipping", QualityStatus.FAILED, "Tile quality metrics are missing"), _check("tile-usage", QualityStatus.FAILED, "Tile quality metrics are missing"), _check("tile-adjacency", QualityStatus.FAILED, "Tile quality metrics are missing")))
    else:
        checks.extend((
            _check("tile-seams", QualityStatus.NEEDS_ATTENTION if metrics.max_seam_score > SEAM_ATTENTION_THRESHOLD else QualityStatus.PASSED, "Tile seam threshold check", (processing.seam_preview_path,)),
            _check("tile-clipping", QualityStatus.NEEDS_ATTENTION if metrics.clipped_tile_ids else QualityStatus.PASSED, "Decoration and prop clipping check", metrics.clipped_tile_ids),
            _check("tile-usage", QualityStatus.NEEDS_ATTENTION if metrics.overused_decoration_ids else QualityStatus.PASSED, "Tile usage distribution check", metrics.overused_decoration_ids),
            _check("tile-adjacency", QualityStatus.NEEDS_ATTENTION if metrics.invalid_adjacencies else QualityStatus.PASSED, "Declared Tile adjacency check"),
        ))

    deterministic = QualityStatus.FAILED if any(item.status is QualityStatus.FAILED for item in checks) else QualityStatus.NEEDS_ATTENTION if any(item.status is QualityStatus.NEEDS_ATTENTION for item in checks) or processing.needs_attention else QualityStatus.PASSED
    visual = tuple(_check(check_id, QualityStatus.NEEDS_VISUAL_REVIEW, "manual visual review required") for check_id in TILEMAP_VISUAL_CHECK_IDS)
    return QualityReport(1, request.asset_id, sources.pages[0].image.request_fingerprint, deterministic, QualityStatus.NEEDS_VISUAL_REVIEW, tuple(checks), visual)


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
    record: RawImageRecord | TileMapSourceSet,
    processing: TileMapProcessingResult,
    report: QualityReport,
) -> AssetManifest:
    sources = _sources(record, request)
    roles = {
        processing.slices_path: "sprite-slices",
        processing.placement_path: "tilemap-placement",
        processing.unity_manifest_path: "unity-import-manifest",
        processing.preview_path: "tilemap-preview",
        processing.quality_metrics_path: "tilemap-quality-metrics",
        processing.seam_preview_path: "tile-seam-preview",
        processing.usage_preview_path: "tile-usage-preview",
    }
    roles.update({path: "tileset" for path in processing.tileset_paths})
    if (staging_dir / "map-quality-report.json").is_file():
        roles["map-quality-report.json"] = "map-quality-report"
    outputs = tuple(
        ArtifactRecord(role=roles[path], path=f"{request.output_dir}/{path}", sha256=sha256_file(staging_dir / PurePosixPath(path)))
        for path in _paths(processing)
    )
    source_artifacts = tuple(ArtifactRecord(role="source", path=page.image.path, sha256=page.image.sha256) for page in sources.pages)
    quality_status = "failed" if report.deterministic_status is QualityStatus.FAILED or report.visual_status is QualityStatus.FAILED else "passed" if report.deterministic_status is QualityStatus.PASSED and report.visual_status is QualityStatus.PASSED else "needs_attention"
    source = sources.pages[0].image
    return AssetManifest(1, request.asset_id, source.source_type.value, source.provider.value if source.provider else None, source.model, (*source_artifacts, *outputs), processing.processing_steps, quality_status)
