import json
import os
from datetime import datetime, timezone
from uuid import uuid4

from hb_config import HEARTBEAT_PATH, HEARTBEAT_TOOL_NAME


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


class HeartbeatWriter:

    def __init__(self):
        self.frame_id = uuid4().hex
        self.beat_count = 0

    def beat(self):

        self.beat_count += 1
        curr_time = datetime.now(timezone.utc).isoformat()
        record = {"time_utc": curr_time, "frame_id": self.frame_id}

        tmp_path = HEARTBEAT_PATH.with_suffix(HEARTBEAT_PATH.suffix + ".tmp")
        tmp_path.write_text(json.dumps(record) + "\n")
        os.replace(tmp_path, HEARTBEAT_PATH)


if __name__ == "__main__":
    HeartbeatWriter().beat()
