"""
Run from the repo root:
    python -m prophet.run_experiment --backend jev --bag cumulative --batch-size 12 --limit 1
    python -m prophet.run_experiment --backend alcf --model <model-id> --cluster SOPHIA --bag sliding --k 3
"""

import argparse
import json
import time
from pathlib import Path

from dotenv import load_dotenv

# API keys (e.g. JEV_API_KEY) live in agent-monitor/.env
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from prophet.backends.Base_backend import Decision
from prophet.batch import DEFAULT_TRIALS_DIR, TokenBatcher, load_trajectories
from prophet.decision import ChoicePolicy, ThresholdPolicy
from prophet.runner import MonitorRunner
from prophet.turn_bag import CumulativeBag, SingleBag, SlidingBag
from prophet.backends.ALCF_backend import ALCFBackend
from prophet.backends.JEV_backend import JEVBackend

DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "results"

def make_backend(args):
    if args.backend == "jev":
        return JEVBackend(args.model or "jev-latest")
    if not args.model:
        raise SystemExit("--model is required for the alcf backend")
    return ALCFBackend(args.model, args.cluster)

def make_bag(args):
    if args.bag == "single":
        return SingleBag()
    if args.bag == "cumulative":
        return CumulativeBag()
    return SlidingBag(args.k)


def make_policy(args):
    if args.policy == "threshold":
        return ThresholdPolicy(args.threshold)
    return ChoicePolicy()


def run_name(args) -> str:
    bag = f"sliding{args.k}" if args.bag == "sliding" else args.bag
    policy = f"threshold{args.threshold}" if args.policy == "threshold" else args.policy
    model = (args.model or args.backend).replace("/", "-")
    # a single selected trial goes in the name, so per-trial runs in the same second don't overwrite each other
    trial = f"_{args.trials[0]}" if args.trials and len(args.trials) == 1 else ""
    return f"{model}_{bag}_{policy}_b{args.batch_size}{trial}_{time.strftime('%Y%m%d-%H%M%S')}"


def summarize(results):
    n = len(results)
    if n == 0:
        print("No results.")
        return
    decided = [r for r in results if r.correct is not None]
    abstained = sum(r.final_decision == Decision.UNSURE for r in results)
    forced = sum(r.forced for r in results)
    errors = sum(s.error is not None for r in results for s in r.steps)
    n_steps = sum(len(r.steps) for r in results)

    print(f"\n=== {n} trajectories ===")
    if decided:
        print(f"accuracy:       {sum(r.correct for r in decided) / len(decided):.1%}  ({len(decided)} decided)")
    print(f"abstained:      {abstained / n:.1%}")
    print(f"forced:         {forced / n:.1%}  (reached the end without an early YES/NO)")
    print(f"mean frac_seen: {sum(r.frac_seen for r in results) / n:.2f}")
    print(f"mean latency:   {sum(r.total_latency_s for r in results) / n:.2f}s per trajectory")
    print(f"step errors:    {errors} of {n_steps} steps")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=["jev", "alcf"], required=True)
    ap.add_argument("--model", help="model name (jev default: jev-latest; required for alcf)")
    ap.add_argument("--cluster", choices=["SOPHIA", "MINERVA"], default="SOPHIA", help="ALCF cluster")
    ap.add_argument("--bag", choices=["single", "cumulative", "sliding"], default="cumulative")
    ap.add_argument("--k", type=int, default=3, help="window size for --bag sliding")
    ap.add_argument("--batch-size", type=int, default=12, help="tokenized_input items per batch")
    ap.add_argument("--align", choices=["none", "event"], default="event")
    ap.add_argument("--policy", choices=["choice", "threshold"], default="choice")
    ap.add_argument("--threshold", type=float, default=0.9, help="for --policy threshold")
    ap.add_argument("--trials-dir", type=Path, default=DEFAULT_TRIALS_DIR)
    ap.add_argument("--agents", nargs="+", help="only these agents, e.g. claude-code terminus-2")
    ap.add_argument("--models-filter", nargs="+", help="only trajectories from these agent models")
    ap.add_argument("--trials", nargs="+", help="only these trials, by folder name or trial id")
    ap.add_argument("--limit", type=int, help="only the first N trajectories")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = ap.parse_args()

    runner = MonitorRunner(
        batcher=TokenBatcher(args.batch_size, align=args.align),
        bag=make_bag(args),
        backend=make_backend(args),
        policy=make_policy(args),
    )

    trajs = load_trajectories(
        args.trials_dir,
        models=set(args.models_filter) if args.models_filter else None,
        agents=set(args.agents) if args.agents else None,
        trials=set(args.trials) if args.trials else None,
    )[:args.limit]
    if args.trials and not trajs:
        raise SystemExit(f"no trials matched {args.trials} (check the names, and that tokenizer.py has been run)")

    # one folder per run: results/<name>/results.jsonl + config.json
    run_dir = args.out_dir / run_name(args)
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "results.jsonl"
    config = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
    (run_dir / "config.json").write_text(json.dumps(config, indent=1))
    print(f"Running {len(trajs)} trajectories -> {out_path}")

    results = []
    with open(out_path, "w") as f:
        for i, traj in enumerate(trajs, 1):
            r = runner.run(traj)
            results.append(r)
            f.write(json.dumps(r.to_dict()) + "\n")
            f.flush()  # keep finished trajectories if the run is interrupted
            print(f"  [{i}/{len(trajs)}] {r.model_name:26} label={r.label!s:5} -> "
                  f"{r.final_decision.name if r.final_decision is not None else None:6} "
                  f"step={r.stop_step} seen={r.frac_seen:.0%} forced={r.forced} correct={r.correct}")

    summarize(results)


if __name__ == "__main__":
    main()
