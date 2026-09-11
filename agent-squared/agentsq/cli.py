import argparse
import asyncio
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from openai import AsyncOpenAI

from agentsq.agent.run import run_task
from agentsq.experiments import REGISTRY, get
from agentsq.monitor.loop import Monitor
from agentsq.monitor.pipeline import build_chain
from agentsq.settings import ROOT, run_dir
from agentsq.tasks import append_results, load_tasks


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path)
    p.add_argument("--experiment", required=True, choices=sorted(REGISTRY))
    p.add_argument("--run-id")
    return p.parse_args()


def start_watchdog(rd):
    return subprocess.Popen(
        [
            sys.executable, "-m", "agentsq.liveness.watchdog",
            "--heartbeat", str(rd / "heartbeat.json"),
            "--report", str(rd / "report.jsonl"),
        ],
        cwd=ROOT,
    )


def stop_watchdog(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


async def main_async(args, rd):
    experiment = get(args.experiment)
    tasks = load_tasks(args.input)
    output = args.output or rd / "results.jsonl"

    chain = build_chain()
    client = AsyncOpenAI()

    sem = asyncio.Semaphore(experiment.concurrency)
    lock = asyncio.Lock()

    async def run_one(task):
        monitor = Monitor(chain, experiment.snapshot_window)
        async with sem:
            result = await experiment.runner(task, experiment, monitor, client, rd)
        async with lock:
            append_results(output, [result])
            print(f"done: {task.get('question_id')}", flush=True)

    await asyncio.gather(*(run_one(task) for task in tasks))


def main():
    args = parse_args()
    rd = run_dir(args.run_id or f"{args.experiment}-{datetime.now():%Y%m%d-%H%M%S}")
    print(f"run dir: {rd}", flush=True)

    watchdog_proc = start_watchdog(rd) if get(args.experiment).watchdog else None
    try:
        asyncio.run(main_async(args, rd))
    finally:
        if watchdog_proc is not None:
            stop_watchdog(watchdog_proc)


if __name__ == "__main__":
    main()
