"""Backend-specific execution for the existing MiniMax and Jimeng video routes."""
from __future__ import annotations

import re
import shutil
import urllib.request
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from game_visual_forge.contracts import ExternalProvider, VideoGenerationMode, VideoModelCatalogSnapshot, VideoModelProfile
from game_visual_forge.contracts.video_provider import VideoProviderBackend
from .image_http import ImageApiError
from .mcp_client import McpClient, tool_result, validate_tool
from .tool_runtime import execution_config, require_help_flags, run_tool, tool_preflight


def _config(provider, payload):
    parameters = payload.get("parameters", {})
    execution = parameters.get("execution")
    if execution is None:
        execution = {"backend": payload["backend"]}
        if payload.get("executable"):
            execution["command"] = [str(payload["executable"])]
    config = execution_config(provider, execution)
    if config["backend"] != payload["backend"]:
        raise ValueError("video execution backend differs from confirmed backend")
    return config


def _minimax_region_arguments(region):
    if region not in {"cn", "global"}:
        raise ValueError("MiniMax region must be cn or global")
    return ["--region", region, "--base-url", "https://api.minimax.cn" if region == "cn" else "https://api.minimax.io"]


def _models(provider, backend, region):
    provider_enum = ExternalProvider(provider)
    backend_enum = VideoProviderBackend(backend)
    if provider == "minimax" and backend == "cli":
        from .minimax_video import _h3_profile
        models = (replace(_h3_profile(), supported_backends=(backend_enum,)),)
    else:
        if provider == "minimax":
            model, durations, resolutions = "MiniMax-Hailuo-02", (6, 10), ("768P", "1080P")
        else:
            model, durations, resolutions = "dreamina-default", (), ()
        models = (VideoModelProfile(1, provider_enum, model, "tool", "generate_video" if backend == "mcp" else "dreamina", (VideoGenerationMode.T2V, VideoGenerationMode.I2V_FIRST), ("first_frame",), durations, resolutions, (), False, (backend_enum,), "2026-11-17"),)
    return VideoModelCatalogSnapshot.create(provider=provider_enum, backend=backend_enum, region=region, refreshed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), adapter_version="2.0", models=models, source="official-" + backend)


def _arguments(provider, payload, config):
    parameters = payload.get("parameters", {})
    model = payload["model"]
    mode = VideoGenerationMode(payload.get("mode", parameters.get("generation_mode", "t2v")))
    prompt = parameters.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("video prompt is required")
    if provider == "minimax" and config["backend"] == "cli":
        from .minimax_video import _prepared_submit_request
        if model != "MiniMax-H3":
            raise ValueError("MiniMax CLI supports MiniMax-H3 for V2. Select the API for other H3 models.")
        _prepared_submit_request(model, mode, parameters)
        if parameters.get("extra") or parameters.get("aigc_watermark"):
            raise ValueError("these H3 options require API execution")
        args = ["video", "generate", "--model", model, "--prompt", prompt, "--async", "--quiet", "--output", "json", *_minimax_region_arguments(payload.get("region", "global"))]
        single = {"first_frame_path": "image", "first_frame_url": "image", "last_frame_url": "last-frame", "duration": "duration", "resolution": "resolution", "ratio": "ratio"}
        for key, flag in single.items():
            if key in parameters:
                args.extend(["--" + flag, str(parameters[key])])
        for key, flag in (("reference_image_urls", "reference-image"), ("reference_video_urls", "reference-video"), ("reference_audio_urls", "reference-audio")):
            for value in parameters.get(key, []):
                args.extend(["--" + flag, value])
        return args
    if mode not in {VideoGenerationMode.T2V, VideoGenerationMode.I2V_FIRST}:
        raise ValueError("this tool supports t2v and i2v-first")
    first = parameters.get("first_frame_url") or parameters.get("first_frame_path")
    if bool(first) != (mode is VideoGenerationMode.I2V_FIRST):
        raise ValueError("video mode and first-frame input differ")
    if provider == "minimax":
        if model != "MiniMax-Hailuo-02":
            raise ValueError("selected model has no verified official video MCP profile")
        duration = parameters.get("duration", 6)
        resolution = parameters.get("resolution", "768P")
        if duration not in {6, 10} or resolution not in {"768P", "1080P"} or (duration == 10 and resolution == "1080P"):
            raise ValueError("unsupported Hailuo-02 duration/resolution combination")
        result = {"model": model, "prompt": prompt, "async_mode": True, "duration": duration, "resolution": resolution}
        if first:
            if parameters.get("first_frame_path"):
                from .minimax_video import _verified_png_data_uri
                first = _verified_png_data_uri(first, parameters.get("first_frame_sha256"))
            result["first_frame_image"] = first
        if set(parameters) - {"prompt", "generation_mode", "first_frame_url", "first_frame_path", "first_frame_sha256", "duration", "resolution", "reference_sha256", "execution"}:
            raise ValueError("unsupported official MiniMax video MCP parameters")
        return result
    if model != "dreamina-default":
        raise ValueError("Dreamina model selection requires its runtime help; use the default profile")
    command = "image2video" if first else "text2video"
    args = [command, "--prompt=" + prompt]
    if first:
        args.extend(["--image", first])
    for key in ("duration", "ratio"):
        if key in parameters:
            args.append("--" + key + "=" + str(parameters[key]))
    if set(parameters) - {"prompt", "generation_mode", "first_frame_url", "first_frame_path", "first_frame_sha256", "duration", "ratio", "reference_sha256", "execution"}:
        raise ValueError("unsupported Dreamina video parameters")
    if parameters.get("first_frame_path"):
        from .minimax_video import _verified_png_data_uri
        _verified_png_data_uri(first, parameters.get("first_frame_sha256"))
    require_help_flags(config, command, args)
    return args


