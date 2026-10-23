from prophet.backends.Base_backend import Decision, Prediction
from prophet.record import RunResult, StepRecord


def describe(obj) -> str:
    """Short label for a component, including its settings (e.g. 'SlidingBag(k=3)')."""
    settings = {k: v for k, v in vars(obj).items() if isinstance(v, (int, float, str)) and not k.startswith("_")}
    args = ", ".join(f"{k}={v}" for k, v in settings.items())
    return f"{type(obj).__name__}({args})"


class MonitorRunner():

    def __init__(self, batcher, bag, backend, policy):
        self.batcher = batcher
        self.bag = bag
        self.backend = backend
        self.policy = policy

    def run(self, traj) -> RunResult:

        batches = self.batcher.split(traj)
        steps = []
        pred = None
        for t in range(len(batches)):
            text = self.bag.build(batches, t)
            try:
                pred = self.backend.predict(text)
            except Exception as e:
                pred = Prediction(decision=None, confidence=None, raw=None, error=repr(e))
            decision = self.policy.decide(pred, t)
            steps.append(StepRecord(
                t=t,
                agent_turn=batches[t].agent_turn,
                items_seen=batches[t].end_token_idx,
                decision=pred.decision,
                policy_decision=decision,
                confidence=pred.confidence,
                latency_s=pred.latency_s,
                error=pred.error,
                raw=pred.raw,
            ))

            if decision != Decision.UNSURE:
                return self._make_result(traj, steps, decision, forced=False)

        decision = self.policy.finalize(pred)
        return self._make_result(traj, steps, decision, forced=True)

    def run_all(self, trajs) -> list[RunResult]:
        return [self.run(traj) for traj in trajs]

    def _make_result(self, traj, steps, final_decision, forced) -> RunResult:
        last = steps[-1] if steps else None
        items_seen = last.items_seen if last else 0
        n_items = len(traj.tokenized_input)

        correct = None
        if final_decision in (Decision.YES, Decision.NO) and traj.success is not None:
            correct = (final_decision == Decision.YES) == traj.success

        return RunResult(
            trial_name=traj.path.parent.name,
            model_name=traj.model_name,
            agent_name=traj.agent,
            task_name=traj.task_name,
            backend=self.backend.model_name,
            bag=describe(self.bag),
            policy=describe(self.policy),
            batch_size=self.batcher.batch_size,
            label=traj.success,
            final_decision=final_decision,
            forced=forced,
            stop_step=last.t if last else None,
            stop_agent_turn=last.agent_turn if last else None,
            items_seen=items_seen,
            frac_seen=items_seen / n_items if n_items else 0.0,
            total_latency_s=sum(s.latency_s or 0.0 for s in steps),
            correct=correct,
            steps=steps,
        )
