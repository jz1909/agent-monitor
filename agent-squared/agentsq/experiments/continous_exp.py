from agentsq.agent.tools.faulty_mcp import FaultyMcpTools
from agentsq.agent.tools.mcp import McpTools
from agentsq.experiments.base import Experiment, register
from agentsq.agent.run_cont_stream import run_cont_task


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
    name="continous",
    backend=make_backend,
    reasoning_effort="high",
    max_turns=35,
    concurrency=10,
    search_version="baseline",
    runner=run_cont_task,
    inference_provider="ALCF"
))
