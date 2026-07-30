from __future__ import annotations

import importlib.util
import multiprocessing as mp
import os
import queue
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from game_visual_forge.contracts import (
    BackgroundRemoval,
    RembgRefinement,
    SpriteRequest,
)


@dataclass(frozen=True)
class BackgroundResult:
    image: Any
    method: str
    needs_attention: bool


DEFAULT_REMBG_MODEL = "birefnet-general"
DEFAULT_REMBG_PROVIDER_TIMEOUT_SECONDS = 120.0
DEFAULT_CHROMA_FALLBACK_TOLERANCE = 32
DEFAULT_REMBG_CHROMA_EDGE_RADIUS = 20
DEFAULT_REMBG_CHROMA_SOFT_DISTANCE = 0.5
MAX_REMBG_FAILURE_DETAIL_LENGTH = 240
REMBG_MODEL_ENV = "GAME_VISUAL_FORGE_REMBG_MODEL"
REMBG_PROVIDER_TIMEOUT_ENV = "GAME_VISUAL_FORGE_REMBG_PROVIDER_TIMEOUT_SECONDS"


@dataclass(frozen=True)
class DirectOnnxModelConfig:
    input_size: tuple[int, int]
    mean: tuple[float, float, float]
    std: tuple[float, float, float]
    apply_sigmoid: bool = False


DIRECT_ONNX_REMBG_MODELS = {
    "u2net": DirectOnnxModelConfig(
        input_size=(320, 320),
        mean=(0.485, 0.456, 0.406),
        std=(0.229, 0.224, 0.225),
    ),
    "u2netp": DirectOnnxModelConfig(
        input_size=(320, 320),
        mean=(0.485, 0.456, 0.406),
        std=(0.229, 0.224, 0.225),
    ),
    "isnet-anime": DirectOnnxModelConfig(
        input_size=(1024, 1024),
        mean=(0.485, 0.456, 0.406),
        std=(1.0, 1.0, 1.0),
    ),
    "birefnet-general": DirectOnnxModelConfig(
        input_size=(1024, 1024),
        mean=(0.485, 0.456, 0.406),
        std=(0.229, 0.224, 0.225),
        apply_sigmoid=True,
    ),
}


def remove_chroma(image: Any, color: str, *, tolerance: int = 0) -> Any:
    target = tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, alpha = pixels[x, y]
            distance = (
                (red - target[0]) ** 2
                + (green - target[1]) ** 2
                + (blue - target[2]) ** 2
            )
            pixels[x, y] = (red, green, blue, 0 if distance <= tolerance ** 2 else alpha)
    return rgba


def clean_rembg_chroma_residue(
    image: Any,
    color: str,
    *,
    tolerance: int = DEFAULT_CHROMA_FALLBACK_TOLERANCE,
    edge_radius: int = DEFAULT_REMBG_CHROMA_EDGE_RADIUS,
    soft_distance: float = DEFAULT_REMBG_CHROMA_SOFT_DISTANCE,
) -> Any:
    import numpy as np
    from PIL import Image, ImageFilter

    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    rgb = rgba[:, :, :3].astype(np.float32)
    alpha = rgba[:, :, 3].astype(np.float32)
    target = np.asarray(
        [int(color[index:index + 2], 16) for index in (1, 3, 5)],
        dtype=np.float32,
    )

    exact_distance = np.linalg.norm(rgb - target, axis=2)
    alpha[exact_distance <= tolerance] = 0

    target_range = float(np.max(target) - np.min(target))
    if edge_radius > 0 and soft_distance > 0 and target_range >= 128:
        transparent = Image.fromarray(
            np.where(alpha == 0, 255, 0).astype(np.uint8),
            mode="L",
        )
        nearby_transparency = np.asarray(
            transparent.filter(ImageFilter.MaxFilter(edge_radius * 2 + 1)),
            dtype=np.uint8,
        ) > 0

        pixel_scale = np.max(rgb, axis=2)
        target_scale = max(float(np.max(target)), 1.0)
        normalized_rgb = rgb / np.maximum(pixel_scale[:, :, None], 1.0)
        normalized_target = target / target_scale
        chroma_distance = np.linalg.norm(
            normalized_rgb - normalized_target,
            axis=2,
        )
        fringe = (
            nearby_transparency
            & (pixel_scale >= 16)
            & (chroma_distance < soft_distance)
        )
        alpha[fringe] *= np.clip(
            chroma_distance[fringe] / soft_distance,
            0,
            1,
        )

    rgba[:, :, 3] = np.where(alpha < 2, 0, np.rint(alpha)).astype(np.uint8)
    return Image.fromarray(rgba, mode="RGBA")


def _load_rembg() -> Any:
    return object() if importlib.util.find_spec("rembg") is not None else None


def _available_onnx_providers() -> tuple[str, ...]:
    try:
        import onnxruntime as ort
    except ImportError:
        return ()
    return tuple(str(provider) for provider in ort.get_available_providers())


