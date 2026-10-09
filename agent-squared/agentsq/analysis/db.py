"""SQLite mirror of the experiment results.

The JSON files stay the source of truth; this database is a cache that can be
deleted and rebuilt at any time. ``sync`` is idempotent and keyed on each
source file's (mtime, size), so calling it on every request is cheap, and every
family under runs/ -- graph_runs, mcp_runs, whatever lands next -- is picked up
without a code change. Runs are keyed by (experiment, run) because run ids are
only unique within a family.
"""

import json
import sqlite3
import time
from pathlib import Path

from agentsq.analysis.results import RUNS_ROOT, iter_results, parse_result
from agentsq.settings import ROOT

DB_PATH = ROOT / "runs" / "experiments.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    experiment         TEXT NOT NULL,
    run                TEXT NOT NULL,
    batch              INTEGER,
    trial              INTEGER,
    condition          TEXT,
    agent_model        TEXT,
    monitor_model      TEXT,
    effort             TEXT,
    topos              INTEGER,
    started            TEXT,
    parsed             INTEGER,
    question_id        TEXT,
    question_title     TEXT,
    n_steps            INTEGER,
    n_body_steps       INTEGER,
    final_phase        TEXT,
    n_stuck            INTEGER,
    stuck_share        REAL,
    n_completed_labels INTEGER,
    agent_answer       TEXT,
    answer_len         INTEGER,
    n_sources          INTEGER,
    research_loops     INTEGER,
    mcp_call_count     INTEGER,
    mcp_faulted_count  INTEGER,
    faulted_share      REAL,
    has_tokens         INTEGER,
    agent_input        INTEGER,
    agent_output       INTEGER,
    agent_reasoning    INTEGER,
    agent_visible_output INTEGER,
    agent_total        INTEGER,
    monitor_input      INTEGER,
    monitor_output     INTEGER,
    monitor_reasoning  INTEGER,
    monitor_visible_output INTEGER,
    monitor_total      INTEGER,
    monitor_agent_ratio REAL,
    extras             TEXT,
    source_path        TEXT,
    source_mtime       REAL,
    source_size        INTEGER,
    ingested_at        REAL,
    PRIMARY KEY (experiment, run)
);

CREATE TABLE IF NOT EXISTS steps (
    experiment    TEXT NOT NULL,
    run           TEXT NOT NULL,
    i             INTEGER NOT NULL,
    pos           REAL,
    phase         TEXT,
    next_phase    TEXT,
    justification TEXT,
    summary       TEXT,
    raw_summary   TEXT,
    hedged        INTEGER,
    fail_lang     INTEGER,
    PRIMARY KEY (experiment, run, i)
);

CREATE TABLE IF NOT EXISTS calls (
    experiment TEXT NOT NULL,
    run        TEXT NOT NULL,
    idx        INTEGER NOT NULL,
    pos        REAL,
    tool       TEXT,
    faulted    INTEGER,
    arguments  TEXT,
    PRIMARY KEY (experiment, run, idx)
);

CREATE TABLE IF NOT EXISTS sources (
    experiment TEXT NOT NULL,
    run        TEXT NOT NULL,
    i          INTEGER NOT NULL,
    title      TEXT,
    url        TEXT,
    PRIMARY KEY (experiment, run, i)
);

CREATE TABLE IF NOT EXISTS tool_counts (
    experiment TEXT NOT NULL,
    run        TEXT NOT NULL,
    tool       TEXT NOT NULL,
    n          INTEGER,
    PRIMARY KEY (experiment, run, tool)
);

