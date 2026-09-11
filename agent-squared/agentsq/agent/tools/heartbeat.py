from pathlib import Path

from agentsq.agent.tools.base import ToolBackend
from agentsq.liveness.writer import HeartbeatWriter

HEARTBEAT_TOOL_NAME = "heartbeat"

HEARTBEAT_TOOL_SPEC = {
    "type": "function",
    "name": HEARTBEAT_TOOL_NAME,
    "description": (
        "Record that you are still making progress. Call this after finishing a "
        "chunk of work, and before starting a long-running operation. Takes no "
        "arguments and has no effect on the task."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
}


class HeartbeatTools(ToolBackend):

    def __init__(self, path: Path):
        self.writer = HeartbeatWriter(path)

    async def specs(self) -> list[dict]:
        return [HEARTBEAT_TOOL_SPEC]

    async def call(self, name: str, arguments: str) -> str:
        if name != HEARTBEAT_TOOL_NAME:
            return f"unknown tool: {name}"
        try:
            self.writer.beat()
            print(f"[beat #{self.writer.beat_count}]", flush=True)
            return "ok"
        except Exception as e:
            print(f"[beat FAILED] {e}", flush=True)
            return f"heartbeat failed: {e}"

    def extras(self) -> dict:
        return {"frame_id": self.writer.frame_id, "beat_count": self.writer.beat_count}
