"""Image adapters for installed vendor CLIs and official MCP tools."""
from __future__ import annotations

import ast
import io
import re
from pathlib import Path

from game_visual_forge.contracts.provider import ExternalProvider
from game_visual_forge.contracts.serialization import dump_json, load_json
from .image_http import ImageApiError, ImageHttpTransport, check_parameters, image_data_uri, integer
from .mcp_client import McpClient, tool_result, validate_tool
from .tool_runtime import OFFICIAL_GUIDES, execution_config, run_tool, tool_preflight


def _paths_in_directory(paths, directory):
    result = []
    for value in paths:
        path = Path(value).resolve()
        path.relative_to(directory.resolve())
        if not path.is_file() or path.stat().st_size > 128 * 1024 * 1024:
            raise ImageApiError("invalid_tool_image")
        result.append(path)
    return result


def minimax_media_result(value, directory):
    """MiniMax's official MCP returns a labelled Python list in text content."""
    result = tool_result(value)
    text = result.get("text", "")
    prefix = "Success. Image URLs: "
    if text.startswith(prefix):
        try:
            items = ast.literal_eval(text[len(prefix):])
        except (ValueError, SyntaxError):
            raise ImageApiError("invalid_minimax_mcp_result") from None
        if isinstance(items, list) and all(isinstance(item, str) for item in items):
            return items
    raise ImageApiError("missing_minimax_mcp_images")


