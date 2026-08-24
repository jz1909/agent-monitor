from typing import Any
from state import status
from uuid import uuid4
from datetime import datetime, timezone
from hb_config import STATE_DIR, HEARTBEAT_PATH
import json
import os

class HeartbeatWriter:

    def __init__(self):
        self.frame_id = uuid4().hex

    def generate_id(self):
        frame_id = uuid4().hex
        return frame_id

    def beat(self):

        frame_id = self.generate_id()
        curr_time = datetime.now(timezone.utc).isoformat()
        record = {"time_utc":curr_time, "frame_id":frame_id}

        tmp_path = HEARTBEAT_PATH.with_suffix(HEARTBEAT_PATH.suffix + ".tmp")
        tmp_path.write_text(json.dumps(record) + "\n")
        os.replace(tmp_path, HEARTBEAT_PATH)