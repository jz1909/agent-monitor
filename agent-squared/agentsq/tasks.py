import json
from pathlib import Path


def load_tasks(path) -> list[dict]:
    with open(path, "r") as f:
        tasks = json.load(f)
    return list(tasks.values())


def append_results(path, results: list[dict]):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        for result in results:
            f.write(json.dumps(result) + "\n")
