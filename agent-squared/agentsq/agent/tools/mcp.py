import json
import os
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agentsq.agent.tools.base import ToolBackend
from dotenv import load_dotenv

load_dotenv()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


class McpTools(ToolBackend):

    def __init__(self, command: str = "npx", args: list[str] | None = None):
        if args is None:
            args = ["-y", "mcp-remote", f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}"]
        self.params = StdioServerParameters(command=command, args=args)
        self.stack: AsyncExitStack | None = None
        self.session: ClientSession | None = None

    async def __aenter__(self):
        self.stack = AsyncExitStack()
        read, write = await self.stack.enter_async_context(stdio_client(self.params))
        self.session = await self.stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()
        return self

    async def __aexit__(self, *exc):
        await self.stack.aclose()
        self.stack = None
        self.session = None
        return False

    async def specs(self) -> list[dict]:
        listed = await self.session.list_tools()
        return [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": getattr(tool, "inputSchema", None) or tool.input_schema,
            }
            for tool in listed.tools
        ]

    async def call(self, name: str, arguments: str) -> str:
        result = await self.session.call_tool(name, json.loads(arguments))
        return self._flatten(result)

    def _flatten(self, result) -> str:
        parts = []
        for c in result.content:
            kind = getattr(c, "type", "unknown")
            if kind == "text":
                parts.append(c.text)
            elif kind == "image":
                parts.append(f"[image {c.mimeType}, {len(c.data)} b64chars]")
            else:
                parts.append(f"[{kind}] block")
        return "".join(parts)
