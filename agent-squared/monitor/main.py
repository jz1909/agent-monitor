import argparse
import asyncio
from pathlib import Path


from openai import AsyncOpenAI
from graph import build_chain
from io_tasks import load_tasks, append_tasks
from runners.runner import run_task
from runners.runner_mcp import run_mcp_task


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path)
    p.add_argument("--output", type=Path)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--mcp", action="store_true")
    mode.add_argument("--plain", action="store_true")
    return p.parse_args()

async def main_async(args):
    tasks = load_tasks(args.input)

    chain = build_chain()
    client = AsyncOpenAI()

    sem = asyncio.Semaphore(10)  
    lock = asyncio.Lock()

    runner = run_mcp_task if args.mcp else run_task


    async def run_one(task):
        async with sem:
            result = await runner(task, chain, client, 1)
        async with lock:
            append_tasks(args.output, [result])
            print(f"done: {task.get('question_id')}", flush=True)

    await asyncio.gather(*(run_one(task) for task in tasks))

def main():
    args = parse_args()
    asyncio.run(main_async(args))

if __name__ == "__main__":
    main()