def _rembg_provider_order() -> tuple[str, ...]:
    providers = []
    available = _available_onnx_providers()
    if "CUDAExecutionProvider" in available:
        providers.append("CUDAExecutionProvider")
    providers.append("CPUExecutionProvider")
    return tuple(providers)


def _rembg_model() -> str:
    return os.environ.get(REMBG_MODEL_ENV, DEFAULT_REMBG_MODEL)


def _rembg_provider_timeout_seconds() -> float:
    value = os.environ.get(REMBG_PROVIDER_TIMEOUT_ENV)
    if value is None:
        return DEFAULT_REMBG_PROVIDER_TIMEOUT_SECONDS
    try:
        timeout = float(value)
    except ValueError:
        return DEFAULT_REMBG_PROVIDER_TIMEOUT_SECONDS
    return timeout if timeout > 0 else DEFAULT_REMBG_PROVIDER_TIMEOUT_SECONDS


def _rembg_model_path(model: str) -> Path:
    configured_home = os.environ.get("U2NET_HOME")
    if configured_home is None:
        data_home = os.environ.get("XDG_DATA_HOME", "~")
        configured_home = os.path.join(data_home, ".u2net")
    return Path(configured_home).expanduser() / f"{model}.onnx"


def _remove_direct_onnx(image: Any, provider: str, model: str) -> tuple[Any, str]:
    import numpy as np
    import onnxruntime as ort
    from PIL import Image, ImageOps

    config = DIRECT_ONNX_REMBG_MODELS[model]
    model_path = _rembg_model_path(model)
    if not model_path.is_file():
        raise FileNotFoundError(
            f"rembg model is not cached at {model_path}; install/download model {model!r} first"
        )

    preload_dlls = getattr(ort, "preload_dlls", None)
    if callable(preload_dlls):
        preload_dlls(directory="")

    session_options = ort.SessionOptions()
    if provider != "CPUExecutionProvider":
        session_options.add_session_config_entry(
            "session.disable_cpu_ep_fallback",
            "1",
        )
    session = ort.InferenceSession(
        str(model_path),
        sess_options=session_options,
        providers=[provider],
        enable_fallback=False,
    )
    active_providers = tuple(str(item) for item in session.get_providers())
    if provider not in active_providers:
        raise RuntimeError(
            f"{provider} was requested but ONNX Runtime activated {active_providers!r}"
        )

    oriented = ImageOps.exif_transpose(image).convert("RGB")
    resized = np.asarray(
        oriented.resize(config.input_size, Image.Resampling.LANCZOS),
        dtype=np.float32,
    )
    resized /= max(float(np.max(resized)), 1e-6)
    normalized = np.empty_like(resized, dtype=np.float32)
    for channel in range(3):
        normalized[:, :, channel] = (
            resized[:, :, channel] - config.mean[channel]
        ) / config.std[channel]
    model_input = np.expand_dims(normalized.transpose((2, 0, 1)), 0)

    prediction = session.run(
        None,
        {session.get_inputs()[0].name: model_input},
    )[0][:, 0, :, :]
    if config.apply_sigmoid:
        prediction = 1 / (1 + np.exp(-prediction))
    minimum = float(np.min(prediction))
    maximum = float(np.max(prediction))
    if maximum <= minimum:
        raise RuntimeError("rembg model returned a constant alpha mask")
    prediction = np.squeeze((prediction - minimum) / (maximum - minimum))
    mask = Image.fromarray(
        (prediction.clip(0, 1) * 255).astype("uint8"),
        mode="L",
    ).resize(oriented.size, Image.Resampling.LANCZOS)
    transparent = Image.new("RGBA", oriented.size, 0)
    return Image.composite(oriented.convert("RGBA"), transparent, mask), provider


def _remove_with_rembg_package(
    image: Any,
    provider: str,
    model: str,
) -> tuple[Any, str]:
    from rembg import new_session, remove

    session = new_session(model, providers=[provider])
    active_providers = tuple(
        str(item) for item in session.inner_session.get_providers()
    )
    if provider not in active_providers:
        raise RuntimeError(
            f"{provider} was requested but rembg activated {active_providers!r}"
        )
    return remove(image, session=session).convert("RGBA"), provider


def _rembg_worker(input_png: bytes, provider: str, model: str, result_queue: Any) -> None:
    try:
        from PIL import Image

        image = Image.open(BytesIO(input_png)).convert("RGBA")
        if model in DIRECT_ONNX_REMBG_MODELS:
            result, active_provider = _remove_direct_onnx(image, provider, model)
        else:
            result, active_provider = _remove_with_rembg_package(
                image,
                provider,
                model,
            )
        output = BytesIO()
        result.convert("RGBA").save(output, format="PNG")
        result_queue.put(("ok", output.getvalue(), active_provider))
    except BaseException as exc:  # pragma: no cover - parent handles worker errors
        result_queue.put(("error", f"{type(exc).__name__}: {exc}", provider))


