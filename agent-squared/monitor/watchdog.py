from datetime import datetime, timezone
import json
from hb_config import status, HEARTBEAT_PATH, WARNING_AFTER_SECONDS, REPORT_FILE


def classify(hb_time):

    curr_time = datetime.now(timezone.utc)
    hb_dt = datetime.fromisoformat(hb_time)
    age_seconds = (curr_time - hb_dt).total_seconds()

    if age_seconds >= WARNING_AFTER_SECONDS:
        return (age_seconds, status.DEAD)
    return (age_seconds, status.OK)

def read_hb():
    with open(HEARTBEAT_PATH, 'r') as hb_file:
        hb_data = json.load(hb_file)

    hb_time = hb_data['time_utc']
    return hb_time

def write_liveness():
    hb_time = read_hb()
    last_hb_time, curr_status = classify(hb_time)

    record = {"status":curr_status, "hb_time": last_hb_time}
    with open(REPORT_FILE, 'a') as report_file:
        report_file.write(json.dumps(record) + "\n")


    



    



