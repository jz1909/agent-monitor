import argparse
import asyncio
import subprocess
from dataclasses import replace
import sys
from datetime import datetime
from pathlib import Path

from langchain.chat_models import init_chat_model
from openai import AsyncOpenAI

from agentsq.experiments import REGISTRY, get
from agentsq.monitor.loop import Monitor
from agentsq.monitor.pipeline import build_chain
from agentsq.settings import ROOT, run_dir
from agentsq.tasks import append_results, load_tasks
from agentsq.workflows.deep_researcher.graph import MAX_RETRIES, REQUEST_TIMEOUT, log


def parse_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path)
    p.add_argument("--experiment", required=True, choices=sorted(REGISTRY))
    p.add_argument("--run-id")
    p.add_argument("--agent-model")
    p.add_argument("--monitor-model")
    p.add_argument("--reasoning-effort")
    p.add_argument("--search-version", choices=["baseline", "broken", "limited"])
    p.add_argument("--use-topos", action=argparse.BooleanOptionalAction)
    p.add_argument("--cluster", choices=['SOPHIA', 'MINERVA'])
    return p.parse_args(argv)


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

    overrides = {
        "agent_model": args.agent_model,
        "monitor_model": args.monitor_model,
        "reasoning_effort": args.reasoning_effort,
        "search_version": args.search_version,
        "use_topos": args.use_topos,
        "cluster": args.cluster
    }
    experiment = replace(get(args.experiment), **{k: v for k, v in overrides.items() if v is not None})

    tasks = load_tasks(args.input)
    output = args.output or rd / "results.jsonl"

    chain = build_chain()
    client = AsyncOpenAI()

    monitor_kwargs = {}
    if experiment.inference_provider == 'ALCF':
        if experiment.cluster is None:
            raise ValueError("ALCF experiments need --cluster (SOPHIA or MINERVA)")
        from inference_auth_token import get_access_token
        from agentsq.agent.run_cont_stream import BASE_URLS
        monitor_kwargs = dict(model_provider='openai', base_url=BASE_URLS[experiment.cluster], api_key=get_access_token())

    monitor_llm = init_chat_model(
        experiment.monitor_model,
        timeout=REQUEST_TIMEOUT,
        max_retries=MAX_RETRIES,
        **monitor_kwargs
    )

    sem = asyncio.Semaphore(experiment.concurrency)
    lock = asyncio.Lock()

    async def run_one(task):
        monitor = Monitor(chain, experiment.snapshot_window, monitor_llm=monitor_llm)
        async with sem:
            try:
                result = await experiment.runner(task, experiment, monitor, client, rd)
            except Exception as e:
                # one task crashing must not cancel the rest of the run
                result = {"question_id": task.get("question_id"),
                          "question_title": task.get("question_title"),
                          "error": repr(e)}
        async with lock:
            append_results(output, [result])
            status = "FAILED" if "error" in result else "done"
            print(f"[{rd.name}] {status}: {task.get('question_id')}", flush=True)

    await asyncio.gather(*(run_one(task) for task in tasks))


async def run(args):
    rd = run_dir(args.run_id or f"{args.experiment}-{datetime.now():%Y%m%d-%H%M%S}")
    print(f"run dir: {rd}", flush=True)

    watchdog_proc = start_watchdog(rd) if get(args.experiment).watchdog else None
    try:
        await main_async(args, rd)
    finally:
        if watchdog_proc is not None:
            stop_watchdog(watchdog_proc)


def main(argv=None):
    asyncio.run(run(parse_args(argv)))


if __name__ == "__main__":
    main()
