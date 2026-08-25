import argparse
import asyncio
import subprocess
import sys
from pathlib import Path


from openai import AsyncOpenAI
from graph import build_chain
from io_tasks import load_tasks, append_tasks
from runners.runner import run_task
from runners.runner_mcp import run_mcp_task
from runners.runner_hb import run_hb_task


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path)
    p.add_argument("--output", type=Path)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--mcp", action="store_true")
    mode.add_argument("--hb", action="store_true")
    mode.add_argument("--plain", action="store_true")
    return p.parse_args()

async def main_async(args):
    tasks = load_tasks(args.input)

    chain = build_chain()
    client = AsyncOpenAI()

    sem = asyncio.Semaphore(10)  
    lock = asyncio.Lock()


    if args.mcp:
        runner = run_mcp_task
    else:
        if args.hb:
            runner = run_hb_task
        else:
            runner = run_task

    async def run_one(task):
        async with sem:
            result = await runner(task, chain, client, 1)
        async with lock:
            append_tasks(args.output, [result])
            print(f"done: {task.get('question_id')}", flush=True)

    if args.mcp or not args.hb:
        await asyncio.gather(*(run_one(task) for task in tasks))
    else:
        for task in tasks:
            await run_one(task)


def start_watchdog():
    watchdog_path = Path(__file__).resolve().parent / "watchdog.py"
    proc = subprocess.Popen([sys.executable, str(watchdog_path)], cwd=watchdog_path.parent)
    return proc


def stop_watchdog(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def main():
    args = parse_args()
    watchdog_proc = start_watchdog() if args.hb else None
    try:
        asyncio.run(main_async(args))
    finally:
        if watchdog_proc is not None:
            stop_watchdog(watchdog_proc)

if __name__ == "__main__":
    main()