CREATE INDEX IF NOT EXISTS steps_run   ON steps (experiment, run);
CREATE INDEX IF NOT EXISTS calls_run   ON calls (experiment, run);
CREATE INDEX IF NOT EXISTS sources_run ON sources (experiment, run);
CREATE INDEX IF NOT EXISTS runs_exp    ON runs (experiment);
"""

RUN_COLS = [
    "experiment", "run", "batch", "trial", "condition", "agent_model",
    "monitor_model", "effort", "topos", "started", "parsed", "question_id",
    "question_title", "n_steps", "n_body_steps", "final_phase", "n_stuck",
    "stuck_share", "n_completed_labels", "agent_answer", "answer_len",
    "n_sources", "research_loops", "mcp_call_count", "mcp_faulted_count",
    "faulted_share", "has_tokens", "agent_input", "agent_output",
    "agent_reasoning", "agent_visible_output", "agent_total", "monitor_input",
    "monitor_output", "monitor_reasoning", "monitor_visible_output",
    "monitor_total", "monitor_agent_ratio", "extras", "source_path",
    "source_mtime", "source_size", "ingested_at",
]

TABLES = ("steps", "calls", "sources", "tool_counts", "runs")


def connect(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _delete_run(conn, experiment, name):
    for table in TABLES:
        conn.execute(f"DELETE FROM {table} WHERE experiment = ? AND run = ?",
                     (experiment, name))


def _insert(conn, experiment, name, path, rec, stat):
    run, steps, calls, sources = parse_result(experiment, name, rec)
    tool_counts = run.pop("tool_counts")
    run["extras"] = json.dumps(run.get("extras") or {})
    run.update(source_path=str(path), source_mtime=stat.st_mtime,
               source_size=stat.st_size, ingested_at=time.time())
    run["topos"] = None if run["topos"] is None else int(run["topos"])
    run["parsed"] = int(run["parsed"])
    run["has_tokens"] = int(run["has_tokens"])

    conn.execute(
        f"INSERT INTO runs ({','.join(RUN_COLS)}) "
        f"VALUES ({','.join('?' * len(RUN_COLS))})",
        [run.get(c) for c in RUN_COLS])
    conn.executemany(
        "INSERT INTO steps (experiment,run,i,pos,phase,next_phase,justification,"
        "summary,raw_summary,hedged,fail_lang) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(s["experiment"], s["run"], s["i"], s["pos"], s["phase"], s["next_phase"],
          s["justification"], s["summary"], s["raw_summary"], int(s["hedged"]),
          int(s["fail_lang"])) for s in steps])
    conn.executemany(
        "INSERT INTO calls (experiment,run,idx,pos,tool,faulted,arguments) "
        "VALUES (?,?,?,?,?,?,?)",
        [(c["experiment"], c["run"], c["index"], c["pos"], c["tool"],
          int(c["faulted"]), c["arguments"]) for c in calls])
    conn.executemany(
        "INSERT INTO sources (experiment,run,i,title,url) VALUES (?,?,?,?,?)",
        [(s["experiment"], s["run"], s["i"], s["title"], s["url"]) for s in sources])
    conn.executemany(
        "INSERT INTO tool_counts (experiment,run,tool,n) VALUES (?,?,?,?)",
        [(experiment, name, t, n) for t, n in tool_counts.items()])


def sync(conn, runs_root=RUNS_ROOT, prune=True):
    """Ingest new or changed results files across every experiment family.

    A run is re-ingested when its source file's mtime or size has moved, and
    (with prune) dropped when its source file is gone -- the database mirrors
    whatever is on disk right now.
    """
    known = {(r["experiment"], r["run"]): (r["source_mtime"], r["source_size"])
             for r in conn.execute(
                 "SELECT experiment, run, source_mtime, source_size FROM runs")}
    seen, added, updated = set(), [], []

    for fam, name, path, rec in iter_results(runs_root):
        key = (fam, name)
        seen.add(key)
        stat = path.stat()
        prev = known.get(key)
        if prev is None:
            _insert(conn, fam, name, path, rec, stat)
            added.append(f"{fam}/{name}")
        elif prev != (stat.st_mtime, stat.st_size):
            _delete_run(conn, fam, name)
            _insert(conn, fam, name, path, rec, stat)
            updated.append(f"{fam}/{name}")

    removed = []
    if prune:
        for fam, name in known.keys() - seen:
            _delete_run(conn, fam, name)
            removed.append(f"{fam}/{name}")

    conn.commit()
    return {"added": sorted(added), "updated": sorted(updated),
            "removed": sorted(removed), "total": len(seen)}


# --- queries ---------------------------------------------------------------
# The webapp reads only through these, so the storage choice stays swappable.

def _rows(conn, sql, args=()):
    return [dict(r) for r in conn.execute(sql, args)]


def _where(experiment, run=None):
    clauses, args = [], []
    if experiment:
        clauses.append("experiment = ?")
        args.append(experiment)
    if run:
        clauses.append("run = ?")
        args.append(run)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), tuple(args)


def experiments(conn):
    """One row per family, with enough counts to label a tab."""
    rows = _rows(conn, """
        SELECT experiment,
               count(*)                AS n_runs,
               sum(n_steps)            AS n_steps,
               sum(coalesce(mcp_call_count, 0)) AS n_calls,
               sum(has_tokens)         AS n_with_tokens,
               sum(coalesce(mcp_faulted_count, 0)) AS n_faulted,
               max(started)            AS latest
          FROM runs
      GROUP BY experiment
      ORDER BY experiment
    """)
    for r in rows:
        r["has_calls"] = bool(r["n_calls"])
        r["has_tokens"] = bool(r["n_with_tokens"])
    return rows


def all_runs(conn, experiment=None):
    where, args = _where(experiment)
    runs = _rows(conn, "SELECT * FROM runs" + where +
                 " ORDER BY experiment, batch, trial, run", args)
    counts = {}
    for r in conn.execute("SELECT experiment, run, tool, n FROM tool_counts" + where, args):
        counts.setdefault((r["experiment"], r["run"]), {})[r["tool"]] = r["n"]
    for r in runs:
        r["tool_counts"] = counts.get((r["experiment"], r["run"]), {})
        r["topos"] = bool(r["topos"]) if r["topos"] is not None else None
        r["parsed"] = bool(r["parsed"])
        r["has_tokens"] = bool(r["has_tokens"])
        r["extras"] = json.loads(r["extras"] or "{}")
        r.pop("agent_answer", None)      # kept out of list payloads; large
    return runs


def steps_for(conn, experiment=None, run=None):
    where, args = _where(experiment, run)
    rows = _rows(conn, "SELECT * FROM steps" + where +
                 " ORDER BY experiment, run, i", args)
    for r in rows:
        r["hedged"] = bool(r["hedged"])
        r["fail_lang"] = bool(r["fail_lang"])
    return rows


def calls_for(conn, experiment=None, run=None):
    where, args = _where(experiment, run)
    rows = _rows(conn, "SELECT * FROM calls" + where +
                 " ORDER BY experiment, run, idx", args)
    for r in rows:
        r["faulted"] = bool(r["faulted"])
        r["index"] = r.pop("idx")
    return rows


def sources_for(conn, experiment=None, run=None):
    where, args = _where(experiment, run)
    return _rows(conn, "SELECT * FROM sources" + where +
                 " ORDER BY experiment, run, i", args)


TASKS_DIR = ROOT / "data" / "tasks"


def task_index(tasks_dir=TASKS_DIR):
    """question_id -> {"prompt", "answer"} from every task file; answer is optional."""
    out = {}
    for path in sorted(Path(tasks_dir).glob("*.json")):
        try:
            tasks = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for task in tasks.values() if isinstance(tasks, dict) else []:
            if isinstance(task, dict) and task.get("question_id"):
                entry = out.setdefault(task["question_id"], {})
                if "prompt" in task:
                    entry["prompt"] = str(task["prompt"])
                if "answer" in task:
                    entry["answer"] = str(task["answer"])
    return out


def run_detail(conn, experiment, run):
    row = conn.execute("SELECT * FROM runs WHERE experiment = ? AND run = ?",
                       (experiment, run)).fetchone()
    if row is None:
        return None
    detail = dict(row)
    task = task_index().get(detail["question_id"], {})
    detail["prompt"] = task.get("prompt")
    detail["expected_answer"] = task.get("answer")
    detail["topos"] = bool(detail["topos"]) if detail["topos"] is not None else None
    detail["parsed"] = bool(detail["parsed"])
    detail["has_tokens"] = bool(detail["has_tokens"])
    detail["extras"] = json.loads(detail["extras"] or "{}")
    detail["tool_counts"] = {r["tool"]: r["n"] for r in conn.execute(
        "SELECT tool, n FROM tool_counts WHERE experiment = ? AND run = ?",
        (experiment, run))}
    detail["steps"] = steps_for(conn, experiment, run)
    detail["calls"] = calls_for(conn, experiment, run)
    detail["sources"] = sources_for(conn, experiment, run)
    return detail


def payload(conn, experiment=None):
    """Everything the dashboard needs for one experiment, in one document."""
    return {"generated_at": time.time(),
            "experiment": experiment,
            "experiments": experiments(conn),
            "runs": all_runs(conn, experiment),
            "steps": steps_for(conn, experiment),
            "calls": calls_for(conn, experiment)}


def main(argv=None):
    import argparse

    p = argparse.ArgumentParser(description="sync experiment results into sqlite")
    p.add_argument("--runs-root", type=Path, default=RUNS_ROOT)
    p.add_argument("--db", type=Path, default=DB_PATH)
    p.add_argument("--rebuild", action="store_true",
                   help="delete the database file first")
    p.add_argument("--no-prune", dest="prune", action="store_false",
                   help="keep rows whose source file has disappeared")
    p.add_argument("--quiet", action="store_true", help="counts only")
    args = p.parse_args(argv)

    if args.rebuild and args.db.exists():
        args.db.unlink()
    conn = connect(args.db)
    report = sync(conn, args.runs_root, prune=args.prune)
    counts = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
              for t in ("runs", "steps", "calls", "sources")}
    print(f"{args.db}: {report['total']} run(s) on disk | "
          f"+{len(report['added'])} new, ~{len(report['updated'])} updated, "
          f"-{len(report['removed'])} removed")
    print("  rows:", json.dumps(counts))
    for e in experiments(conn):
        print(f"  {e['experiment']:12} {e['n_runs']:>3} runs  "
              f"{e['n_steps']:>4} steps  {e['n_calls']:>4} calls"
              f"{'  (tokens)' if e['has_tokens'] else ''}")
    if not args.quiet:
        for label in ("added", "updated", "removed"):
            for name in report[label]:
                print(f"  {label:8} {name}")
    conn.close()


if __name__ == "__main__":
    main()
