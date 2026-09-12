from agentsq.agent.tools.none import NoTools
from agentsq.experiments.base import Experiment, register

register(Experiment(
    name="plain",
    backend=lambda run_dir: NoTools(),
    reasoning_effort="xhigh",
    max_turns=1,
    concurrency=10,
))
