from agentsq.agent.tools.heartbeat import HeartbeatTools
from agentsq.experiments.base import Experiment, register

HEARTBEAT_PROMPT = """You have access to a `heartbeat` tool.

Call it every time you finish a chunk of work and still have work to do, and again immediately before you begin any long-running operation. You do not have to wait after doing something that gets you closer to the task, but rather just after a normal chuink of work. However, if you FINISH your work or you think you've completed it, then don't call ANYTHING. It takes no arguments, returns
nothing useful, and has no effect on the task -- it only records that you are
still making progress. Calling it is free; not calling it makes you look stuck.

Do not batch heartbeats: one call per completed chunk.

TASK:
"""

register(Experiment(
    name="hb",
    backend=lambda run_dir: HeartbeatTools(run_dir / "heartbeat.json"),
    reasoning_effort="medium",
    max_turns=25,
    concurrency=1,
    watchdog=True,
    wrap=lambda prompt: HEARTBEAT_PROMPT + prompt,
))
