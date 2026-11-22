
from __future__ import annotations

import asyncio
import json
from recovery import MCP_TIMEOUT_SECONDS
from contextlib import AsyncExitStack

from mcp import Client
from observability import observability


class MCPToolRuntime:

    def __init__(self, servers: dict):
        self.servers = servers

        self.stack = AsyncExitStack()

        # Tool Name → MCP Client
        self.tool_clients = {}

        # Tool Name → Server Name
        self.tool_servers = {}

        # 给 DeepSeek 的 Function Schema
        self.llm_tools = []

    # ========================================
    # MCP 生命周期
    # ========================================

    async def __aenter__(self):

        try:
            for server_name, params in self.servers.items():

                print(
                    f"[MCP] connecting {server_name}"
                )

                client = await self.stack.enter_async_context(
                    Client(params)
                )

                # MCP Tool List 可能分页
                cursor = None

                while True:

                    page = await client.list_tools(
                        cursor=cursor
                    )

                    for tool in page.tools:

                        name = tool.name

                        if name in self.tool_clients:
                            raise ValueError(
                                f"Tool 重名: {name}"
                            )

                        self.tool_clients[name] = client
                        self.tool_servers[name] = server_name

                        self.llm_tools.append(
                            self.convert_tool(tool)
                        )

                        print(
                            f"[MCP] registered {name} "
                            f"from {server_name}"
                        )

                    cursor = getattr(
                        page,
                        "next_cursor",
                        None,
                    )

                    if cursor is None:
                        break

            if not self.llm_tools:
                raise RuntimeError(
                    "没有发现任何 MCP Tool"
                )

            return self

        except BaseException:
            await self.stack.aclose()
            raise

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        await self.stack.aclose()

    # ========================================
    # MCP Schema → LLM Function Schema
    # ========================================

    def convert_tool(self, tool) -> dict:

        schema = getattr(
            tool,
            "input_schema",
            None,
        )

        if schema is None:
            schema = getattr(
                tool,
                "inputSchema",
                None,
            )

        if schema is None:
            schema = {
                "type": "object",
                "properties": {},
            }

        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": schema,
            },
        }

    # ========================================
    # MCP Result → Text
    # ========================================

    @staticmethod
    def result_to_text(result) -> str:

        structured = getattr(
            result,
            "structured_content",
            None,
        )

        if structured is not None:

            text = json.dumps(
                structured,
                ensure_ascii=False,
            )

        else:

            text = "\n".join(
                getattr(item, "text", None) or str(item)
                for item in result.content
            )

        if getattr(result, "is_error", False):
            return "MCP Tool 执行失败：\n" + text

        return text

    # ========================================
    # Tool Router + Executor
    # ========================================

    async def execute(
        self,
        tool_name: str,
        arguments: dict,
    ) -> str:

        client = self.tool_clients.get(
            tool_name
        )

        if client is None:
            return f"未知工具: {tool_name}"

        server_name = self.tool_servers[
            tool_name
        ]

        print(
            f"[MCP Execute] "
            f"server={server_name}, "
            f"tool={tool_name}"
        )

        print(
            f"[Arguments] keys={sorted(arguments)}"
        )

        try:

            with observability.span("tool", tool_name, metadata={"server": server_name}) as outcome:
                result = await asyncio.wait_for(client.call_tool(tool_name, arguments), MCP_TIMEOUT_SECONDS)
                text = self.result_to_text(result)
                status = "error" if getattr(result, "is_error", False) else "ok"
                if status == "error":
                    outcome.update(status="error", error_type="MCPToolError")

        except Exception as e:
            status = "error"
            text = (
                "Tool 异常："
                f"{type(e).__name__}"
            )

        print(
            f"[Tool Result] tool={tool_name}, length={len(text)}, status={status}"
        )

        return text
