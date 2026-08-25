from datetime import datetime, timezone
import json
import os
import time
from uuid import uuid4

from hb_config import (
    status,
    HEARTBEAT_PATH,
    WARNING_AFTER_SECONDS,
    CHECK_INTERVAL_SECONDS,
    REPORT_FILE,
)


def classify(age_seconds):
    if age_seconds is None or age_seconds >= WARNING_AFTER_SECONDS:
        return status.DEAD
    return status.OK


def read_hb():
    
    with open(HEARTBEAT_PATH, 'r') as hb_file:
        hb_data = json.load(hb_file)
    hb_dt = datetime.fromisoformat(hb_data['time_utc'])
    

    if hb_dt.tzinfo is None:
        hb_dt = hb_dt.replace(tzinfo=timezone.utc)

    age_seconds = (datetime.now(timezone.utc) - hb_dt).total_seconds()
    return age_seconds, hb_data.get('frame_id')



def emit(record):
    print(f"{record['status']} age={record['age_seconds']} frame={record['frame_id']}", flush=True)
    with open(REPORT_FILE, 'a') as report_file:
        report_file.write(json.dumps(record) + "\n")


def check_once(prev_frame_id):
    age_seconds, frame_id = read_hb()
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

    wd_frame_id = uuid4().hex
    prev_frame_id = None
    
    while True:
        record, frame_id = check_once(prev_frame_id)
        if frame_id is not None:
            prev_frame_id = frame_id
        emit(record)
        time.sleep(CHECK_INTERVAL_SECONDS)
   


if __name__ == "__main__":
    main()
