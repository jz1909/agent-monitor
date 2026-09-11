import argparse
import json
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

WARNING_AFTER_SECONDS = 20
CHECK_INTERVAL_SECONDS = WARNING_AFTER_SECONDS // 2


class Liveness(Enum):
    OK = 1
    DEAD = 2


def classify(age_seconds):
    if age_seconds is None or age_seconds >= WARNING_AFTER_SECONDS:
        return Liveness.DEAD
    return Liveness.OK


def read_hb(path):
    try:
        with open(path, 'r') as hb_file:
            hb_data = json.load(hb_file)
    except (FileNotFoundError, json.JSONDecodeError):
        return None, None

    hb_dt = datetime.fromisoformat(hb_data['time_utc'])
    if hb_dt.tzinfo is None:
        hb_dt = hb_dt.replace(tzinfo=timezone.utc)

    age_seconds = (datetime.now(timezone.utc) - hb_dt).total_seconds()
    return age_seconds, hb_data.get('frame_id')


def emit(record, report_path):
    print(f"{record['status']} age={record['age_seconds']} frame={record['frame_id']}", flush=True)
    with open(report_path, 'a') as report_file:
        report_file.write(json.dumps(record) + "\n")


def check_once(path, prev_frame_id):
    age_seconds, frame_id = read_hb(path)
    curr_status = classify(age_seconds)

    record = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": curr_status.name,
        "age_seconds": age_seconds,
        "frame_id": frame_id,
        "restarted": prev_frame_id is not None and frame_id is not None and frame_id != prev_frame_id,
    }
    return record, frame_id


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--heartbeat", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    prev_frame_id = None

    while True:
        record, frame_id = check_once(args.heartbeat, prev_frame_id)
        if frame_id is not None:
            prev_frame_id = frame_id
        emit(record, args.report)
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
