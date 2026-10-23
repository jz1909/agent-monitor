from dataclasses import asdict, dataclass
from enum import Enum

from prophet.backends.Base_backend import Decision


def _readable(obj):
    if isinstance(obj, Enum):
        return obj.name
    if isinstance(obj, dict):
        return {k: _readable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_readable(v) for v in obj]
    return obj


@dataclass
class StepRecord:

    t: int
    agent_turn: int | None
    items_seen: int
    decision: Decision | None         
    policy_decision: Decision         
    confidence: float | None
    latency_s: float | None
    error: str | None
    raw: str | dict | None


@dataclass
class RunResult:

    trial_name: str
    model_name: str
    agent_name: str
    task_name: str
    backend: str
    bag: str
    policy: str
    batch_size: int
    label: bool | None
    final_decision: Decision | None
    forced: bool                      
    stop_step: int | None
    stop_agent_turn: int | None
    items_seen: int
    frac_seen: float
    total_latency_s: float
    correct: bool | None              
    steps: list[StepRecord]

    def to_dict(self) -> dict:
        return _readable(asdict(self))
