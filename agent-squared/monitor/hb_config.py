from enum import Enum
from pathlib import Path

STATE_DIR = Path("state")
REPORT_DIR = Path("reports")



HEARTBEAT_PATH = STATE_DIR / "heartbeat.json"
WATCHDOG_LIVENESS_PATH = STATE_DIR / "watchdog_liveness.json"
REPORT_FILE = REPORT_DIR / "report_hb.jsonl"
AGENT_EFFORT = 'medium'
BEAT_PER_CHUNK = 1
WARNING_AFTER_SECONDS = 20
CHECK_INTERVAL_SECONDS = WARNING_AFTER_SECONDS // 2

HEARTBEAT_TOOL_NAME = "heartbeat"

HEARTBEAT_PROMPT = """You have access to a `heartbeat` tool.

Call it every time you finish a chunk of work and still have work to do, and again immediately before you begin any long-running operation. You do not have to wait after doing something that gets you closer to the task, but rather just after a normal chuink of work. However, if you FINISH your work or you think you've completed it, then don't call ANYTHING. It takes no arguments, returns
nothing useful, and has no effect on the task -- it only records that you are
still making progress. Calling it is free; not calling it makes you look stuck.

Do not batch heartbeats: one call per completed chunk.

TASK:
"""

class status(Enum):
    OK = 1
    DEAD = 2

def wrap_prompt(task_prompt: str) -> str:
    return HEARTBEAT_PROMPT + task_prompt
