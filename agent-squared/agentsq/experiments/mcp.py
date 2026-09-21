from agentsq.agent.tools.faulty_mcp import FaultyMcpTools
from agentsq.agent.tools.mcp import McpTools
from agentsq.experiments.base import Experiment, register


def make_backend(run_dir, experiment):
    if experiment.search_version == "baseline":
        return McpTools()
    if experiment.search_version == "broken":
        return FaultyMcpTools()
    raise ValueError(
        f"mcp experiment has no {experiment.search_version!r} search version "
        "(expected 'baseline' or 'broken')"
    )


register(Experiment(
    name="mcp",
    backend=make_backend,
    reasoning_effort="xhigh",
    max_turns=10,
    concurrency=10,
    search_version="baseline"
))
