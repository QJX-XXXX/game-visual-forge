"""Project-provided stdio workflows for Jimeng and model-specific Wan images."""
from __future__ import annotations

from pathlib import Path
import asyncio
import inspect
import importlib.metadata
import json
from typing import get_type_hints

from game_visual_forge.contracts.serialization import load_json
from .image import confirm_image_attempt, download_image_attempt, image_adapter, prepare_image_attempt, query_image_attempt, submit_image_attempt
from .image_http import repo_path, assert_safe
from .video import download_video_attempt, query_video_attempt, submit_video_attempt


def create_server(repo_root, provider="jimeng"):
    if provider not in {"jimeng", "wanxiang"}:
        raise ValueError("unsupported workflow bridge provider")
    allowed_providers = {"jimeng", "dreamina"} if provider == "jimeng" else {"wanxiang"}
    try:
        if not importlib.metadata.version("mcp").startswith("2."):
            raise ImportError
        from mcp.server import Server
        from mcp import types
        from pydantic import create_model
    except (ImportError, importlib.metadata.PackageNotFoundError):
        raise ValueError("MCP 2.x Python extra is required; ask the user before installing .[mcp]") from None
    root = Path(repo_root).resolve()
    tools = {}

    def tool():
        def register(function):
            hints = get_type_hints(function)
            fields = {name: (hints[name], ... if parameter.default is inspect.Parameter.empty else parameter.default) for name, parameter in inspect.signature(function).parameters.items()}
            arguments = create_model(function.__name__ + "Arguments", **fields)
            tools[provider + "_" + function.__name__] = (function, arguments)
            return function
        return register

    async def list_tools(context, params):
        return types.ListToolsResult(tools=[types.Tool(name=name, description=inspect.getdoc(function), inputSchema=arguments.model_json_schema()) for name, (function, arguments) in tools.items()])

    async def call_tool(context, params):
        try:
            function, arguments = tools[params.name]
            values = arguments.model_validate(params.arguments or {}).model_dump()
            result = await asyncio.to_thread(function, **values)
            assert_safe(result)
            return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))], structuredContent=result)
        except Exception as error:
            message = "Bridge operation failed: " + type(error).__name__
            if type(error) is ValueError:
                try:
                    assert_safe(str(error))
                    message = str(error)
                except ValueError:
                    pass
            return types.CallToolResult(isError=True, content=[types.TextContent(type="text", text=message)])

    server = Server("Game Visual Forge " + provider, instructions="Project-provided provider workflow bridge. Use Agent-native image tools first. Obtain user source selection and explicit paid confirmation before submit. Installation and login require separate user authorization.", on_list_tools=list_tools, on_call_tool=call_tool)

    def path(value):
        return repo_path(root, value)

    def image_attempt(value):
        target = path(value)
        if load_json(target).get("provider") not in allowed_providers:
            raise ValueError("attempt differs from this bridge provider")
        return target

    def video_attempt(value):
        target = path(value)
        if load_json(target).get("provider") != "jimeng":
            raise ValueError("this bridge serves Jimeng video attempts")
        return target

    @tool()
    def image_models(backend: str = "cli") -> dict:
        """List the project's verified image profiles for a CLI or API attempt."""
        if backend not in {"api", "cli"}:
            raise ValueError("choose api or cli execution within this MCP bridge")
        return image_adapter(provider, execution=None if backend == "api" else {"backend": "cli"}).models()

    @tool()
    def image_preflight(backend: str = "cli") -> dict:
        """Inspect local prerequisites. Does not install tools, authenticate, or generate."""
        if backend not in {"api", "cli"}:
            raise ValueError("choose api or cli execution within this MCP bridge")
        return image_adapter(provider, execution=None if backend == "api" else {"backend": "cli"}).preflight()

    @tool()
    def image_prepare(request: str, decision: str, output: str, now: str, parameters: str | None = None, kind: str = "sprite", model: str | None = None, quantity: int = 1, state: str | None = None, backend: str = "cli") -> dict:
        """Prepare a source-selected image attempt. All paths are workspace-relative."""
        if load_json(path(decision)).get("selected_provider") not in allowed_providers:
            raise ValueError("select this bridge provider before preparing the attempt")
        if backend not in {"api", "cli"}:
            raise ValueError("choose api or cli execution within this MCP bridge")
        configured = load_json(path(parameters)).get("execution") if parameters else None
        if configured and configured.get("backend", "api") != backend:
            raise ValueError("bridge execution differs from the selected backend")
        execution = configured or ({"backend": "cli"} if backend == "cli" else None)
        selected_model = model or image_adapter(provider, execution=execution).models()["models"][0]["model"]
        return prepare_image_attempt(path(request), path(decision), path(parameters) if parameters else None, path(output), kind=kind, model=selected_model, quantity=quantity, state_path=path(state) if state else None, repo_root=root, now=now, execution=execution)

    @tool()
    def image_confirm(attempt: str, quote: str, output: str, now: str, user_confirmed: bool = False) -> dict:
        """Record a verified total quote only after the user explicitly confirms spending."""
        if not user_confirmed:
            raise ValueError("explicit user spending confirmation is required")
        return confirm_image_attempt(image_attempt(attempt), path(quote), path(output), now=now)

    @tool()
    def image_submit(attempt: str, confirmation: str, now: str) -> dict:
        """Consume a bound one-time paid confirmation and submit one image attempt."""
        return submit_image_attempt(image_attempt(attempt), path(confirmation), repo_root=root, now=now)

    @tool()
    def image_query(attempt: str, now: str, recovered_task_id: str | None = None) -> dict:
        """Query the same task, optionally attaching a provider-verified recovery ID."""
        return query_image_attempt(image_attempt(attempt), repo_root=root, now=now, recovered_task_id=recovered_task_id)

    @tool()
    def image_download(attempt: str, now: str) -> dict:
        """Recover and validate image outputs for the existing paid task."""
        return download_image_attempt(image_attempt(attempt), repo_root=root, now=now)

    if provider == "jimeng":
        wrapper = Path(__file__).resolve().parents[3] / "skills" / "forge-video-to-sprite" / "scripts" / "providers" / "jimeng.py"

        @tool()
        def video_submit(attempt: str, confirmation: str, now: str) -> dict:
            """Submit an existing video attempt with its bound one-time paid confirmation."""
            return submit_video_attempt(video_attempt(attempt), path(confirmation), wrapper, now=now).to_dict()

        @tool()
        def video_query(attempt: str, now: str) -> dict:
            """Query the existing CLI or API video task without another generation."""
            return query_video_attempt(video_attempt(attempt), wrapper, now=now).to_dict()

        @tool()
        def video_download(attempt: str, output_dir: str, now: str) -> dict:
            """Download the existing video task through its original backend."""
            return download_video_attempt(video_attempt(attempt), wrapper, path(output_dir), now=now).to_dict()

    return server


def serve(repo_root, provider="jimeng"):
    async def run():
        server = create_server(repo_root, provider)
        from mcp.server.stdio import stdio_server
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    asyncio.run(run())
