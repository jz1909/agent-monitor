import argparse
import asyncio
from pathlib import Path


from openai import AsyncOpenAI
from graph import build_chain
from io_tasks import load_tasks, append_tasks
from runner import run_task


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path)
    p.add_argument("--output", type=Path)
    return p.parse_args()

async def main_async(args):
    tasks = load_tasks(args.input)

    chain = build_chain()
    client = AsyncOpenAI()

    sem = asyncio.Semaphore(10)  
    lock = asyncio.Lock()


    async def run_one(task):
        async with sem:
            result = await run_task(task, chain, client, 1)
        async with lock:
            append_tasks(args.output, [result])
            print(f"done: {task.get('question_id')}", flush=True)

    await asyncio.gather(*(run_one(task) for task in tasks))

def main():
    args = parse_args()
    asyncio.run(main_async(args))

if __name__ == "__main__":
    main()