def _mcp(config, region):
    if region not in {"cn", "global"}:
        raise ValueError("MiniMax region must be cn or global")
    return McpClient(config, environment={"MINIMAX_API_HOST": "https://api.minimaxi.com" if region == "cn" else "https://api.minimax.io", "MINIMAX_API_RESOURCE_MODE": "url"})


def _query(provider, payload, config):
    task_id = payload["external_task_id"]
    if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", task_id):
        raise ValueError("invalid video task ID")
    if config["backend"] == "mcp":
        text = tool_result(_mcp(config, payload.get("region", "global")).call("query_video_generation", {"task_id": task_id})).get("text", "")
        if text.startswith("Success. Video URL: "):
            return {"status": "completed", "url": text[len("Success. Video URL: "):].strip()}
        if text.startswith("Video generation FAILED"):
            return {"status": "failed"}
        if text.startswith("Video generation task is still processing: "):
            return {"status": "running"}
        raise ImageApiError("invalid_minimax_mcp_video_status")
    if provider == "minimax":
        arguments = ["video", "task", "get", "--task-id", task_id, "--model", payload["model"], *_minimax_region_arguments(payload.get("region", "global")), "--output", "json"]
        result = run_tool(config, arguments)
        status = str(result.get("status", "")).lower()
        if status in {"success", "succeeded", "completed"}:
            return {"status": "completed", "url": result.get("url"), "file_id": result.get("file_id")}
        if status in {"fail", "failed"}:
            return {"status": "failed"}
        if status in {"cancelled", "canceled", "expired"}:
            return {"status": status}
        if status not in {"preparing", "queueing", "processing", "running", "queued", "submitted", "pending", "in_progress"}:
            raise ImageApiError("invalid_minimax_cli_video_status")
        return {"status": "running"}
    result = run_tool(config, ["query_result", "--submit_id=" + task_id])
    status = result.get("gen_status")
    if status not in {"success", "fail", "querying"}:
        raise ImageApiError("invalid_dreamina_video_status")
    return {"status": {"success": "completed", "fail": "failed", "querying": "running"}[status]}


