"""Convert one Harbor trial folder into a canonical, agent-agnostic event list.

Every trial becomes:
    {"header": {...trial metadata + outcome...}, "events": [ {...}, ... ]}

Each event is
    {"turn": int, "type": str, "content": str, "meta": {...}}
with type in {system, user, reasoning, text, tool_call, tool_result}.

`turn` counts LLM API calls (0-based). User / environment events carry the
turn index of the call that consumes them next. Events are in temporal order.

Adapters:
  - claude-code  -> raw session .jsonl (content blocks grouped by message.id)
  - everything else (terminus-2, qwen-code, ...) -> agent/trajectory.json (ATIF),
    with terminus-2's raw JSON completion attached from agent/episode-N/response.txt
"""

import json
import re
import sys
from pathlib import Path

# Map agent-specific tool names onto a small shared vocabulary.
TOOL_NAME_MAP = {
    "bash": "shell", "bash_command": "shell", "run_shell_command": "shell",
    "read": "read", "read_file": "read", "read_many_files": "read",
    "edit": "edit", "multiedit": "edit", "replace": "edit",
    "write": "write", "write_file": "write",
    "grep": "search", "glob": "search", "ls": "search", "grep_search": "search",
    "search_file_content": "search", "list_directory": "search",
    "todowrite": "todo", "todo_write": "todo",
    "webfetch": "web", "websearch": "web", "web_fetch": "web", "web_search": "web",
    "agent": "subagent", "task": "subagent",
    "toolsearch": "meta",
    "mark_task_complete": "submit",
}

# ATIF v1.2 appends this harness-generated suffix to tool observations.
METADATA_SUFFIX = re.compile(r"\n*\[metadata\] \{.*\}\s*$", re.DOTALL)


def normalize_tool_name(name):
    return TOOL_NAME_MAP.get(name.lower(), name.lower())


