from state import status
from typing import Any

from buffer import stream_buffer
from nodes import compact_node
from render import renderState
from config import AGENT_EFFORT, AGENT_MODEL



class TaskRunner:

    def __init__(self, task, chain, openai_client, snapshot_window:int = 1):
        self.task:str= task
        self.chain = chain
        self.openai_client = openai_client
        self.snapshot_window:int = snapshot_window

        self.buffer:stream_buffer = stream_buffer()
        self.renderer:renderState = renderState()
        self.summaries:dict[int, str] = {}
        self.prev_idx: int | None = None
        self.compacted_sum:str = ""
        self.saved_state:status= status.PROGRESSING
        self.prev_history:list[status] = []


    async def run(self) -> dict:
        stream = await self._open_stream()
        async for event in stream:
            if event.type == "response.reasoning_summary_text.delta":
                idx = event.summary_index
                await self._handle_summary_delta(event, idx)
                self.prev_idx = idx
        await self._finalize()
        return self._build_result()


    async def _open_stream(self):

        return await self.openai_client.responses.create(
            model=AGENT_MODEL,
            reasoning={"effort": AGENT_EFFORT, 'summary':'auto'},
            input=[{"role":"user", "content":self.task["prompt"]}],
            stream=True,
        )
        

    async def _handle_summary_delta(self, event, idx):
        if idx not in self.summaries:
            self.summaries[idx] = event.delta
        else:
            self.summaries[idx] += event.delta

        if self.prev_idx is not None and idx != self.prev_idx:
            self.buffer.append(self.summaries[self.prev_idx])
            recent_sums = self.buffer.return_snapshot(self.snapshot_window)
            result = await self.chain.ainvoke({"reasoning_sums":recent_sums, "last_sum":self.compacted_sum, "curr_sum":"", "curr_analysis":"", "curr_state":self.saved_state, "status_history":self.prev_history})
            self.renderer.update_state(new_phase=result['curr_state'], new_summary_text=self.summaries[self.prev_idx], new_curr_sum=result['curr_sum'], new_curr_analysis=result['curr_analysis'])

            self.compacted_sum = result['curr_sum']
            self.saved_state = result['curr_state']
            self.prev_history = result['status_history']


    async def _finalize(self):
        if self.prev_idx is not None:
            self.buffer.append(self.summaries[self.prev_idx])
            final = await compact_node({
                "reasoning_sums": self.buffer.return_snapshot(1),
                "last_sum": self.compacted_sum,
            })
            self.compacted_sum = final['curr_sum']

            self.renderer.update_state(
                new_phase=status.COMPLETED,
                new_summary_text=self.summaries[self.prev_idx],
                new_curr_sum=self.compacted_sum,
                new_curr_analysis=self.renderer.curr_analysis
            )
                


    def _build_result(self) -> dict[Any]:
        return  {
            "question_id": self.task.get("question_id"),
            "question_title": self.task.get("question_title"),
            **self.renderer.to_dict()
        }

async def run_task(task, chain, openai_client, snapshot_window) -> dict:
    return await TaskRunner(task, chain, openai_client, snapshot_window).run()


    

    