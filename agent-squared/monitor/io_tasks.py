import json


def load_tasks(path)-> list[dict]:
    with open(path, "r") as f:
        tasks = json.load(f)
    return list(tasks.values())

def append_tasks(path, results: list[dict]):
    with open(path, "a") as f:
        for result in results:
            f.write(json.dumps(result) + "\n")