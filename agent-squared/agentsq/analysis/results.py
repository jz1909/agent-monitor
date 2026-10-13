"""Parsing for experiment results.

One place that knows the shape of ``results.jsonl``, shared by the sqlite sync
and the notebooks, so the two cannot drift when the record changes again.

Every top-level folder under ``runs/`` is an experiment family, and the
families do not agree on fields: graph runs carry token accounting and a
research loop count, mcp runs carry a tool-call log, the legacy heartbeat run
carries neither. The core (phases, analysis, summaries) is common, so it gets
real columns; anything family-specific is kept as well but stays optional, and
unrecognised keys survive in ``extras`` rather than being dropped.
"""

import json
import re
from pathlib import Path

from agentsq.settings import ROOT

RUNS_ROOT = ROOT / "runs"

# Known levels are hints, not a whitelist: parse_run_id works from the right so
# an unseen model or effort still parses.
MODELS = ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol", "gpt-5-nano",
          "gpt-oss-120b", "gpt-oss-20b", "inkling-bf16", "nemotron-3-ultra"]
CLUSTERS = {"sophia", "minerva"}

# A results.jsonl holds one line per task. When a run has several, each task
# becomes its own row, named "<run dir>~<line index>".
TASK_SEP = "~"
TOOLS = ["tavily_search", "tavily_research", "tavily_extract",
         "tavily_crawl", "tavily_map"]

# Fields consumed below; whatever else a record carries lands in extras.
KNOWN_KEYS = {
    "question_id", "question_title", "agent_answer", "phase_count",
    "final_phase", "phase_history", "analysis_log", "summary_log",
    "raw_summary_log", "tool_call", "research_loop_count", "agent_tokens",
    "monitor_tokens", "mcp_call_count", "mcp_tool_counts", "mcp_faulted_count",
    "mcp_call_log", "correct",
}

# Hedging language in the monitor's justification: near-miss STUCK calls.
HEDGE_RE = re.compile(
    r"limited progress|little progress|slow progress|repeat|repetiti|"
    r"no convergence|not converging|circular|loop(?:ing)?\b|redundan|"
    r"marginal|stalling|stagnat|diminishing", re.I)

# Search-failure language in the agent's own summary.
FAIL_RE = re.compile(
    r"search error|\berrors?\b|timed? ?out|timeout|no results|no relevant|"
    r"irrelevant|unrelated|off-topic|failed to (?:fetch|retrieve)|"
    r"could not (?:fetch|retrieve|find)|404|blocked|unavailable", re.I)

SOURCE_RE = re.compile(r"^\s*[*-]\s*(?P<title>.*?)\s*:\s*(?P<url>https?://\S+)\s*$")
_MODELISH = re.compile(r"^(?:gpt|claude|o\d|llama|qwen|grok|inkling|nemotron)[\w.\-]*$", re.I)
# "broken-batch2", "batch-1", "batch_3": the folder's batch number
_FOLDER_BATCH = re.compile(r"batch[-_]?(\d+)", re.I)


def split_models(mid):
    """Split 'agent-monitor' where both halves may contain '-' and '.'."""
    for agent in sorted(MODELS, key=len, reverse=True):
        if mid.startswith(agent + "-") and mid[len(agent) + 1:] in MODELS:
            return agent, mid[len(agent) + 1:]
    # unknown model: fall back to any split where both halves look like models
    parts = mid.split("-")
    for k in range(1, len(parts)):
        a, b = "-".join(parts[:k]), "-".join(parts[k:])
        if _MODELISH.match(a) and _MODELISH.match(b):
            return a, b
    return None, None


def parse_run_id(name):
    """Pull metadata out of a run directory name.

    Parsed from the right (date, time, an optional cluster, then topos and
    effort) so new models, efforts and conditions do not need a code change. Returns
    None-ish fields rather than raising, so one odd directory -- the legacy
    heartbeat run is not named like a sweep cell at all -- cannot stop a sync.
    """
    meta = dict(batch=None, trial=None, condition=None, agent_model=None,
                monitor_model=None, effort=None, topos=None, started=None,
                cluster=None, parsed=False)
    parts = name.split("-")
    if len(parts) >= 3 and parts[-3] in CLUSTERS:
        meta["cluster"] = parts.pop(-3).upper()
    if len(parts) < 8 or not re.fullmatch(r"\d{8}", parts[-2]) \
            or not re.fullmatch(r"\d{6}", parts[-1]):
        return meta
    head = parts[:-4]
    if not re.fullmatch(r"batch\d+", head[0]) or not head[1].isdigit():
        return meta
    agent, monitor = split_models("-".join(head[3:]))
    meta.update(batch=int(head[0][5:]), trial=int(head[1]), condition=head[2],
                agent_model=agent, monitor_model=monitor, effort=parts[-4],
                topos=(parts[-3] == "topos"),
                started=parts[-2] + "-" + parts[-1],
                parsed=agent is not None)
    return meta


