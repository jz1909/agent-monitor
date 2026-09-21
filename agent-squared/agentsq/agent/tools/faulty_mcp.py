import json

from agentsq.agent.tools.mcp import McpTools
from agentsq.workflows.deep_researcher.spoofer.search_faults import (
    broken_tavily_crawl,
    broken_tavily_extract,
    broken_tavily_map,
    broken_tavily_research,
    broken_tavily_search,
)

BROKEN = {
    "tavily_search": broken_tavily_search,
    "tavily_extract": broken_tavily_extract,
    "tavily_crawl": broken_tavily_crawl,
    "tavily_map": broken_tavily_map,
    "tavily_research": broken_tavily_research,
}


class FaultyMcpTools(McpTools):
    """MCP backend whose search tools always fail.

    The fault lives on the instance, so concurrent runs in the same process
    stay independent: a baseline run holds a plain McpTools and is unaffected.
    """

    def __init__(self, faults: dict = None, **kwargs):
        super().__init__(**kwargs)
        self.faults = BROKEN if faults is None else faults

    async def call(self, name: str, arguments: str) -> str:
        if name not in self.faults:
            return await super().call(name, arguments)
        self.record(name, arguments, faulted=True)
        return json.dumps(self.faults[name]())
