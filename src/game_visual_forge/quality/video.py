from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from game_visual_forge.contracts import ArtifactRecord, AssetManifest, QualityCheck, QualityStatus, VideoQualityReport, VideoMotionReview, VideoSpriteRequest, VideoSourceRecord
from game_visual_forge.processing.background import VIDEO_CHROMA_TOLERANCE
from game_visual_forge.processing.video_probe import sha256_file
from game_visual_forge.processing.video_review import calculate_temporal_metrics, validate_video_motion_review


MAX_VIDEO_CHROMA_RESIDUE_PERCENT = 1.0


def _check(check_id: str, status: QualityStatus, message: str, paths: tuple[str, ...] = ()) -> QualityCheck:
    return QualityCheck(check_id, status, message, paths)


def _load_delivery_frames(root: Path, processing: Any, density: int) -> tuple[Any, ...]:
    from PIL import Image
    directory = root / processing.artifacts[f"frames:{density}"]
    paths = sorted(directory.glob("frame-*.png"))
    frames = []
    for path in paths:
        with Image.open(path) as image:
            frames.append(image.convert("RGBA"))
    return tuple(frames)


def _delivery_frame_paths(root: Path, processing: Any) -> dict[int, tuple[Path, ...]]:
    result: dict[int, tuple[Path, ...]] = {}
    for role, relative in processing.artifacts.items():
        if not role.startswith("frames:"):
            continue
        density = int(role.split(":", 1)[1])
        result[density] = tuple(sorted((root / relative).glob("frame-*.png")))
    return result


def _visible_chroma_residue_percent(image: Any, color: str, *, tolerance: int = VIDEO_CHROMA_TOLERANCE) -> float:
    import numpy as np

    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    target = np.asarray([int(color[index:index + 2], 16) for index in (1, 3, 5)], dtype=np.int32)
    distance_squared = np.sum((rgba[:, :, :3].astype(np.int32) - target) ** 2, axis=2)
    visible = rgba[:, :, 3] >= 8
    visible_pixels = int(np.count_nonzero(visible))
    if visible_pixels == 0:
        return 0.0
    residue_pixels = int(np.count_nonzero(visible & (distance_squared <= int(tolerance) ** 2)))
    return round(100.0 * residue_pixels / visible_pixels, 4)


def assess_video_outputs(repo_root: Path, request: VideoSpriteRequest, source: VideoSourceRecord, processing: Any) -> VideoQualityReport:
    root = repo_root.resolve()
    checks: list[QualityCheck] = []
    source_path = root / source.path
    checks.append(_check("source-hash", QualityStatus.PASSED if source_path.is_file() and sha256_file(source_path) == source.sha256 else QualityStatus.FAILED, "source video hash matches"))
    highest = max(request.frame_counts)
    density_paths = _delivery_frame_paths(root, processing)
    expected_densities = set(request.frame_counts)
    frame_count_matches = set(density_paths) == expected_densities and all(
        len(density_paths[density]) == density for density in expected_densities
    )
    checks.append(_check("frame-count", QualityStatus.PASSED if frame_count_matches else QualityStatus.FAILED, "every requested density has the expected frame count"))
    frame_paths = list(density_paths.get(highest, ()))
    all_density_paths = tuple((density, path) for density in sorted(density_paths) for path in density_paths[density])
    readable = True
    sizes = set()
    for _, path in all_density_paths:
        try:
            from PIL import Image
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                sizes.add(image.size)
        except OSError:
            readable = False
    checks.append(_check("frame-readability", QualityStatus.PASSED if readable else QualityStatus.FAILED, "delivery frames are readable"))
    checks.append(_check("frame-dimensions", QualityStatus.PASSED if len(sizes) == 1 else QualityStatus.FAILED, "delivery frame dimensions are consistent across densities"))
    if request.background_mode.value != "preserve":
        opaque = False
        for _, path in all_density_paths:
            from PIL import Image
            with Image.open(path).convert("RGBA") as image:
                if image.getchannel("A").getextrema() == (255, 255):
                    opaque = True
        checks.append(_check("transparency", QualityStatus.FAILED if opaque else QualityStatus.PASSED, "transparent output is not fully opaque"))
    if request.background_mode.value == "chroma" and request.chroma_color is not None:
        residue_measurements: list[tuple[float, int, Path]] = []
        for density, path in all_density_paths:
            try:
                from PIL import Image
                with Image.open(path) as image:
                    residue_measurements.append((_visible_chroma_residue_percent(image, request.chroma_color), density, path))
            except OSError:
                continue
        maximum_residue, residue_density, residue_path = max(residue_measurements, default=(0.0, highest, Path("no-frame")))
        residue_status = QualityStatus.FAILED if maximum_residue > MAX_VIDEO_CHROMA_RESIDUE_PERCENT else QualityStatus.PASSED
        checks.append(_check("chroma-residue", residue_status, f"visible chroma residue is at most {MAX_VIDEO_CHROMA_RESIDUE_PERCENT:.1f}% (measured {maximum_residue:.4f}% at density {residue_density} {residue_path.name})"))
    deterministic = QualityStatus.FAILED if any(item.status is QualityStatus.FAILED for item in checks) else QualityStatus.PASSED
    frames = _load_delivery_frames(root, processing, highest) if frame_paths else ()
    metrics = calculate_temporal_metrics(frames) if frames else None
    temporal = QualityStatus.NEEDS_ATTENTION if metrics is not None and metrics.attention_reasons else QualityStatus.PASSED
    metric_dict = {} if metrics is None else {"frame_count": metrics.frame_count, "exact_duplicate_rate": metrics.exact_duplicate_rate, "near_duplicate_rate": metrics.near_duplicate_rate, "motion_coverage": metrics.motion_coverage, "static_intervals": list(metrics.static_intervals), "subject_bounds_variation": metrics.subject_bounds_variation, "anchor_jitter": metrics.anchor_jitter, "first_last_loop_difference": metrics.first_last_loop_difference, "alpha_coverage": metrics.alpha_coverage, "clipping_risk": metrics.clipping_risk, "frame_flicker": metrics.frame_flicker, "attention_reasons": list(metrics.attention_reasons)}
    metric_dict["layout_mode"] = request.layout_mode.value
    try:
        from game_visual_forge.contracts.serialization import load_json
        timing = load_json(root / processing.timing_path)
        metric_dict["reference_bounds"] = timing.get("reference_bounds")
    except (OSError, ValueError, KeyError):
        metric_dict["reference_bounds"] = None
    return VideoQualityReport(1, request.asset_id, source.request_fingerprint, deterministic, temporal, QualityStatus.NEEDS_VISUAL_REVIEW, tuple(checks), metric_dict, {})


