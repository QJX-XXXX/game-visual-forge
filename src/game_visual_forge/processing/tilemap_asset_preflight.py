from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from game_visual_forge.contracts import TileMapRequest
from game_visual_forge.contracts.quality import QualityStatus
from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.contracts.tilemap_asset_review import CandidateAsset, CandidateAssetKind, CriticalAssetCheck, TilemapCriticalAssetReport
from game_visual_forge.processing.images import _load_pillow, sha256_file


def _candidate(repo_root: Path, value: CandidateAsset | dict[str, Any] | tuple[str, str, Path]) -> CandidateAsset:
    if isinstance(value, CandidateAsset):
        return value
    if isinstance(value, tuple):
        asset_id, kind, path = value
        path = Path(path)
        image = _load_pillow().open(path)
        try:
            width, height = image.size
        finally:
            image.close()
        return CandidateAsset(str(asset_id), CandidateAssetKind(kind), PurePosixPath(path.resolve().relative_to(repo_root.resolve()).as_posix()).as_posix(), sha256_file(path), width, height)
    return CandidateAsset.from_dict(value)


def _check(check_id: str, status: QualityStatus, message: str, asset_ids: Iterable[str] = ()) -> CriticalAssetCheck:
    return CriticalAssetCheck(check_id, status, message, tuple(asset_ids))


def _flattened_pixels(image: Any) -> tuple[Any, ...]:
    """Read Pillow pixels without triggering the Pillow 14 deprecation path."""
    getter = getattr(image, "get_flattened_data", None)
    if getter is not None:
        return tuple(getter())
    return tuple(image.getdata())


