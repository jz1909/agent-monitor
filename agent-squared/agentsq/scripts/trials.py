import argparse
import asyncio
import sys
from datetime import datetime

from agentsq.cli import parse_args as parse_cli_args, run

input_path = "data/tasks/deep_research_topics.json"

NANO, LUNA, TERRA = 'gpt-5-nano', 'gpt-5.6-luna', 'gpt-5.6-terra'


def trial(search_version, main, monitor, reasoning, topos):
    return {'experiment': 'graph-topo', 'main': main, 'monitor': monitor, 'reasoning': reasoning, 'search_version': search_version, 'topos': topos}


batch1 = [
    trial('baseline', NANO, NANO, 'low', True),
    trial('broken', NANO, LUNA, 'medium', True),
    trial('limited', NANO, TERRA, 'high', True),
]

batch2 = [
    trial('broken', LUNA, NANO, 'low', True),
    trial('limited', LUNA, LUNA, 'medium', True),
    trial('baseline', LUNA, TERRA, 'high', True),
]

batch3 = [
    trial('baseline', TERRA, NANO, 'medium', True),
    trial('broken', TERRA, LUNA, 'high', True),
    trial('limited', TERRA, TERRA, 'low', True),
]

batch4 = [
    trial('limited', NANO, NANO, 'high', False),
    trial('baseline', NANO, LUNA, 'low', False),
    trial('broken', NANO, TERRA, 'medium', False),
]

batch5 = [
    trial('limited', LUNA, NANO, 'medium', False),
    trial('baseline', LUNA, LUNA, 'high', False),
    trial('broken', LUNA, TERRA, 'low', False),
]

batch6 = [
    trial('broken', TERRA, NANO, 'high', False),
    trial('limited', TERRA, LUNA, 'low', False),
    trial('baseline', TERRA, TERRA, 'medium', False),
]

BATCHES = {f"batch{i}": b for i, b in enumerate([batch1, batch2, batch3, batch4, batch5, batch6], start=1)}


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
        sys.exit("set input_path in trials.py first")
    asyncio.run(main_async(args.batch, args.trial))


if __name__ == "__main__":
    main()