def validate_reviewed_video_outputs(repo_root: Path, request: VideoSpriteRequest, source: VideoSourceRecord, processing: Any, review: VideoMotionReview, quality_report_path: Path, artifact_paths: dict[str, Path]) -> VideoQualityReport:
    report = assess_video_outputs(repo_root, request, source, processing)
    validate_video_motion_review(repo_root, review, quality_report_path, artifact_paths)
    if report.deterministic_status is QualityStatus.FAILED:
        return report
    return VideoQualityReport(1, report.asset_id, report.request_fingerprint, report.deterministic_status, report.temporal_status, QualityStatus.PASSED, report.deterministic_checks, report.temporal_metrics, review.checks, review.review_sha256)


def build_video_asset_manifest(repo_root: Path, request: VideoSpriteRequest, source: VideoSourceRecord, processing: Any, report: VideoQualityReport) -> AssetManifest:
    root = repo_root.resolve()
    artifacts = [ArtifactRecord("source-video", source.path, source.sha256)]
    staging_root = root / processing.staging_dir
    for role, path in sorted(processing.artifacts.items()):
        artifact_path = root / path
        if artifact_path.is_dir():
            for child in sorted(artifact_path.iterdir()):
                if child.is_file():
                    artifacts.append(ArtifactRecord(f"video-{role}", f"{request.output_dir}/{child.relative_to(staging_root).as_posix()}", sha256_file(child)))
        elif artifact_path.is_file():
            artifacts.append(ArtifactRecord(f"video-{role}", f"{request.output_dir}/{artifact_path.relative_to(staging_root).as_posix()}", sha256_file(artifact_path)))
    quality_path = root / processing.staging_dir / "video-quality-report.json"
    if quality_path.is_file():
        artifacts.append(ArtifactRecord("video-quality-report", f"{request.output_dir}/video-quality-report.json", sha256_file(quality_path)))
    return AssetManifest(1, request.asset_id, request.source_preference.value if request.source_preference else "existing-file", source.provider.value if source.provider else None, source.model, tuple(artifacts), ("verify-source", "sample-by-timestamp", "cleanup", "align-bottom-center", "normalize-delivery", "validate-video-quality"), "passed" if report.deterministic_status is QualityStatus.PASSED and report.visual_status is QualityStatus.PASSED else "failed" if report.deterministic_status is QualityStatus.FAILED or report.visual_status is QualityStatus.FAILED else "needs_attention", {"processing_mode": request.processing_mode.value, "anchor": request.anchor.value, "fit_scale": request.fit_scale})


def publish_video_outputs(staging_dir: Path, final_dir: Path, report: VideoQualityReport, manifest: AssetManifest) -> bool:
    if report.deterministic_status is QualityStatus.FAILED or report.visual_status is not QualityStatus.PASSED:
        return False
    from game_visual_forge.contracts.serialization import dump_json
    dump_json(staging_dir / "asset-manifest.json", manifest.to_dict())
    if final_dir.exists():
        raise ValueError("final output directory already exists")
    os.replace(staging_dir, final_dir)
    return True
