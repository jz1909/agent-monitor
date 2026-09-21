import argparse
import asyncio
import sys
from datetime import datetime

from agentsq.cli import parse_args as parse_cli_args, run

input_path = "data/tasks/evobrowse.json"

NANO, LUNA, TERRA, SOL = 'gpt-5-nano', 'gpt-5.6-luna', 'gpt-5.6-terra', 'gpt-5.6-sol'


def trial(search_version, main, monitor, reasoning, topos):
    return {'experiment': 'mcp', 'main': main, 'monitor': monitor, 'reasoning': reasoning, 'search_version': search_version, 'topos': topos}

batch1 = [
    trial('baseline', SOL, SOL, 'max', False),
    trial('broken', SOL, SOL, 'max', False),
]

batch2 = [
    trial('baseline', TERRA, TERRA, 'max', False),
    trial('broken', TERRA, TERRA, 'max', False),
]

# nano caps out at 'high' -- 'max'/'xhigh' are rejected with a 400
batch3 = [
    trial('baseline', NANO, TERRA, 'high', False),
    trial('broken', NANO, TERRA, 'high', False),
]


BATCHES = {f"batch{i}": b for i, b in enumerate([batch1, batch2, batch3], start=1)}


def trial_argv(trial, run_id):
    argv = [
        "--input", input_path,
        "--experiment", trial['experiment'],
        "--run-id", run_id,
        "--agent-model", trial['main'],
        "--monitor-model", trial['monitor'],
        "--reasoning-effort", trial['reasoning'],
        "--search-version", trial['search_version'],
        "--use-topos" if trial['topos'] else "--no-use-topos",
    ]
    return argv


async def main_async(batch, trials=None):
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    runs = {}
    for i, t in enumerate(BATCHES[batch]):
        if trials is not None and i not in trials:
            continue
        topos = "topos" if t['topos'] else "notopos"
        run_id = f"{batch}-{i}-{t['search_version']}-{t['main']}-{t['monitor']}-{t['reasoning']}-{topos}-{stamp}"
        runs[run_id] = parse_cli_args(trial_argv(t, run_id))

    results = await asyncio.gather(*(run(args) for args in runs.values()), return_exceptions=True)

    print("\nsummary:")
    for run_id, result in zip(runs, results):
        print(f"  {'FAIL' if isinstance(result, BaseException) else 'ok  '} {run_id}" + (f": {result!r}" if isinstance(result, BaseException) else ""))
    if any(isinstance(r, BaseException) for r in results):
        sys.exit(1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("batch", choices=sorted(BATCHES))
    p.add_argument("--trial", type=int, nargs="+", help="trial indices within the batch to run (default: all)")
    args = p.parse_args()

    n = len(BATCHES[args.batch])
    if not n:
        sys.exit(f"{args.batch} is empty")
    if args.trial and any(i < 0 or i >= n for i in args.trial):
        sys.exit(f"{args.batch} has trials 0-{n - 1}, got {args.trial}")
    if not input_path:
        sys.exit("set input_path in mcp_trials.py first")
    asyncio.run(main_async(args.batch, args.trial))


if __name__ == "__main__":
    main()
