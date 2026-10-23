import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import IntEnum


class Decision(IntEnum):
    YES = 1
    NO = 0
    UNSURE = 2


@dataclass
class Prediction:
    decision: Decision | None     
    confidence: float | None
    raw: str | dict | None
    latency_s: float | None = None
    error: str | None = None


class BaseBackend(ABC):

    def __init__(self, model_name: str):
        self.model_name = model_name

    def predict(self, text: str) -> Prediction:
        start = time.perf_counter()
        result = self._predict(text)
        result.latency_s = time.perf_counter() - start
        return result

    @abstractmethod
    def _predict(self, text: str) -> Prediction:
        pass