class ToolImageAdapter:
    def __init__(self, provider, execution, *, root=None, output_dir=None, transport=None, client=None):
        self.provider = ExternalProvider(provider)
        self.execution = execution_config(self.provider.value, execution)
        if self.execution["backend"] not in {"cli", "mcp"}:
            raise ValueError("tool image adapter requires CLI or MCP execution")
        self.root = Path(root or ".").resolve()
        self.directory = Path(output_dir or self.root / "outputs" / "provider").resolve() / ".provider"
        self.transport = transport or ImageHttpTransport()
        self.client = client
        if self.provider in {ExternalProvider.JIMENG, ExternalProvider.DREAMINA} and self.execution["backend"] == "mcp":
            raise ValueError("use the project's Jimeng MCP bridge workflow tools; their attempts select CLI or API execution")
        self.synchronous = self.provider not in {ExternalProvider.JIMENG, ExternalProvider.DREAMINA}

    def models(self):
        provider = self.provider.value
        if provider == "minimax":
            models = ("MiniMax-H3-Image",)
        elif provider in {"jimeng", "dreamina"}:
            models = ("dreamina-default",)
        elif self.execution["backend"] == "mcp":
            models = ("bailian-image-auto",)
        else:
            models = ("wan2.7-image", "wan2.7-image-pro")
        preset = provider in {"jimeng", "dreamina"} or models == ("bailian-image-auto",)
        return {"schema_version": 1, "provider": provider, "backend": self.execution["backend"], "official_source": OFFICIAL_GUIDES[provider], "models": [{"model": model, "modes": ["text-to-image", "reference-image"], "synchronous": self.synchronous, "native_alpha": False, "model_selection": "server-preset" if preset else "explicit", "notice": "Official Bailian MCP selects its own model; this does not identify a Wan model" if model == "bailian-image-auto" else ""} for model in models]}

    def normalize(self, model, parameters, quantity):
        if model not in {item["model"] for item in self.models()["models"]}:
            raise ValueError("model is unsupported by the selected tool backend")
        params = dict(parameters)
        execution = execution_config(self.provider.value, params.pop("execution", self.execution))
        if execution != self.execution:
            raise ValueError("image execution binding does not match")
        if self.provider is ExternalProvider.MINIMAX:
            from .minimax_image import MiniMaxImageAdapter
            value = MiniMaxImageAdapter().normalize(model, params, quantity, inline_response=False)
            if "aigc_watermark" in value:
                raise ValueError("aigc_watermark is supported by the API backend")
            if self.execution["backend"] == "cli" and "disable_prompt_enhanced" in value:
                raise ValueError("disable_prompt_enhanced requires the API or MCP backend")
        elif self.provider is ExternalProvider.WANXIANG and self.execution["backend"] == "cli":
            from .wanxiang_image import WanxiangImageAdapter
            value = WanxiangImageAdapter().normalize(model, params, quantity)
            if "workspace_id" in value or value["region"] != "cn-beijing":
                raise ValueError("Bailian CLI uses its configured account/region; use API for explicit workspace or international region")
            if set(value) - {"prompt", "references", "size", "region"}:
                raise ValueError("selected Bailian CLI image options require API execution")
        else:
            allowed = {"ratio", "resolution_type"} if self.provider.value in {"jimeng", "dreamina"} else {"size", "negative_prompt", "prompt_extend"}
            value = check_parameters(params, allowed, 32000, 1 if self.provider is ExternalProvider.WANXIANG else 16)
            integer(quantity, 1, 1 if self.provider.value in {"jimeng", "dreamina"} or value["references"] else 4, "quantity")
            for key in ("ratio", "resolution_type", "negative_prompt"):
                if key in value and (not isinstance(value[key], str) or not value[key].strip()):
                    raise ValueError(key + " must be a nonempty string")
            if "prompt_extend" in value and not isinstance(value["prompt_extend"], bool):
                raise ValueError("prompt_extend must be boolean")
            if "size" in value and not re.fullmatch(r"[1-9][0-9]*\*[1-9][0-9]*", str(value["size"])):
                raise ValueError("Bailian MCP size must use width*height")
        value["execution"] = execution
        return value

    def preflight(self):
        return tool_preflight(self.provider.value, self.execution)

    def build_body(self, model, parameters, quantity, reference_data):
        self.normalize(model, parameters, quantity)
        if len(reference_data) != len(parameters["references"]):
            raise ValueError("verified reference image bytes are required")
        if self.execution["backend"] == "cli" and self.provider.value in {"jimeng", "dreamina"}:
            from .tool_runtime import require_help_flags
            command = "image2image" if reference_data else "text2image"
            flags = ["--prompt"]
            if reference_data:
                flags.append("--images")
            flags.extend("--" + key for key in ("ratio", "resolution_type") if key in parameters)
            require_help_flags(self.execution, command, flags)
        if self.execution["backend"] == "mcp":
            client = self._mcp_client(parameters)
            name, arguments = self._mcp_arguments(model, parameters, quantity, reference_data)
            validate_tool(client.tools(), name, arguments)
        return {}

    def _mcp_client(self, parameters):
        if self.client is not None:
            return self.client
        environment = {}
        if self.provider is ExternalProvider.MINIMAX:
            environment = {"MINIMAX_API_RESOURCE_MODE": "url", "MINIMAX_API_HOST": "https://api.minimaxi.com" if parameters["region"] == "cn" else "https://api.minimax.io"}
        return McpClient(self.execution, environment=environment)

    def _references(self, reference_data):
        from PIL import Image
        paths = []
        directory = self.directory.parent / ".references"
        for index, data in enumerate(reference_data, 1):
            with Image.open(io.BytesIO(data)) as image:
                extension = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "BMP": ".bmp"}[image.format]
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"reference-{index:02d}{extension}"
            path.write_bytes(data)
            paths.append(str(path))
        return paths

    def submit(self, model, parameters, quantity, reference_data):
        self.normalize(model, parameters, quantity)
        self.directory.mkdir(parents=True, exist_ok=True)
        if self.execution["backend"] == "mcp":
            return self._submit_mcp(model, parameters, quantity, reference_data)
        references = self._references(reference_data)
        if self.provider is ExternalProvider.MINIMAX:
            arguments = ["image", "generate", "--model", model, "--prompt", parameters["prompt"], "--out-dir", str(self.directory), "--output-format", "png", "--output", "json", "--quiet"]
            for reference in references:
                arguments.extend(["--image", reference])
            arguments.extend(["--n", str(quantity)])
            arguments.extend(["--region", parameters["region"], "--base-url", "https://api.minimax.cn" if parameters["region"] == "cn" else "https://api.minimax.io"])
            for key in ("size", "aspect_ratio", "area"):
                if key in parameters and not (key == "size" and parameters[key] == "auto"):
                    arguments.extend(["--" + key.replace("_", "-"), str(parameters[key])])
            result = run_tool(self.execution, arguments)
            paths = result.get("saved", [])
        elif self.provider is ExternalProvider.WANXIANG:
            arguments = ["image", "edit" if references else "generate", "--model", model, "--prompt", parameters["prompt"], "--out-dir", str(self.directory), "--output", "json"]
            for reference in references:
                arguments.extend(["--image", reference])
            arguments.extend(["--n", str(quantity), "--size", parameters["size"]])
            result = run_tool(self.execution, arguments)
            paths = result.get("saved", [])
        else:
            command = "image2image" if references else "text2image"
            arguments = [command, "--prompt=" + parameters["prompt"]]
            if references:
                arguments.extend(["--images", *references])
            for key in ("ratio", "resolution_type"):
                if key in parameters:
                    arguments.append("--" + key + "=" + str(parameters[key]))
            result = run_tool(self.execution, arguments)
            task_id = result.get("submit_id")
            if not task_id:
                raise ImageApiError("missing_dreamina_submit_id")
            return {"external_task_id": str(task_id), "status": "submitted"}
        if not isinstance(paths, list) or not paths:
            raise ImageApiError("missing_tool_images")
        saved = [str(path) for path in _paths_in_directory(paths, self.directory)]
        dump_json(self.directory / "saved-images.json", {"paths": saved})
        return self._read_images(saved, quantity)

    def _mcp_arguments(self, model, parameters, quantity, reference_data):
        if self.provider is ExternalProvider.MINIMAX:
            arguments = {"model": model, "prompt": parameters["prompt"], "n": quantity, "output_directory": str(self.directory)}
            for key in ("size", "aspect_ratio", "area"):
                if key in parameters:
                    arguments[key] = parameters[key]
            if reference_data:
                arguments["images"] = [image_data_uri(data) for data in reference_data]
                tool = "image_edit"
            else:
                tool = "text_to_image"
                if "disable_prompt_enhanced" in parameters:
                    arguments["prompt_optimizer"] = not parameters["disable_prompt_enhanced"]
            if arguments.get("size") == "auto":
                arguments.pop("size")
        else:
            arguments = {"prompt": parameters["prompt"]}
            if reference_data:
                arguments["image_url"] = image_data_uri(reference_data[0])
                tool = "bailian_image_edit"
            else:
                tool = "bailian_image_gen"
                arguments["n"] = quantity
                for key in ("size", "prompt_extend"):
                    if key in parameters:
                        arguments[key] = parameters[key]
            if "negative_prompt" in parameters:
                arguments["negative_prompt"] = parameters["negative_prompt"]
        return tool, arguments

    def _submit_mcp(self, model, parameters, quantity, reference_data):
        tool, arguments = self._mcp_arguments(model, parameters, quantity, reference_data)
        response = self._mcp_client(parameters).call(tool, arguments)
        if self.provider is ExternalProvider.MINIMAX:
            items = minimax_media_result(response, self.directory)
        else:
            result = tool_result(response)
            urls = result.get("results", [])
            if not isinstance(urls, list) or not urls:
                raise ImageApiError("missing_bailian_mcp_images")
            items = [item if isinstance(item, str) else item["url"] for item in urls]
        return self._read_images(items, quantity)

    def _read_images(self, items, quantity):
        if not items or len(items) > quantity:
            raise ImageApiError("unexpected_tool_image_count")
        images, errors = [], []
        for index, item in enumerate(items, 1):
            try:
                if item.startswith(("https://", "http://")):
                    data = self.transport.read_image(item)
                else:
                    data = _paths_in_directory([item], self.directory)[0].read_bytes()
                images.append(data)
            except Exception:
                images.append(None)
                errors.append({"index": index, "code": "tool_image_download_failed"})
        return {"images": images, "uncertain": bool(errors) or len(images) != quantity, "errors": errors}

    def recover_images(self, quantity):
        manifest = self.directory / "saved-images.json"
        if manifest.is_file():
            paths = _paths_in_directory(load_json(manifest)["paths"], self.directory)
        else:
            paths = sorted(path for path in self.directory.rglob("*") if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} and path.is_file()) if self.directory.is_dir() else []
        return self._read_images([str(path) for path in paths], quantity) if paths else {"images": [], "errors": []}

    def query(self, task_id, model, parameters):
        if self.synchronous:
            raise ValueError("this image tool completes synchronously; recover saved local output")
        directory = self.directory / task_id
        directory.mkdir(parents=True, exist_ok=True)
        result = run_tool(self.execution, ["query_result", "--submit_id=" + task_id, "--download_dir=" + str(directory)])
        status = result.get("gen_status")
        if status == "fail":
            return {"status": "failed", "error_code": "dreamina_generation_failed"}
        if status != "success":
            if status != "querying":
                raise ImageApiError("invalid_dreamina_status")
            return {"status": "running"}
        paths = sorted(path for path in directory.rglob("*") if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} and path.is_file())
        if not paths:
            raise ImageApiError("dreamina_download_missing")
        return {"status": "completed", "result_paths": [str(path) for path in _paths_in_directory(paths, directory)]}
