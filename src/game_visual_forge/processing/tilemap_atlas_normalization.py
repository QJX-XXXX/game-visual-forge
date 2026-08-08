from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from game_visual_forge.contracts import (
    AtlasNormalizationPageRecord,
    AtlasNormalizationReport,
    AtlasNormalizationStatus,
    MapSourceDecision,
    MapSourceType,
    TileMapRequest,
)
from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.jobs import fingerprint_request
from game_visual_forge.processing.images import _load_pillow, sha256_file


_ASPECT_TOLERANCE = 0.01


def _inside(root: Path, path: Path, field_name: str) -> Path:
    root = root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{field_name} must remain inside repo_root") from exc
    return resolved


def _relative(root: Path, path: Path) -> str:
    return PurePosixPath(path.resolve().relative_to(root.resolve()).as_posix()).as_posix()


def _cell_edges(length: int, count: int) -> tuple[int, ...]:
    return tuple(round(index * length / count) for index in range(count + 1))


def _target_size(request: TileMapRequest, page_id: str) -> tuple[int, int]:
    page = next(page for page in request.resolved_atlas_pages if page.atlas_id == page_id)
    return (
        request.atlas_margin * 2 + page.columns * page.tile_width + (page.columns - 1) * request.atlas_spacing,
        request.atlas_margin * 2 + page.rows * page.tile_height + (page.rows - 1) * request.atlas_spacing,
    )


def _relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(abs(right), 1e-9)


def _resampling_name(request: TileMapRequest) -> str:
    return "nearest" if request.filter_mode.value == "point" else "lanczos"


def _resampling(Image: Any, name: str) -> Any:
    return Image.Resampling.NEAREST if name == "nearest" else Image.Resampling.LANCZOS


def _validate_source_geometry(image: Any, page: Any) -> tuple[tuple[int, ...], tuple[int, ...]]:
    x_edges = _cell_edges(image.width, page.columns)
    y_edges = _cell_edges(image.height, page.rows)
    source_aspect = (image.width / page.columns) / (image.height / page.rows)
    target_aspect = page.tile_width / page.tile_height
    if _relative_difference(source_aspect, target_aspect) > _ASPECT_TOLERANCE:
        raise ValueError(
            f"atlas {page.atlas_id} source grid aspect ratio {source_aspect:.6f} "
            f"does not match target Tile aspect ratio {target_aspect:.6f}"
        )
    for row in range(page.rows):
        if y_edges[row + 1] - y_edges[row] < page.tile_height:
            raise ValueError(f"atlas {page.atlas_id} source cell height is smaller than target Tile height")
    for column in range(page.columns):
        if x_edges[column + 1] - x_edges[column] < page.tile_width:
            raise ValueError(f"atlas {page.atlas_id} source cell width is smaller than target Tile width")
    return x_edges, y_edges


