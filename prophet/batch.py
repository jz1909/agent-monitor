import json
import re
from pathlib import Path
from typing import List


DEFAULT_TRIALS_DIR = Path(__file__).resolve().parent / "data_collection" / "trajectory-data" / "trials"


class Trajectory:

    def __init__(self, model_name, agent, task_name, tokenized_input, success,
                 reasoning_visibility, n_turns, crashed, path):

        self.model_name = model_name
        self.agent = agent
        self.task_name = task_name
        self.tokenized_input = tokenized_input
        self.success = success
        self.reasoning_visibility = reasoning_visibility
        self.n_turns = n_turns
        self.crashed = crashed
        self.path = path


def _load_trajectory(path) -> Trajectory:
    with open(path, "r") as f:
        data = json.load(f)

    return Trajectory(
        model_name=data["model"],
        agent=data["agent"],
        task_name=data["task_name"],
        tokenized_input=data["tokens"],
        success=data["success"],
        reasoning_visibility=data["reasoning_visibility"],
        n_turns=data["n_turns"],
        crashed=data.get("exception") is not None,
        path=Path(path),
    )


def load_trajectories(trials_dir=DEFAULT_TRIALS_DIR, require_label=True, skip_crashed=True,models=None, agents=None, trials=None)-> List[Trajectory]:
    """trials: if given, only these trials, named by their folder
    (e.g. 'claude-sonnet-4-6__claude-code__astropy__astropy-12907') or trial id ('astropy__astropy-12907__EWnwaYU')"""

    trajs = []

    for path in sorted(Path(trials_dir).glob("*/*/parsed_trajectory.json")):
        if trials is not None and path.parent.parent.name not in trials and path.parent.name not in trials:
            continue
        traj = _load_trajectory(path)

        if require_label and traj.success is None:
            continue
        if skip_crashed and traj.crashed:
            continue
        if models is not None and traj.model_name not in models:
            continue
        if agents is not None and traj.agent not in agents:
            continue

        trajs.append(traj)

    return trajs

#Actual batching stuff
#
# Batch size is measured in list items of tokenized_input: each tag ("<|tool_call ...|>")
# and each content string counts as 1, regardless of its length. Items are never split.

TURN_RE = re.compile(r"^<\|turn (\d+)\|>$")


def _is_delimiter(piece):
    return piece.startswith("<|") and piece.endswith("|>")


def _is_event_start(piece):
    return _is_delimiter(piece) and not piece.startswith("<|/")


class Batch:

    def __init__(self, batch_idx, pieces, start_token_idx, end_token_idx, agent_turn):
        self.batch_idx = batch_idx
        self.pieces = pieces
        self.start_token_idx = start_token_idx  # index into tokenized_input
        self.end_token_idx = end_token_idx      # exclusive
        self.agent_turn = agent_turn

    @property
    def n_tokens(self):
        return self.end_token_idx - self.start_token_idx


class TokenBatcher:

    def __init__(self, batch_size, align='none'):
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if align not in ("none", "event"):
            raise ValueError("align must be 'none' or 'event'")
        self.batch_size = batch_size
        self.align = align

    def split(self, trajectory) -> List[Batch]:
        items = trajectory.tokenized_input
        if self.align == "event":
            bounds = self._event_bounds(items)
        else:
            bounds = list(range(0, len(items), self.batch_size)) + [len(items)]

        batches = []
        for start, end in zip(bounds, bounds[1:]):
            prev_turn = batches[-1].agent_turn if batches else None
            turns = [int(m.group(1)) for p in items[start:end] if (m := TURN_RE.match(p))]
            batches.append(Batch(len(batches), items[start:end], start, end,
                                 turns[-1] if turns else prev_turn))
        return batches

    def _group_events(self, items):
        starts = []
        for i, piece in enumerate(items):
            after_turn_marker = i > 0 and TURN_RE.match(items[i - 1])
            if i == 0 or (_is_event_start(piece) and not after_turn_marker):
                starts.append(i)
        return list(zip(starts, starts[1:] + [len(items)]))

    def _event_bounds(self, items):
        bounds = [0]
        for start, end in self._group_events(items):
            if end - bounds[-1] > self.batch_size and start > bounds[-1]:
                bounds.append(start)
            while end - bounds[-1] > self.batch_size:
                bounds.append(bounds[-1] + self.batch_size)
        if bounds[-1] != len(items):
            bounds.append(len(items))
        return bounds
