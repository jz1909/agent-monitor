r"""Render canonical event lists into a flat, delimiter-tokenized stream.

By default, walks ../trajectory-data/trials, finds every trial folder (one
containing result.json), builds its event list with event_list.py, and writes
<trial>/parsed_trajectory.json.

Token format (one neutral template for every model / agent):

    <|turn 3|>
    <|reasoning|>...<|/reasoning|>
    <|text|>...<|/text|>
    <|tool_call name=shell id=3.1|>{"command":"ls"}<|/tool_call|>
    <|tool_result id=3.1 error=false|>...<|/tool_result|>

Parse with:  re.split(r"(<\|/?[a-z_]+(?: [^|]*)?\|>)", text)
Literal "<|" inside content is escaped as "<\\|" so delimiters stay unambiguous.

Usage:
    python tokenizer.py                          # all trials, default folder
    python tokenizer.py --trials-dir PATH
    python tokenizer.py --no-reasoning           # strip reasoning (fair comparisons)
    python tokenizer.py --max-result-chars 4000  # truncate long tool results
"""

import argparse
import json
from pathlib import Path

from event_list import build_event_list

DEFAULT_TRIALS_DIR = Path(__file__).resolve().parents[1] / "trajectory-data" / "trials"


def escape(content):
    return content.replace("<|", "<\\|")


def truncate(content, limit):
    if limit and len(content) > limit:
        return content[:limit] + f"[...truncated {len(content) - limit} chars]"
    return content


def open_tag(e):
    meta = e["meta"]
    if e["type"] == "tool_call":
        return f"<|tool_call name={meta['name']} id={meta['call_id']}|>"
    if e["type"] == "tool_result":
        ids = ",".join(meta.get("call_ids") or []) or "none"
        return f"<|tool_result id={ids} error={str(meta.get('is_error', False)).lower()}|>"
    return f"<|{e['type']}|>"


def tokenize(events, include_reasoning=True, max_result_chars=0):
    """Return the flat token list: delimiter tokens and content chunks, in order."""
    tokens = []
    current_turn = None
    for e in events:
        if e["type"] == "reasoning" and not include_reasoning:
            continue
        # Turn markers open each LLM call; user/system input precedes them.
        if e["type"] not in ("user", "system") and e["turn"] != current_turn:
            current_turn = e["turn"]
            tokens.append(f"<|turn {current_turn}|>")
        content = e["content"]
        if e["type"] == "tool_result":
            content = truncate(content, max_result_chars)
        tokens += [open_tag(e), escape(content), f"<|/{e['type']}|>"]
    return tokens


def process_trial(trial_dir, include_reasoning, max_result_chars):
    parsed = build_event_list(trial_dir)
    header = parsed["header"]
    tokens = tokenize(parsed["events"], include_reasoning, max_result_chars)
    out = {
        "model": header["model"],
        "success": header["success"],
        **header,
        "render": {"include_reasoning": include_reasoning, "max_result_chars": max_result_chars},
        "n_events": len(parsed["events"]),
        "tokens": tokens,
        "text": "\n".join(tokens),
    }
    out_path = Path(trial_dir) / "parsed_trajectory.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    return out_path, header


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trials-dir", type=Path, default=DEFAULT_TRIALS_DIR)
    ap.add_argument("--no-reasoning", action="store_true", help="drop reasoning events from the stream")
    ap.add_argument("--max-result-chars", type=int, default=0, help="truncate tool results (0 = keep full)")
    args = ap.parse_args()

    trial_dirs = sorted(p.parent for p in args.trials_dir.rglob("result.json")
                        if (p.parent / "agent").is_dir())
    print(f"Found {len(trial_dirs)} trials in {args.trials_dir}")

    for trial_dir in trial_dirs:
        try:
            out_path, h = process_trial(trial_dir, not args.no_reasoning, args.max_result_chars)
        except Exception as exc:  # keep going; one bad trial shouldn't stop the batch
            print(f"  FAILED {trial_dir}: {exc!r}")
            continue
        print(f"  {h['model']:28} {h['agent']:12} turns={h['n_turns']:<4} "
              f"success={h['success']!s:5} reasoning={h['reasoning_visibility']:10} -> {out_path.name}")


if __name__ == "__main__":
    main()