def normalize_tilemap_atlases(
    repo_root: Path,
    request: TileMapRequest,
    decision: MapSourceDecision,
    atlas_pages: tuple[tuple[str, Path], ...],
    out_dir: Path,
    *,
    allow_non_native: bool = False,
) -> AtlasNormalizationReport:
    if request.tileset_profile.value == "coherent_foundation":
        raise ValueError("coherent_foundation atlas pages must not be normalized")
    expected_fingerprint = fingerprint_request(request.to_dict())
    if decision.request_fingerprint != expected_fingerprint:
        raise ValueError("source decision does not match tilemap request")
    if decision.source_type is None:
        raise ValueError("source decision has no source type")
    if decision.source_type is not MapSourceType.AGENT_NATIVE and not allow_non_native:
        raise ValueError("automatic atlas normalization requires agent-native source; pass --allow-non-native for explicit use")

    expected_ids = tuple(page.atlas_id for page in request.resolved_atlas_pages)
    actual_ids = tuple(atlas_id for atlas_id, _ in atlas_pages)
    if actual_ids != expected_ids:
        raise ValueError(f"atlas pages must match request order: expected {expected_ids}, got {actual_ids}")
    root = repo_root.resolve()
    out_dir = _inside(root, out_dir, "out_dir")
    out_dir.mkdir(parents=True, exist_ok=True)
    pages_by_id = {page.atlas_id: page for page in request.resolved_atlas_pages}
    Image = _load_pillow()
    resampling_name = _resampling_name(request)
    records: list[AtlasNormalizationPageRecord] = []

    for atlas_id, raw_path in atlas_pages:
        page = pages_by_id[atlas_id]
        source_path = _inside(root, raw_path, f"source path for {atlas_id}")
        source_digest = sha256_file(source_path)
        with Image.open(source_path) as opened:
            image = opened.convert("RGBA")
        expected_size = _target_size(request, atlas_id)
        if image.size == expected_size:
            records.append(
                AtlasNormalizationPageRecord(
                    atlas_id,
                    AtlasNormalizationStatus.NOT_REQUIRED,
                    _relative(root, source_path),
                    source_digest,
                    image.width,
                    image.height,
                    page.columns,
                    page.rows,
                    page.tile_width,
                    page.tile_height,
                    request.atlas_margin,
                    request.atlas_spacing,
                    "none",
                    _relative(root, source_path),
                    source_digest,
                    image.width,
                    image.height,
                )
            )
            continue

        x_edges, y_edges = _validate_source_geometry(image, page)
        normalized = Image.new("RGBA", expected_size, (0, 0, 0, 0))
        sampler = _resampling(Image, resampling_name)
        for row in range(page.rows):
            for column in range(page.columns):
                cell = image.crop((x_edges[column], y_edges[row], x_edges[column + 1], y_edges[row + 1]))
                cell = cell.resize((page.tile_width, page.tile_height), resample=sampler)
                left = request.atlas_margin + column * (page.tile_width + request.atlas_spacing)
                top = request.atlas_margin + row * (page.tile_height + request.atlas_spacing)
                normalized.paste(cell, (left, top))
        output_path = _inside(root, out_dir / f"{atlas_id}.png", f"output path for {atlas_id}")
        if output_path == source_path:
            raise ValueError(f"atlas {atlas_id} normalization output must not overwrite its source")
        normalized.save(output_path, format="PNG")
        output_digest = sha256_file(output_path)
        records.append(
            AtlasNormalizationPageRecord(
                atlas_id,
                AtlasNormalizationStatus.NORMALIZED,
                _relative(root, source_path),
                source_digest,
                image.width,
                image.height,
                page.columns,
                page.rows,
                page.tile_width,
                page.tile_height,
                request.atlas_margin,
                request.atlas_spacing,
                resampling_name,
                _relative(root, output_path),
                output_digest,
                normalized.width,
                normalized.height,
            )
        )

    status = AtlasNormalizationStatus.NOT_REQUIRED if all(item.status is AtlasNormalizationStatus.NOT_REQUIRED for item in records) else AtlasNormalizationStatus.NORMALIZED
    report = AtlasNormalizationReport(1, expected_fingerprint, decision.source_type, status, tuple(records))
    dump_json(out_dir / "atlas-normalization-report.json", report.to_dict())
    return report


def validate_atlas_normalization_report(
    repo_root: Path,
    request: TileMapRequest,
    decision: MapSourceDecision,
    report: AtlasNormalizationReport,
    atlas_pages: tuple[tuple[str, Path], ...],
    *,
    allow_non_native: bool = False,
) -> None:
    if request.tileset_profile.value == "coherent_foundation":
        raise ValueError("coherent_foundation atlas pages must not be normalized")
    expected_fingerprint = fingerprint_request(request.to_dict())
    if report.request_fingerprint != expected_fingerprint or decision.request_fingerprint != expected_fingerprint:
        raise ValueError("atlas normalization report does not match tilemap request")
    if report.source_type is not decision.source_type:
        raise ValueError("atlas normalization report does not match source decision")
    if decision.source_type is not MapSourceType.AGENT_NATIVE and not allow_non_native:
        raise ValueError("non-native atlas normalization requires explicit opt-in")
    expected_ids = tuple(page.atlas_id for page in request.resolved_atlas_pages)
    actual_ids = tuple(atlas_id for atlas_id, _ in atlas_pages)
    report_ids = tuple(page.atlas_id for page in report.pages)
    if actual_ids != expected_ids or report_ids != expected_ids:
        raise ValueError("atlas normalization pages must match request order")
    root = repo_root.resolve()
    page_defs = {page.atlas_id: page for page in request.resolved_atlas_pages}
    for (atlas_id, supplied_path), record in zip(atlas_pages, report.pages):
        page = page_defs[atlas_id]
        source_path = _inside(root, supplied_path, f"source path for {atlas_id}")
        output_path = _inside(root, root / PurePosixPath(record.output_path), f"output path for {atlas_id}")
        if _relative(root, source_path) != record.output_path:
            raise ValueError(f"atlas {atlas_id} candidate must use normalized output path")
        if record.columns != page.columns or record.rows != page.rows or record.tile_width != page.tile_width or record.tile_height != page.tile_height:
            raise ValueError(f"atlas {atlas_id} normalization geometry does not match request")
        if sha256_file(output_path) != record.output_sha256:
            raise ValueError(f"atlas {atlas_id} normalized output hash changed")
        with _load_pillow().open(output_path) as opened:
            if opened.size != _target_size(request, atlas_id):
                raise ValueError(f"atlas {atlas_id} normalized output dimensions do not match request")
        source_path_from_report = _inside(root, root / PurePosixPath(record.source_path), f"source path for {atlas_id}")
        if sha256_file(source_path_from_report) != record.source_sha256:
            raise ValueError(f"atlas {atlas_id} source hash changed")
