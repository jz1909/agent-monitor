from pathlib import Path


STATE_DIR = Path("./state")
REPORT_DIR = Path("./report")
HEARTBEAT_PATH = Path(f"{STATE_DIR}/heartbeat.json")
REPORT_FILE = Path(f"{REPORT_DIR}/report_hb.jsonl")


BEAT_PER_CHUNK = 1
WARNING_AFTER_SECONDS = 20
CHECK_INTERVAL_SECONDS = WARNING_AFTER_SECONDS