def _run_rembg_attempt(
    image: Any,
    provider: str,
    *,
    model: str,
    timeout_seconds: float,
) -> tuple[Any, str]:
    input_png = BytesIO()
    image.convert("RGBA").save(input_png, format="PNG")

    context = mp.get_context("spawn")
    result_queue = context.Queue(maxsize=1)
    process = context.Process(
        target=_rembg_worker,
        args=(input_png.getvalue(), provider, model, result_queue),
    )
    process.start()
    try:
        status, payload, active_provider = result_queue.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        if process.is_alive():
            process.terminate()
            process.join(5)
            raise TimeoutError(
                f"{provider} rembg attempt exceeded {timeout_seconds:g}s"
            ) from exc
        raise RuntimeError(
            f"{provider} rembg attempt exited without a result"
        ) from exc
    finally:
        result_queue.close()

    process.join(5)
    if process.is_alive():
        process.terminate()
        process.join(5)
    if status == "error":
        raise RuntimeError(str(payload))

    from PIL import Image

    return Image.open(BytesIO(payload)).convert("RGBA"), str(active_provider)


def _provider_label(provider: str) -> str:
    if provider == "CUDAExecutionProvider":
        return "cuda"
    if provider == "CPUExecutionProvider":
        return "cpu"
    return provider


def _failure_detail(label: str, exc: Exception) -> str:
    detail = " ".join(str(exc).split())
    if len(detail) > MAX_REMBG_FAILURE_DETAIL_LENGTH:
        detail = f"{detail[:MAX_REMBG_FAILURE_DETAIL_LENGTH - 3]}..."
    return f"{label}: {detail}"


def _remove_rembg_with_fallbacks(image: Any) -> BackgroundResult | None:
    if _load_rembg() is None:
        return None
    failures = []
    model = _rembg_model()
    timeout_seconds = _rembg_provider_timeout_seconds()
    for provider in _rembg_provider_order():
        label = _provider_label(provider)
        try:
            result, active_provider = _run_rembg_attempt(
                image,
                provider,
                model=model,
                timeout_seconds=timeout_seconds,
            )
            method = f"rembg-{model}-{_provider_label(active_provider)}"
            if failures:
                method = f"{method}-after-fallback ({'; '.join(failures)})"
            return BackgroundResult(
                result,
                method,
                False,
            )
        except Exception as exc:
            failures.append(_failure_detail(label, exc))
    return BackgroundResult(
        image.convert("RGBA"),
        f"rembg-{model}-failed ({'; '.join(failures)})",
        True,
    )


def _refine_rembg_result(
    source: Any,
    result: BackgroundResult,
    request: SpriteRequest,
) -> BackgroundResult:
    from game_visual_forge.processing.matting import (
        hybrid_chroma_fusion,
        reconstruct_known_background,
        refine_with_pymatting,
    )

    color = request.chroma_color
    if color is None:
        return result
    hybrid = hybrid_chroma_fusion(source, result.image, color)
    if request.rembg_refinement is RembgRefinement.PYMATTING:
        try:
            refined = refine_with_pymatting(source, hybrid, color)
        except Exception as exc:
            fallback = reconstruct_known_background(source, hybrid, color)
            return BackgroundResult(
                fallback,
                (
                    f"{result.method}+hybrid-known-background-after-"
                    f"{_failure_detail('pymatting', exc)}"
                ),
                True,
            )
        return BackgroundResult(
            refined,
            f"{result.method}+hybrid-pymatting",
            False,
        )
    return BackgroundResult(
        reconstruct_known_background(source, hybrid, color),
        f"{result.method}+hybrid-known-background",
        False,
    )


def remove_background(image: Any, request: SpriteRequest) -> BackgroundResult:
    if request.background_removal is BackgroundRemoval.REMBG:
        result = _remove_rembg_with_fallbacks(image)
        if result is not None and not result.needs_attention:
            if request.chroma_color is not None:
                try:
                    return _refine_rembg_result(image, result, request)
                except Exception as exc:
                    return BackgroundResult(
                        clean_rembg_chroma_residue(
                            result.image,
                            request.chroma_color,
                        ),
                        (
                            f"{result.method}+chroma-clean-after-"
                            f"{_failure_detail('refinement', exc)}"
                        ),
                        True,
                    )
            return result
        if request.chroma_color is not None:
            method = (
                "chroma-fallback"
                if result is None
                else f"chroma-fallback-after-{result.method}"
            )
            return BackgroundResult(
                remove_chroma(
                    image,
                    request.chroma_color,
                    tolerance=DEFAULT_CHROMA_FALLBACK_TOLERANCE,
                ),
                method,
                True,
            )
        if result is not None:
            return result
        return BackgroundResult(image.convert("RGBA"), "preserve-background", True)
    if request.background_removal is BackgroundRemoval.CHROMA:
        return BackgroundResult(
            remove_chroma(image, request.chroma_color or "#ff00ff"),
            "chroma",
            False,
        )
    return BackgroundResult(image.convert("RGBA"), "preserve-background", True)
