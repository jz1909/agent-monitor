from langchain_core.callbacks import UsageMetadataCallbackHandler

from agentsq.monitor.buffer import SummaryBuffer
from agentsq.monitor.nodes import compact_node
from agentsq.monitor.state import Phase
from agentsq.monitor.trace import RunTrace


class Monitor:

    def __init__(self, chain, snapshot_window: int = 1, topos: str ="", monitor_llm=None):
        self.chain = chain
        self.snapshot_window = snapshot_window
        self.topos = topos
        self.usage = UsageMetadataCallbackHandler()
        self.monitor_llm = monitor_llm.with_config(callbacks=[self.usage]) if monitor_llm else None

        self.buffer = SummaryBuffer()
        self.trace = RunTrace()
        self.compacted_sum: str = ""
        self.phase: Phase = Phase.PROGRESSING
        self.history: list[Phase] = []

    async def observe(self, block: str) -> dict:
        self.buffer.append(block)

        result = await self.chain.ainvoke({
            "reasoning_sums": self.buffer.return_snapshot(self.snapshot_window),
            "last_sum": self.compacted_sum,
            "curr_sum": "",
            "curr_analysis": "",
            "curr_state": self.phase,
            "status_history": self.history,
            "topology": self.topos,
            "monitor_llm": self.monitor_llm,
        })

        self.trace.update(
            phase=result['curr_state'],
            summary_text=block,
            curr_sum=result['curr_sum'],
            curr_analysis=result['curr_analysis'],
        )

        self.compacted_sum = result['curr_sum']
        self.phase = result['curr_state']
        self.history = result['status_history']
        return result

    async def finalize(self):
        if not self.compacted_sum:
            return

        final = await compact_node({
            "reasoning_sums": self.buffer.return_snapshot(1),
            "last_sum": self.compacted_sum,
            "monitor_llm": self.monitor_llm,
        })

        self.compacted_sum = final['curr_sum']
        self.trace.update(
            phase=Phase.COMPLETED,
            summary_text="",
            curr_sum=self.compacted_sum,
            curr_analysis=self.trace.curr_analysis,
        )
