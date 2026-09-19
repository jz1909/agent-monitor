from contextlib import contextmanager
from unittest import mock

from agentsq.agent.tools.mcp import McpTools
import json
from agentsq.workflows.deep_researcher.spoofer.search_faults import (
    broken_tavily_crawl,
    broken_tavily_extract,
    broken_tavily_map,
    broken_tavily_research,
    broken_tavily_search,
)

BROKEN = ["tavily_search",
    "tavily_extract",
    "tavily_crawl",
    "tavily_map",
    "tavily_research"]

MAPPING = {
    "tavily_search": broken_tavily_search,
    "tavily_extract": broken_tavily_extract,
    "tavily_crawl": broken_tavily_crawl,
    "tavily_map": broken_tavily_map,
    "tavily_research": broken_tavily_research,
}
@contextmanager
def fault_mcp():
    original = McpTools.call

    async def faulty_call(self, name, argument):
        if name not in MAPPING:
            return await original(self, name, argument)
        self.record(name, argument, faulted=True)
        return json.dumps(MAPPING[name]())

    with mock.patch.object(McpTools, "call", faulty_call):
        yield

