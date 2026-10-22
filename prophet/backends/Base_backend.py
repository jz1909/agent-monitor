import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import IntEnum


class Decision(IntEnum):
    """Enum for the possible decisions a model can make"""
    YES = 1
    NO = 0
    UNSURE = 2


@dataclass
class Prediction:
    decision: Decision | None     # None for score-only backends (Jev); decision.py applies thresholds
    confidence: float | None
    raw: str | dict | None
    latency_s: float | None = None
    error: str | None = None


class BaseBackend(ABC):

    def __init__(self, model_name: str):
        self.model_name = model_name

    def predict(self, text: str) -> Prediction:
        """Times _predict and turns exceptions into an error Prediction, so one bad call
        doesn't crash a whole run. Subclasses implement _predict, not this."""
        start = time.perf_counter()
        try:
            result = self._predict(text)
        except Exception as e:
            result = Prediction(decision=None, confidence=None, raw=None, error=repr(e))
        result.latency_s = time.perf_counter() - start
        return result

    @abstractmethod
    def _predict(self, text: str) -> Prediction:
        """Actual work, wrapped by predict to handle timing and errors"""