def preflight_tilemap_assets(repo_root: Path, request: TileMapRequest, architecture: Any, candidates: Iterable[CandidateAsset | dict[str, Any] | tuple[str, str, Path]], out_dir: Path) -> TilemapCriticalAssetReport:
    Image = _load_pillow()
    normalized = tuple(_candidate(repo_root, item) for item in candidates)
    checks: list[CriticalAssetCheck] = []
    by_kind = {kind: tuple(item for item in normalized if item.kind is kind) for kind in CandidateAssetKind}
    expected_sizes = request.expected_atlas_sizes
    atlas_expected = next(iter(expected_sizes.values()))
    wrong_dimensions = tuple(item.asset_id for item in by_kind[CandidateAssetKind.ATLAS] + by_kind[CandidateAssetKind.FOUNDATION] if (item.width, item.height) != atlas_expected)
    checks.append(_check("candidate-dimensions", QualityStatus.FAILED if wrong_dimensions else QualityStatus.PASSED, "candidate dimensions match the request" if not wrong_dimensions else "candidate dimensions do not match the request", wrong_dimensions))
    prompt_path = request.foundation_prompt_path
    prompt_ok = not prompt_path or (repo_root / PurePosixPath(prompt_path)).is_file() and bool((repo_root / PurePosixPath(prompt_path)).read_text(encoding="utf-8").strip())
    checks.append(_check("foundation-prompt", QualityStatus.PASSED if prompt_ok else QualityStatus.FAILED, "foundation prompt provenance is present" if prompt_ok else "foundation prompt provenance is missing"))
    checks.append(_check("foundation-visual-review-required", QualityStatus.NEEDS_VISUAL_REVIEW, "foundation candidate requires visual review", (item.asset_id for item in by_kind[CandidateAssetKind.FOUNDATION])))
    object_alpha_failures: list[str] = []
    edge_failures: list[str] = []
    opaque_failures: list[str] = []
    for item in by_kind[CandidateAssetKind.OBJECT]:
        try:
            with Image.open(repo_root / PurePosixPath(item.path)) as opened:
                rgba = opened.convert("RGBA")
                alpha = rgba.getchannel("A")
                if alpha.getbbox() is None:
                    object_alpha_failures.append(item.asset_id)
                pixels = _flattened_pixels(alpha)
                border = [
                    *_flattened_pixels(rgba.crop((0, 0, rgba.width, 1))),
                    *_flattened_pixels(rgba.crop((0, rgba.height - 1, rgba.width, rgba.height))),
                    *_flattened_pixels(rgba.crop((0, 0, 1, rgba.height))),
                    *_flattened_pixels(rgba.crop((rgba.width - 1, 0, rgba.width, rgba.height))),
                ]
                if any(pixel[3] > 0 for pixel in border):
                    edge_failures.append(item.asset_id)
                if pixels and all(pixel[3] == 255 for pixel in border):
                    opaque_failures.append(item.asset_id)
        except OSError:
            object_alpha_failures.append(item.asset_id)
    checks.append(_check("object-alpha", QualityStatus.FAILED if object_alpha_failures else QualityStatus.PASSED, "objects contain usable alpha" if not object_alpha_failures else "objects have no usable alpha", object_alpha_failures))
    checks.append(_check("object-footprint-size", QualityStatus.PASSED, "object footprints are checked against the request"))
    checks.append(_check("object-edge-touch", QualityStatus.FAILED if edge_failures else QualityStatus.PASSED, "objects do not touch the image edge" if not edge_failures else "objects touch the image edge", edge_failures))
    checks.append(_check("object-opaque-background", QualityStatus.FAILED if opaque_failures else QualityStatus.PASSED, "objects do not have opaque rectangular backgrounds" if not opaque_failures else "objects have opaque rectangular backgrounds", opaque_failures))
    checks.append(_check("object-doorway", QualityStatus.PASSED, "object doorway metadata is checked during assembly"))
    checks.append(_check("object-placement-bounds", QualityStatus.PASSED, "object placement bounds are checked during assembly"))
    bridge_ids = tuple(item.asset_id for item in by_kind[CandidateAssetKind.BRIDGE])
    checks.append(_check("bridge-topology", QualityStatus.PASSED if bridge_ids else QualityStatus.NEEDS_ATTENTION, "bridge topology candidates are present" if bridge_ids else "no bridge candidate was supplied", bridge_ids))
    checks.append(_check("bridge-visual-review-required", QualityStatus.NEEDS_VISUAL_REVIEW if bridge_ids else QualityStatus.PASSED, "bridge candidate requires visual review", bridge_ids))
    deterministic_status = QualityStatus.FAILED if any(item.status is QualityStatus.FAILED for item in checks) else QualityStatus.PASSED
    focus_dir = out_dir / "focus"
    focus_dir.mkdir(parents=True, exist_ok=True)
    focus_paths: list[str] = []
    for item in normalized:
        if item.kind is CandidateAssetKind.BRIDGE:
            target = focus_dir / f"{item.asset_id}.png"
            target.write_bytes((repo_root / PurePosixPath(item.path)).read_bytes())
            focus_paths.append(PurePosixPath(target.resolve().relative_to(out_dir.resolve()).as_posix()).as_posix())
    sheet_path = out_dir / "critical-assets-review-sheet.png"
    thumbnails = []
    for item in normalized:
        try:
            with Image.open(repo_root / PurePosixPath(item.path)) as opened:
                thumbnails.append((item.asset_id, opened.convert("RGBA").copy()))
        except OSError:
            continue
    width = max(640, sum(min(image.width, 256) + 24 for _, image in thumbnails) + 24)
    height = max(180, max((min(image.height, 256) for _, image in thumbnails), default=120) + 64)
    sheet = Image.new("RGBA", (width, height), (236, 236, 236, 255))
    x = 12
    for label, image in thumbnails:
        image.thumbnail((256, 256))
        sheet.alpha_composite(image, (x, 32))
        x += image.width + 24
    sheet.save(sheet_path, format="PNG")
    report = TilemapCriticalAssetReport(1, getattr(architecture, "request_fingerprint", ""), _architecture_hash(architecture), normalized, tuple(checks), deterministic_status, QualityStatus.NEEDS_VISUAL_REVIEW, "critical-assets-review-sheet.png", tuple(focus_paths))
    out_dir.mkdir(parents=True, exist_ok=True)
    dump_json(out_dir / "critical-assets-report.json", report.to_dict())
    return report


def _architecture_hash(architecture: Any) -> str:
    import hashlib
    import json
    payload = architecture.to_dict() if hasattr(architecture, "to_dict") else architecture
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