def parse_sources(answer):
    """Sources listed under a '## Sources' heading in the agent's answer."""
    lines = (answer or "").splitlines()
    start = next((i for i, l in enumerate(lines)
                  if re.match(r"\s*#{1,4}\s*sources?\s*:?\s*$", l, re.I)), None)
    if start is None:
        return []
    out = []
    for l in lines[start + 1:]:
        m = SOURCE_RE.match(l)
        if m:
            out.append((m.group("title"), m.group("url")))
        elif l.strip().startswith("#"):
            break
    return out


def _tokens(d):
    """Flatten a token dict keyed by versioned model names."""
    inp = out = rea = 0
    for v in (d or {}).values():
        inp += v.get("input_tokens", 0) or 0
        out += v.get("output_tokens", 0) or 0
        rea += (v.get("output_token_details") or {}).get("reasoning", 0) or 0
    return {"input": inp, "output": out, "reasoning": rea,
            "visible_output": max(out - rea, 0), "total": inp + out}


def read_records(path):
    """Every JSON object in a results.jsonl, one per task, in finish order.

    A run still in progress may be mid-append, so an unparseable line is
    skipped rather than failing the whole file.
    """
    records = []
    with open(path) as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def run_folders(experiment, path):
    """The folders between the family folder and the run folder.

    runs/benchmark_runs/broken-batch2/inkling/<run>/results.jsonl gives
    ("broken-batch2", "inkling"); a results.jsonl directly in the family
    folder gives ().
    """
    parts = Path(path).parent.parts
    if parts and parts[-1] == experiment:
        return ()
    idx = max((i for i, p in enumerate(parts[:-1]) if p == experiment), default=None)
    return tuple(parts[idx + 1:-1]) if idx is not None else ()


def parse_location(folders):
    """Grouping taken from where a run sits on disk, not from its name.

    The first folder is the run group (a batch, or condition-batch for the
    benchmark runs) and carries the question batch; the second, when there is
    one, is the model the runs are filed under. The folder's batch wins over
    the one in the run id, which the benchmark script always writes as batch1.
    """
    group = folders[0] if folders else None
    m = _FOLDER_BATCH.search(group or "")
    return {"run_group": group,
            "model_group": folders[1] if len(folders) > 1 else None,
            "folder_batch": int(m.group(1)) if m else None}


