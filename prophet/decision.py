from abc import ABC, abstractmethod
from prophet.backends.Base_backend import Decision, Prediction


class DecisionPolicy(ABC):

    @abstractmethod
    def decide(self, pred: Prediction, t: int) -> Decision:
        pass

    def finalize(self, pred: Prediction) -> Decision:
        if pred is None or pred.confidence is None:
            return Decision.UNSURE
        return Decision.YES if pred.confidence >= 0.5 else Decision.NO



class ChoicePolicy(DecisionPolicy):

    def decide(self, pred: Prediction, t: int) -> Decision:
        if pred.decision in (Decision.YES, Decision.NO):
            return pred.decision
        return Decision.UNSURE


class ThresholdPolicy(DecisionPolicy):

    def __init__(self, threshold: float):
        self.threshold = threshold

    def decide(self, pred: Prediction, t: int) -> Decision:
        decision = pred.decision
        confidence = pred.confidence
        if confidence is None:
            return Decision.UNSURE
        if decision == Decision.YES and confidence >= self.threshold:
            return Decision.YES
        if decision == Decision.NO and (1 - confidence) >= self.threshold:
            return Decision.NO
        return Decision.UNSURE
