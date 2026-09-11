from enum import Enum
from typing import TypedDict


class Phase(Enum):
    STUCK = 1
    PROGRESSING = 2
    COMPLETED = 3


class MonitorState(TypedDict):
    reasoning_sums: list[str]
    last_sum: str
    curr_sum: str
    curr_analysis: str
    curr_state: Phase
    status_history: list[Phase]
    topology: str