def parse_result(experiment, name, rec, folders=()):
    """Turn one raw record into (run, steps, calls, sources) plain dicts."""
    ph = rec.get("phase_history") or []
    alog = rec.get("analysis_log") or []
    slog = rec.get("summary_log") or []
    rlog = rec.get("raw_summary_log") or []
    clog = rec.get("mcp_call_log") or []
    counts = rec.get("mcp_tool_counts") or {}
    tool_call = rec.get("tool_call") or []

    body = [p for p in ph if p != "COMPLETED"]   # the end marker is not a step
    n_calls = len(clog)
    n_faulted = sum(bool(c.get("faulted")) for c in clog)
    answer = rec.get("agent_answer") or ""
    srcs = parse_sources(answer)

    at, mt = _tokens(rec.get("agent_tokens")), _tokens(rec.get("monitor_tokens"))
    has_tokens = bool(rec.get("agent_tokens") or rec.get("monitor_tokens"))

    run_id, _, task = name.partition(TASK_SEP)
    meta, loc = parse_run_id(run_id), parse_location(folders)
    folder_batch = loc.pop("folder_batch")
    if folder_batch is not None:
        meta["batch"] = folder_batch
    run = {
        "experiment": experiment,
        "run": name,
        **meta,
        **loc,
        "task": int(task) if task else 0,
        "question_id": rec.get("question_id"),
        "question_title": rec.get("question_title"),
        # hand-graded answer: True / False, None until someone checks it
        "correct": rec.get("correct") if isinstance(rec.get("correct"), bool) else None,
        "n_steps": len(ph),
        "n_body_steps": len(body),
        "final_phase": rec.get("final_phase"),
        "n_stuck": sum(p == "STUCK" for p in body),
        "stuck_share": (sum(p == "STUCK" for p in body) / len(body)) if body else None,
        "n_completed_labels": sum(p == "COMPLETED" for p in ph),
        "agent_answer": answer,
        "answer_len": len(answer),
        "n_sources": len(srcs),
        "research_loops": rec.get("research_loop_count"),
        # mcp-only; a family without a call log reports no calls rather than zero
        "mcp_call_count": rec.get("mcp_call_count") if clog or "mcp_call_count" in rec else None,
        "mcp_faulted_count": rec.get("mcp_faulted_count", n_faulted) if clog else None,
        "faulted_share": (n_faulted / n_calls) if n_calls else None,
        # graph-only
        "has_tokens": has_tokens,
        **{f"agent_{k}": (v if has_tokens else None) for k, v in at.items()},
        **{f"monitor_{k}": (v if has_tokens else None) for k, v in mt.items()},
        "monitor_agent_ratio": (mt["total"] / at["total"]) if at["total"] else None,
        "tool_counts": {t: int(n) for t, n in counts.items()},
        "extras": {k: v for k, v in rec.items() if k not in KNOWN_KEYS},
    }

    steps = [{
        "experiment": experiment,
        "run": name,
        "i": i,
        "pos": i / (len(ph) - 1) if len(ph) > 1 else 0.0,
        "phase": phase,
        "next_phase": ph[i + 1] if i + 1 < len(ph) else None,
        "justification": alog[i] if i < len(alog) else "",
        "summary": slog[i] if i < len(slog) else "",
        "raw_summary": rlog[i] if i < len(rlog) else "",
        "hedged": bool(HEDGE_RE.search(alog[i] if i < len(alog) else "")),
        "fail_lang": bool(FAIL_RE.search(slog[i] if i < len(slog) else "")),
    } for i, phase in enumerate(ph)]

    # Tool calls run on their own clock: the record carries no link between a
    # call and the phase index it happened under, so index is all we have.
    # mcp runs log arguments and fault status; older families log only names.
    if clog:
        calls = [{
            "experiment": experiment, "run": name,
            "index": c.get("index", j + 1),
            "pos": j / (n_calls - 1) if n_calls > 1 else 0.0,
            "tool": c.get("tool"),
            "faulted": bool(c.get("faulted")),
            "arguments": c.get("arguments", ""),
        } for j, c in enumerate(clog)]
    else:
        calls = [{
            "experiment": experiment, "run": name, "index": j + 1,
            "pos": j / (len(tool_call) - 1) if len(tool_call) > 1 else 0.0,
            "tool": t, "faulted": False, "arguments": "",
        } for j, t in enumerate(tool_call)]
        if calls:
            run["mcp_call_count"] = len(calls)

    sources = [{"experiment": experiment, "run": name, "i": i,
                "title": t, "url": u} for i, (t, u) in enumerate(srcs)]

    return run, steps, calls, sources


def iter_experiments(runs_root=RUNS_ROOT):
    """Every top-level folder under runs/ that holds at least one result."""
    for d in sorted(Path(runs_root).iterdir()):
        if d.is_dir() and not d.name.startswith(".") and any(d.rglob("results.jsonl")):
            yield d.name, d


def iter_results(runs_root=RUNS_ROOT, experiment=None):
    """Yield (experiment, run_name, path, record) for every task record.

    Recursive within each family, so a new batch folder dropped in is picked up
    with no change here. The run name is the containing directory, except for a
    results.jsonl sitting directly in the family folder, which is the family;
    a file holding several tasks gets a TASK_SEP suffix per task.
    """
    for fam, d in iter_experiments(runs_root):
        if experiment and fam != experiment:
            continue
        for path in sorted(d.rglob("results.jsonl")):
            records = read_records(path)
            base = fam if path.parent == d else path.parent.name
            for i, rec in enumerate(records):
                name = base if len(records) == 1 else f"{base}{TASK_SEP}{i}"
                yield fam, name, path, rec


def load(runs_root=RUNS_ROOT, experiment=None):
    """The frames, for notebook use. Imports pandas lazily."""
    import pandas as pd

    run_rows, step_rows, call_rows, src_rows = [], [], [], []
    for fam, name, path, rec in iter_results(runs_root, experiment):
        run, steps, calls, sources = parse_result(fam, name, rec,
                                                  run_folders(fam, path))
        run.update(run.pop("tool_counts"))
        run.pop("extras")
        run_rows.append(run)
        step_rows.extend(steps)
        call_rows.extend(calls)
        src_rows.extend(sources)

    runs = pd.DataFrame(run_rows).sort_values(
        ["experiment", "batch", "run_group", "model_group", "trial", "task"],
        na_position="first").reset_index(drop=True)
    for t in TOOLS:
        if t not in runs:
            runs[t] = 0
        runs[t] = runs[t].fillna(0).astype(int)
    steps = pd.DataFrame(step_rows)
    calls = pd.DataFrame(call_rows)
    steps["is_body"] = steps["phase"] != "COMPLETED"
    return runs, steps, calls, pd.DataFrame(src_rows)
