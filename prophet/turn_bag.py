from abc import ABC, abstractmethod
from prophet.batch import Batch
from typing import List


class TurnBag(ABC):

    def build(self, batches: List[Batch], t: int) -> str:
        """Builds the input text for step t given a list of batches"""
        return "\n".join(piece for b in self.window(batches, t) for piece in b.pieces)

    @abstractmethod
    def window(self, batches: List[Batch], t: int) -> List[Batch]:
        """Returns the batches that are relevant for step t"""


class SingleBag(TurnBag):

    def window(self, batches: List[Batch], t: int) -> List[Batch]:
        return [batches[t]]


class CumulativeBag(TurnBag):

    def window(self, batches: List[Batch], t: int) -> List[Batch]:
        return batches[:t + 1]


class SlidingBag(TurnBag):

    def __init__(self, k: int):
        self.k = k

    def window(self, batches: List[Batch], t: int) -> List[Batch]:
        return batches[max(0, t - self.k + 1):t + 1]
