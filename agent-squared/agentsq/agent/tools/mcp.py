import json
import os
from collections import Counter
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
        self.call_log: list[dict] = []
        self.call_counts: Counter = Counter()

    async def __aenter__(self):
        self.stack = AsyncExitStack()
        read, write = await self.stack.enter_async_context(stdio_client(self.params))
        self.session = await self.stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()
        return self

    async def __aexit__(self, *exc):
        print(f"[mcp] {self.summary()}", flush=True)
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
        self.record(name, arguments)
        result = await self.session.call_tool(name, json.loads(arguments))
        return self._flatten(result)

    def record(self, name: str, arguments: str, faulted: bool = False) -> None:
        self.call_counts[name] += 1
        self.call_log.append({
            "index": len(self.call_log) + 1,
            "tool": name,
            "arguments": arguments,
            "faulted": faulted,
        })

    def summary(self) -> str:
        if not self.call_log:
            return "no tool calls"
        per_tool = ", ".join(f"{n} x{c}" for n, c in self.call_counts.items())
        faulted = sum(1 for c in self.call_log if c["faulted"])
        return f"{len(self.call_log)} calls: {per_tool} ({faulted} faulted)"

    def extras(self) -> dict:
        return {
            "mcp_call_count": len(self.call_log),
            "mcp_tool_counts": dict(self.call_counts),
            "mcp_faulted_count": sum(1 for c in self.call_log if c["faulted"]),
            "mcp_call_log": self.call_log,
        }

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