def _download_url(url, target):
    if not isinstance(url, str) or not url.startswith("https://"):
        raise ValueError("completed video requires a provider HTTPS download URL")
    with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as output:
        remaining = 512 * 1024 * 1024
        while True:
            chunk = response.read(min(1024 * 1024, remaining + 1))
            if not chunk:
                break
            remaining -= len(chunk)
            if remaining < 0:
                raise ValueError("video exceeds the 512 MiB tool download limit")
            output.write(chunk)


def run_video_tool(provider, command, payload):
    config = _config(provider, payload)
    backend = config["backend"]
    if provider == "jimeng" and backend == "mcp":
        raise ValueError("use the project Jimeng MCP bridge workflow tools with a CLI or API attempt")
    result = {"schema_version": 1, "provider": provider, "backend": backend}
    region = payload.get("region", "global" if provider == "minimax" else "cn")
    if command == "capabilities":
        return {**result, "operations": ["capabilities", "models", "preflight", "estimate", "prepare", "submit", "query", "download"]}
    if command == "models":
        return _models(provider, backend, region).to_dict()
    if command == "preflight":
        readiness = tool_preflight(provider, config)
        if readiness["available"] and payload.get("model"):
            arguments = _arguments(provider, payload, config)
            if backend == "mcp":
                validate_tool(_mcp(config, region).tools(), "generate_video", arguments)
        return readiness
    if command == "estimate":
        return {**result, "currency": None, "amount": None, "verified": False, "notice": "verify total cost in the selected tool account before paid confirmation"}
    if command == "prepare":
        snapshot = VideoModelCatalogSnapshot.from_dict(payload["snapshot"])
        if snapshot.provider.value != provider or snapshot.backend.value != backend or snapshot.region != region:
            raise ValueError("video snapshot and selected execution route differ")
        profile = snapshot.model(payload["model"])
        mode = VideoGenerationMode(payload["mode"])
        if mode not in profile.supported_modes:
            raise ValueError("video model does not support this mode")
        _arguments(provider, payload, config)
        parameters = dict(payload.get("parameters", {}))
        parameters["execution"] = config
        parameters["generation_mode"] = mode.value
        return {**result, "region": region, "model": profile.model, "mode": mode.value, "parameters": parameters, "endpoint": profile.endpoint}
    if command == "submit":
        arguments = _arguments(provider, payload, config)
        if backend == "mcp":
            text = tool_result(_mcp(config, region).call("generate_video", arguments)).get("text", "")
            match = re.search(r"Task ID: ([A-Za-z0-9_.:-]+)\. Please use", text)
            task_id = match.group(1) if match else None
        else:
            receipt = run_tool(config, arguments)
            task_id = receipt.get("taskId") if provider == "minimax" else receipt.get("submit_id")
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", task_id):
            raise ImageApiError("missing_tool_video_task_id")
        return {**result, "status": "submitted", "external_task_id": task_id}
    if command == "query":
        receipt = _query(provider, payload, config)
        return {**result, "external_task_id": payload["external_task_id"], "status": receipt["status"]}
    if command == "download":
        receipt = _query(provider, payload, config)
        if receipt["status"] != "completed":
            raise ValueError("video generation is incomplete")
        target = Path(payload["output_path"]).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        if provider == "jimeng":
            directory = target.parent / (payload["external_task_id"] + "-dreamina")
            directory.mkdir(exist_ok=True)
            run_tool(config, ["query_result", "--submit_id=" + payload["external_task_id"], "--download_dir=" + str(directory)])
            paths = sorted(directory.glob("*.mp4"))
            if len(paths) != 1:
                raise ValueError("Dreamina download must produce exactly one MP4")
            paths[0].resolve().relative_to(directory.resolve())
            shutil.copyfile(paths[0], target)
        elif receipt.get("url"):
            _download_url(receipt["url"], target)
        elif receipt.get("file_id") and backend == "cli":
            run_tool(config, ["video", "download", "--file-id", str(receipt["file_id"]), "--out", str(target), *_minimax_region_arguments(region), "--output", "json"])
        else:
            raise ValueError("completed video has no downloadable resource")
        return {**result, "status": "downloaded", "external_task_id": payload["external_task_id"], "path": str(target)}
    raise ValueError("unsupported video tool command")
