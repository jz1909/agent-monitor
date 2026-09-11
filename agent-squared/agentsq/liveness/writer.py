import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class HeartbeatWriter:

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.frame_id = uuid4().hex
        self.beat_count = 0

    def beat(self):
        self.beat_count += 1
        record = {
            "time_utc": datetime.now(timezone.utc).isoformat(),
            "frame_id": self.frame_id,
        }

        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(record) + "\n")
        os.replace(tmp_path, self.path)
