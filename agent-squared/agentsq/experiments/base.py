from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agentsq.agent.tools.base import ToolBackend


@dataclass
class Experiment:
    name: str
    backend: Callable[[Path], ToolBackend]
    effort: str = "medium"
    max_turns: int = 1
    concurrency: int = 10
    snapshot_window: int = 1
    watchdog: bool = False
    wrap: Callable[[str], str] = lambda prompt: prompt


REGISTRY: dict[str, Experiment] = {}


def register(experiment: Experiment) -> Experiment:
    REGISTRY[experiment.name] = experiment
    return experiment


def get(name: str) -> Experiment:
    return REGISTRY[name]
