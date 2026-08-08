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
from game_visual_forge.quality.tilemap_objects import ObjectQualityMetrics, analyze_object_quality


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
        *(path for path in (processing.building_entrances_path,) if path),
        *(path for path in (processing.objects_path, processing.collision_path, processing.asset_set_path) if path),
        processing.preview_path,
        *(path for path in (processing.quality_metrics_path, processing.seam_preview_path, processing.usage_preview_path) if path),
        *(path for path in (processing.gameplay_crop_path, processing.collision_preview_path) if path),
        *(path for path in (processing.foundation_path, processing.foundation_prompt_path, processing.foundation_recomposition_path) if path),
        *(path for path in (processing.review_sheet_path,) if path),
    )


def _sources(record: RawImageRecord | TileMapSourceSet, request: TileMapRequest) -> TileMapSourceSet:
    return load_tilemap_source_set(record.to_dict(), request)


def _expected_building_entrances(request: TileMapRequest) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "map_id": request.asset_id,
        "coordinate_system": "top-left-grid",
        "transition_implementation": "out-of-scope",
        "entries": [entrance.to_dict() for entrance in request.building_entrances],
    }


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
            elif path.endswith(".txt"):
                if not target.read_text(encoding="utf-8").strip():
                    raise ValueError("text artifact must not be empty")
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
    if processing.gameplay_crop_path and request.gameplay_crop is not None:
        raster_sizes[processing.gameplay_crop_path] = (request.gameplay_crop.width * request.tile_width, request.gameplay_crop.height * request.tile_height)
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
    if request.tileset_profile.value == "coherent_foundation":
        foundation_match = False
        try:
            with Image.open(staging_dir / processing.foundation_path) as opened:
                foundation = opened.convert("RGBA")
            with Image.open(staging_dir / processing.foundation_recomposition_path) as opened:
                recomposition = opened.convert("RGBA")
            prompt_valid = bool((staging_dir / processing.foundation_prompt_path).read_text(encoding="utf-8").strip())
            foundation_match = foundation.size == recomposition.size and foundation.tobytes() == recomposition.tobytes() and prompt_valid
        except (OSError, ValueError, TypeError):
            foundation_match = False
        checks.append(_check(
            "foundation-recomposition",
            QualityStatus.PASSED if foundation_match else QualityStatus.FAILED,
            "Foundation slicing recomposes pixel-identically" if foundation_match else "Foundation slicing or prompt provenance is inconsistent",
            tuple(path for path in (processing.foundation_path, processing.foundation_prompt_path, processing.foundation_recomposition_path) if path),
        ))

    try:
        slices = load_json(staging_dir / processing.slices_path)
        placement = load_json(staging_dir / processing.placement_path)
        unity = load_json(staging_dir / processing.unity_manifest_path)
        metrics = TileMapQualityMetrics.from_dict(load_json(staging_dir / processing.quality_metrics_path))
        entrance_artifact_valid = True
        if processing.building_entrances_path:
            entrance_payload = load_json(staging_dir / processing.building_entrances_path)
            entrance_artifact_valid = entrance_payload == _expected_building_entrances(request)
        elif request.building_entrances:
            entrance_artifact_valid = False
        object_metadata_valid = True
        if processing.objects_path:
            object_metadata_valid = load_json(staging_dir / processing.objects_path).get("assets") is not None and load_json(staging_dir / processing.collision_path).get("blocked_cells") is not None
        metadata_valid = (
            len(slices["tiles"]) == len(request.tiles)
            and len(placement["layers"]) == len(request.layers)
            and unity["engine_target"] == "Unity_Tilemap"
            and unity["generated_root"].startswith("Assets/")
            and unity["tile_size_mode"] == request.tile_size_mode.value
            and unity["tile_width"] == request.tile_width
            and unity["tile_height"] == request.tile_height
            and unity["pixels_per_unit"] == request.pixels_per_unit
            and placement.get("bridge_connectivity_rules", []) == [rule.to_dict() for rule in request.bridge_connectivity_rules]
            and unity.get("bridge_connectivity_rules", []) == [rule.to_dict() for rule in request.bridge_connectivity_rules]
            and (not processing.building_entrances_path or unity.get("building_entrances") == processing.building_entrances_path)
            and entrance_artifact_valid
            and object_metadata_valid
        )
    except (OSError, ValueError, TypeError, KeyError):
        metadata_valid = False
        metrics = None
        entrance_artifact_valid = False
    checks.append(_check(
        "unity-bundle-contract",
        QualityStatus.PASSED if metadata_valid else QualityStatus.FAILED,
        "Unity bundle metadata matches the request" if metadata_valid else "Unity bundle metadata is incomplete or inconsistent",
    ))
    checks.append(_check(
        "building-entrances",
        QualityStatus.PASSED if entrance_artifact_valid else QualityStatus.FAILED,
        "Building entrance metadata matches the request" if entrance_artifact_valid else "Building entrance metadata is missing or inconsistent",
        (processing.building_entrances_path,) if processing.building_entrances_path else (),
    ))

    if metrics is None:
        checks.extend((_check("tile-seams", QualityStatus.FAILED, "Tile quality metrics are missing"), _check("tile-clipping", QualityStatus.FAILED, "Tile quality metrics are missing"), _check("tile-usage", QualityStatus.FAILED, "Tile quality metrics are missing"), _check("tile-adjacency", QualityStatus.FAILED, "Tile quality metrics are missing"), _check("bridge-connectivity", QualityStatus.FAILED, "Tile quality metrics are missing")))
    else:
        checks.extend((
            _check("tile-seams", QualityStatus.PASSED if request.tileset_profile.value == "coherent_foundation" and metrics.foundation_recomposition_match else QualityStatus.NEEDS_ATTENTION if metrics.max_seam_score > SEAM_ATTENTION_THRESHOLD else QualityStatus.PASSED, "Tile seam threshold check", (processing.seam_preview_path,)),
            _check("tile-clipping", QualityStatus.NEEDS_ATTENTION if metrics.clipped_tile_ids else QualityStatus.PASSED, "Decoration and prop clipping check", metrics.clipped_tile_ids),
            _check("tile-usage", QualityStatus.NEEDS_ATTENTION if metrics.overused_decoration_ids else QualityStatus.PASSED, "Tile usage distribution check", metrics.overused_decoration_ids),
            _check("tile-adjacency", QualityStatus.NEEDS_ATTENTION if metrics.invalid_adjacencies else QualityStatus.PASSED, "Declared Tile adjacency check"),
            _check(
                "bridge-connectivity",
                QualityStatus.FAILED if metrics.invalid_bridge_connectivity else QualityStatus.PASSED,
                "Declared bridge connectivity check" if not metrics.invalid_bridge_connectivity else "Bridge connectivity failures: " + "; ".join(
                    f"rule={item.rule_id} layer={item.layer_id} coord=({item.x},{item.y}) expected={item.expected_role} actual_tile={item.actual_tile_id or 'empty'} actual_role={item.actual_role or 'none'}"
                    for item in metrics.invalid_bridge_connectivity
                ),
                tuple(f"{item.layer_id}:{item.x},{item.y}" for item in metrics.invalid_bridge_connectivity),
            ),
        ))

    object_metrics = ObjectQualityMetrics()
    if request.object_assets:
        object_images = {}
        try:
            for asset in request.object_assets:
                with Image.open(staging_dir / "objects" / f"{asset.asset_id}.png") as image:
                    object_images[asset.asset_id] = image.convert("RGBA")
            object_metrics = analyze_object_quality(request, object_images)
        except (OSError, ValueError, KeyError):
            object_metrics = ObjectQualityMetrics(alpha_failures=tuple(asset.asset_id for asset in request.object_assets))
        checks.extend((
            _check("object-alpha", QualityStatus.FAILED if object_metrics.alpha_failures else QualityStatus.PASSED, "Object alpha and dimensions check", object_metrics.alpha_failures),
            _check("building-silhouette", QualityStatus.FAILED if object_metrics.silhouette_failures else QualityStatus.PASSED, "Building silhouette and duplication check", object_metrics.silhouette_failures),
            _check("object-overlap", QualityStatus.FAILED if object_metrics.overlap_failures else QualityStatus.PASSED, "Object collision overlap check", object_metrics.overlap_failures),
            _check("object-density", QualityStatus.FAILED if object_metrics.density_failures else QualityStatus.PASSED, "Object density and repeat limit check", object_metrics.density_failures),
            _check("entrance-reachability", QualityStatus.FAILED if object_metrics.entrance_failures else QualityStatus.PASSED, "Object entrance reachability check", object_metrics.entrance_failures),
            _check("road-connectivity", QualityStatus.FAILED if object_metrics.road_connectivity_failures else QualityStatus.PASSED, "Declared road connectivity policy check", object_metrics.road_connectivity_failures),
            _check("water-collision", QualityStatus.FAILED if object_metrics.water_collision_failures else QualityStatus.PASSED, "Water collision policy check", object_metrics.water_collision_failures),
            _check("bridge-traversal", QualityStatus.FAILED if object_metrics.bridge_traversal_failures else QualityStatus.PASSED, "Conditional bridge traversal check", object_metrics.bridge_traversal_failures),
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
        **(({processing.building_entrances_path: "building-entrances"} if processing.building_entrances_path else {})),
        processing.preview_path: "tilemap-preview",
        **({processing.review_sheet_path: "review-sheet"} if processing.review_sheet_path else {}),
        processing.quality_metrics_path: "tilemap-quality-metrics",
        processing.seam_preview_path: "tile-seam-preview",
        processing.usage_preview_path: "tile-usage-preview",
        **({processing.objects_path: "tilemap-objects", processing.collision_path: "tilemap-collision", processing.asset_set_path: "asset-set"} if processing.objects_path else {}),
    }
    roles.update({path: "tileset" for path in processing.tileset_paths})
    if processing.gameplay_crop_path:
        roles[processing.gameplay_crop_path] = "gameplay-crop"
    if processing.collision_preview_path:
        roles[processing.collision_preview_path] = "tilemap-collision-preview"
    if processing.foundation_path:
        roles[processing.foundation_path] = "foundation"
    if processing.foundation_prompt_path:
        roles[processing.foundation_prompt_path] = "foundation-prompt"
    if processing.foundation_recomposition_path:
        roles[processing.foundation_recomposition_path] = "foundation-recomposition"
    if (staging_dir / "map-quality-report.json").is_file():
        roles["map-quality-report.json"] = "map-quality-report"
    output_paths = (*_paths(processing), *(("map-quality-report.json",) if (staging_dir / "map-quality-report.json").is_file() else ()))
    outputs = tuple(
        ArtifactRecord(role=roles[path], path=f"{request.output_dir}/{path}", sha256=sha256_file(staging_dir / PurePosixPath(path)))
        for path in output_paths
    )
    source_artifacts = tuple(ArtifactRecord(role="source", path=page.image.path, sha256=page.image.sha256) for page in sources.pages)
    quality_status = "failed" if report.deterministic_status is QualityStatus.FAILED or report.visual_status is QualityStatus.FAILED else "passed" if report.deterministic_status is QualityStatus.PASSED and report.visual_status is QualityStatus.PASSED else "needs_attention"
    source = sources.pages[0].image
    return AssetManifest(1, request.asset_id, source.source_type.value, source.provider.value if source.provider else None, source.model, (*source_artifacts, *outputs), processing.processing_steps, quality_status)
