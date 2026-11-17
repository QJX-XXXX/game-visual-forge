"""Optional official MCP SDK client for existing stdio and HTTP servers."""
from __future__ import annotations

import asyncio
import os
from contextlib import AsyncExitStack

from .image_http import ImageApiError
from .tool_runtime import existing_command


def validate_tool(tools, name, arguments):
    from jsonschema import Draft202012Validator
    tool = next((item for item in tools if item["name"] == name), None)
    if tool is None:
        raise ValueError("required MCP tool is unavailable: " + name)
    if not Draft202012Validator(tool.get("inputSchema", {})).is_valid(arguments):
        raise ValueError("arguments do not match the current MCP tool schema")


class McpClient:
    def __init__(self, config, *, environment=None):
        self.config = config
        self.environment = environment or {}

    async def _request(self, name, arguments):
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.types import PaginatedRequestParams
        except ImportError:
            raise ValueError("MCP Python extra is missing; ask the user before installing .[mcp]") from None
        config = self.config
        async with AsyncExitStack() as stack:
            transport = config["transport"]
            if transport == "stdio":
                from mcp.client.stdio import stdio_client
                command = existing_command(config["command"])
                environment = dict(self.environment)
                variable = config.get("credential_env")
                if variable and os.environ.get(variable):
                    environment[variable] = os.environ[variable]
                errlog = stack.enter_context(open(os.devnull, "w", encoding="utf-8"))
                streams = await stack.enter_async_context(stdio_client(StdioServerParameters(command=command[0], args=command[1:], env=environment), errlog=errlog))
            else:
                headers = {}
                if config.get("credential_env"):
                    key = os.environ.get(config["credential_env"])
                    if not key:
                        raise ValueError("configured MCP credential environment variable is missing")
                    headers["Authorization"] = "Bearer " + key
                if transport == "sse":
                    from mcp.client.sse import sse_client
                    streams = await stack.enter_async_context(sse_client(config["url"], headers=headers, sse_read_timeout=config["timeout_seconds"]))
                else:
                    import httpx2
                    from mcp.client.streamable_http import streamable_http_client
                    http = await stack.enter_async_context(httpx2.AsyncClient(headers=headers, timeout=config["timeout_seconds"]))
                    streams = await stack.enter_async_context(streamable_http_client(config["url"], http_client=http))
            session = await stack.enter_async_context(ClientSession(streams[0], streams[1], read_timeout_seconds=float(config["timeout_seconds"])))
            await session.initialize()
            tools = []
            cursor = None
            while True:
                page = await session.list_tools(params=PaginatedRequestParams(cursor=cursor) if cursor else None)
                tools.extend(tool.model_dump(mode="json", by_alias=True) for tool in page.tools)
                cursor = page.next_cursor
                if not cursor:
                    break
            if name is None:
                return {"tools": tools}
            validate_tool(tools, name, arguments)
            response = await session.call_tool(name, arguments=arguments)
            value = response.model_dump(mode="json", by_alias=True)
            if value.get("isError"):
                raise ImageApiError("mcp_tool_error")
            return value

    def call(self, name, arguments):
        try:
            return asyncio.run(asyncio.wait_for(self._request(name, arguments), timeout=self.config["timeout_seconds"] + 10))
        except Exception:
            raise ImageApiError("mcp_connection_or_tool_error") from None

    def tools(self):
        return self.call(None, {})["tools"]


def tool_result(value):
    """Decode structured results and JSON text without persisting raw tool output."""
    import json
    if isinstance(value.get("structuredContent"), dict):
        return value["structuredContent"]
    texts = [item.get("text", "") for item in value.get("content", []) if item.get("type") == "text"]
    if len(texts) == 1:
        try:
            result = json.loads(texts[0])
            if isinstance(result, dict):
                return result
        except ValueError:
            pass
    return {"text": "\n".join(texts)}