def canonical_args(args):
    """Deterministic string form of tool arguments."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return args
    return json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def event(turn, type_, content, **meta):
    return {"turn": turn, "type": type_, "content": content, "meta": meta}


def load_json(path):
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Header (trial metadata + outcome)
# ---------------------------------------------------------------------------

def build_header(trial_dir):
    result = load_json(trial_dir / "result.json")
    agent_info = result.get("agent_info") or {}
    model_info = agent_info.get("model_info") or {}
    agent_cfg = (result.get("config") or {}).get("agent") or {}

    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    reward = rewards.get("reward")

    resolved = None
    report_path = trial_dir / "verifier" / "report.json"
    if report_path.exists():
        report = load_json(report_path)
        resolved = next(iter(report.values()), {}).get("resolved")

    return {
        "trial_name": result.get("trial_name", trial_dir.name),
        "task_name": result.get("task_name"),
        "benchmark": Path((result.get("task_id") or {}).get("path", "")).parent.name or None,
        "agent": agent_info.get("name") or agent_cfg.get("name"),
        "agent_version": agent_info.get("version"),
        "model": model_info.get("name") or (agent_cfg.get("model_name") or "").split("/")[-1] or None,
        "model_provider": model_info.get("provider"),
        "reward": reward,
        "success": None if reward is None else reward >= 1.0,
        "resolved": resolved,
        "exception": result.get("exception_info"),
    }


# ---------------------------------------------------------------------------
# claude-code adapter: raw session jsonl
# ---------------------------------------------------------------------------

def find_session_jsonl(trial_dir, session_id):
    projects = trial_dir / "agent" / "sessions" / "projects"
    if not projects.exists():
        return None
    if session_id:
        hits = list(projects.glob(f"*/{session_id}.jsonl"))
        if hits:
            return hits[0]
    hits = sorted(projects.glob("*/*.jsonl"), key=lambda p: p.stat().st_size, reverse=True)
    return hits[0] if hits else None


def tool_result_text(content):
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        kind = block.get("type")
        if kind == "text":
            parts.append(block.get("text", ""))
        elif kind == "tool_reference":
            parts.append(f"[tool_reference: {block.get('tool_name')}]")
        else:
            parts.append(f"[{kind}]")
    return "\n".join(parts)


def events_from_claude_code_jsonl(path):
    events = []
    turn = -1
    current_msg_id = None
    call_ids = {}  # original tool_use id -> "turn.k"

    with open(path) as f:
        rows = [json.loads(line) for line in f if line.strip()]

    for row in rows:
        if row.get("type") not in ("user", "assistant") or row.get("isSidechain"):
            continue
        msg = row.get("message") or {}
        content = msg.get("content")

        if row["type"] == "assistant":
            if msg.get("id") != current_msg_id:
                current_msg_id = msg.get("id")
                turn += 1
                n_calls = 0
            blocks = content if isinstance(content, list) else [{"type": "text", "text": content or ""}]
            for block in blocks:
                kind = block.get("type")
                if kind == "thinking":
                    if block.get("thinking"):
                        events.append(event(turn, "reasoning", block["thinking"]))
                elif kind == "redacted_thinking":
                    events.append(event(turn, "reasoning", "[redacted]", redacted=True))
                elif kind == "text":
                    if block.get("text"):
                        events.append(event(turn, "text", block["text"]))
                elif kind == "tool_use":
                    n_calls += 1
                    cid = f"{turn}.{n_calls}"
                    call_ids[block["id"]] = cid
                    events.append(event(
                        turn, "tool_call", canonical_args(block.get("input", {})),
                        name=normalize_tool_name(block["name"]), raw_name=block["name"],
                        call_id=cid, raw_call_id=block["id"],
                    ))
            continue

        # user row: either tool results or a real user / harness message
        next_turn = turn + 1
        if isinstance(content, list) and any(b.get("type") == "tool_result" for b in content):
            for block in content:
                if block.get("type") != "tool_result":
                    continue
                raw_id = block.get("tool_use_id")
                events.append(event(
                    turn, "tool_result", tool_result_text(block.get("content")),
                    call_ids=[call_ids.get(raw_id, raw_id)], is_error=bool(block.get("is_error")),
                ))
        else:
            text = content if isinstance(content, str) else "\n".join(
                b.get("text", "") for b in content or [] if b.get("type") == "text")
            if text:
                events.append(event(next_turn, "user", text, is_meta=bool(row.get("isMeta"))))
    return events


# ---------------------------------------------------------------------------
# Generic ATIF adapter (terminus-2, qwen-code, fallback for claude-code)
# ---------------------------------------------------------------------------

def terminus_raw_completions(trial_dir):
    episodes = sorted(
        (trial_dir / "agent").glob("episode-*"),
        key=lambda p: int(p.name.split("-")[1]),
    )
    out = []
    for ep in episodes:
        resp = ep / "response.txt"
        out.append(resp.read_text() if resp.exists() else None)
    return out


def events_from_atif(traj, raw_completions=None):
    events = []
    turn = -1
    synthesized_msg = re.compile(r"^Executed \S+ \S+$")

    for step in traj.get("steps", []):
        source = step.get("source")
        message = step.get("message") or ""
        if not isinstance(message, str):
            message = json.dumps(message, ensure_ascii=False)

        if source in ("user", "system"):
            events.append(event(turn + 1, source, message))
            continue

        turn += 1
        meta = {}
        if raw_completions and turn < len(raw_completions) and raw_completions[turn] is not None:
            meta["raw_completion"] = raw_completions[turn]

        if step.get("reasoning_content"):
            events.append(event(turn, "reasoning", step["reasoning_content"]))

        tool_calls = step.get("tool_calls") or []
        if message and not (tool_calls and synthesized_msg.match(message)):
            events.append(event(turn, "text", message, **meta))
            meta = {}

        call_ids = {}
        for k, tc in enumerate(tool_calls, 1):
            cid = f"{turn}.{k}"
            call_ids[tc.get("tool_call_id")] = cid
            events.append(event(
                turn, "tool_call", canonical_args(tc.get("arguments", {})),
                name=normalize_tool_name(tc["function_name"]), raw_name=tc["function_name"],
                call_id=cid, raw_call_id=tc.get("tool_call_id"),
            ))

        for res in (step.get("observation") or {}).get("results", []):
            content = METADATA_SUFFIX.sub("", res.get("content") or "")
            src = res.get("source_call_id")
            # terminus-2 returns one terminal dump per turn with no call id
            ids = [call_ids[src]] if src in call_ids else list(call_ids.values())
            events.append(event(turn, "tool_result", content, call_ids=ids,
                                is_error=content.startswith("<tool_use_error>")))
    return events


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def reasoning_visibility(model, events):
    if any(e["type"] == "reasoning" for e in events):
        return "summarized" if model and model.startswith("claude") else "full"
    return "hidden"


def build_event_list(trial_dir):
    """Return {"header": ..., "events": [...]} for one trial folder."""
    trial_dir = Path(trial_dir)
    header = build_header(trial_dir)
    traj_path = trial_dir / "agent" / "trajectory.json"
    traj = load_json(traj_path) if traj_path.exists() else {"steps": []}

    source = "atif"
    events = None
    if header["agent"] == "claude-code":
        jsonl = find_session_jsonl(trial_dir, traj.get("session_id"))
        if jsonl:
            events = events_from_claude_code_jsonl(jsonl)
            source = "claude-code-jsonl"
    if events is None:
        raw = terminus_raw_completions(trial_dir) if header["agent"] == "terminus-2" else None
        events = events_from_atif(traj, raw)

    for i, e in enumerate(events):
        e["idx"] = i

    header["source"] = source
    header["atif_schema"] = traj.get("schema_version")
    header["n_turns"] = max((e["turn"] for e in events), default=-1) + 1
    header["reasoning_visibility"] = reasoning_visibility(header["model"], events)
    return {"header": header, "events": events}


if __name__ == "__main__":
    # Debug: python event_list.py <trial_dir>  -> prints the event list as JSON
    print(json.dumps(build_event_list(sys.argv[1]), indent=1, ensure_ascii=False))
