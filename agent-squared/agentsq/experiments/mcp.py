from agentsq.agent.tools.mcp import McpTools
from agentsq.experiments.base import Experiment, register

register(Experiment(
    name="mcp",
    backend=lambda run_dir: McpTools(),
    reasoning_effort="xhigh",
    max_turns=10,
    concurrency=10,
))
