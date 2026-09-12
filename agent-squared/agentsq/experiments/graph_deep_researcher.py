from agentsq.experiments.base import Experiment, register
from agentsq.agent.run_graph import run_graph_task
from agentsq.workflows.deep_researcher import adapter

register(Experiment(
    name='graph-topo',
    workflow=adapter,
    loops=3,
    use_topos=True,
    runner=run_graph_task,
    concurrency=1,
    agent_model="gpt-5-nano",
    reasoning_effort="medium",
))
