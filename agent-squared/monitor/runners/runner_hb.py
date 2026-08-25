import time

from state import status
from typing import Any

from buffer import stream_buffer
from nodes import compact_node
from render import renderState
from config import AGENT_MODEL
from heartbeat import HeartbeatWriter, HEARTBEAT_TOOL_SPEC
from hb_config import HEARTBEAT_TOOL_NAME, wrap_prompt, AGENT_EFFORT


class HbTaskRunner:

    def __init__(self, task, chain, openai_client, snapshot_window:int = 1, loop_iterations:int = 5):
            self.task:str= task
            self.chain = chain
            self.openai_client = openai_client
            self.snapshot_window:int = snapshot_window
            self.loop_iterations:int = loop_iterations

            self.buffer:stream_buffer = stream_buffer()
            self.renderer:renderState = renderState()
            self.summaries:dict[int, str] = {}
            self.prev_idx: int | None = None
            self.compacted_sum:str = ""
            self.saved_state:status= status.PROGRESSING
            self.prev_history:list[status] = []
            self.tool_call_hist:list[Any] = []
            self.tool_call_count:int = 0
            self.tool_specs = []
            self.input = []
            self.prev_id = None
            self.answer_parts: list[str] = []
            self.hb: HeartbeatWriter = HeartbeatWriter()


    async def run(self) -> dict:

        self.tool_specs = [HEARTBEAT_TOOL_SPEC]

        self.input = [{"role":"user", "content":wrap_prompt(self.task["prompt"])}]

        run_start = time.monotonic()

        for turn in range(1, self.loop_iterations + 1):
            print(f"[turn {turn}] opening stream", flush=True)

            stream = await self._open_stream()
            calls = []
            async for event in stream:
                if event.type == "response.created":
                    self.prev_id = event.response.id
                elif event.type == "response.output_text.delta":
                    self.answer_parts.append(event.delta)
                elif event.type == "response.reasoning_summary_text.delta":
                    idx = event.summary_index
                    await self._handle_summary_delta(event, idx)
                    self.prev_idx = idx
                elif event.type == "response.output_item.done":
                    if event.item.type == "function_call":
                            calls.append(event.item)
            if self.prev_idx is not None:
                await self._flush_summary(self.prev_idx)
            self.summaries.clear()
            self.prev_idx = None

            if not calls:
                print(f"[end] agent stopped calling tools on turn {turn}", flush=True)
                break

            self.input = await self._call_tool(tool_calls = calls)
            self.renderer.update_tool_call(self.tool_call_hist)


        await self._finalize()
        return self._build_result()


    async def _call_tool(self, tool_calls) -> list[Any]:
        input = []
        for tool_call in tool_calls:
            self.tool_call_count += 1
            self.tool_call_hist.append(tool_call.name)

            if tool_call.name == HEARTBEAT_TOOL_NAME:
                output = self._beat()
            else:
                output = f"unknown tool: {tool_call.name}"

            input.append({
                        "type":"function_call_output",
                        "call_id":tool_call.call_id,
                        "output": output
                    })
        return input


    def _beat(self) -> str:
        try:
            self.hb.beat()
            print(f"[beat #{self.hb.beat_count}]", flush=True)
            return "ok"
        except Exception as e:
            print(f"[beat FAILED] {e}", flush=True)
            return f"heartbeat failed: {e}"


    async def _open_stream(self):

        kwargs = dict(
        model=AGENT_MODEL,
        reasoning={"effort": AGENT_EFFORT, "summary": "auto"},
        tools=self.tool_specs,
        input=self.input,
        stream=True,
    )

        if self.prev_id:
            kwargs["previous_response_id"] = self.prev_id
        else:
            kwargs["tool_choice"]="required"

        return await self.openai_client.responses.create(**kwargs)


    async def _flush_summary(self, idx):

        if idx not in self.summaries:
            return

        self.buffer.append(self.summaries[idx])

        recent_sums = self.buffer.return_snapshot(self.snapshot_window)
        result = await self.chain.ainvoke({
            "reasoning_sums": recent_sums,
            "last_sum": self.compacted_sum,
            "curr_sum": "",
            "curr_analysis": "",
            "curr_state": self.saved_state,
            "status_history": self.prev_history,
        })

        self.renderer.update_state(
            new_phase=result['curr_state'],
            new_summary_text=self.summaries[idx],
            new_curr_sum=result['curr_sum'],
            new_curr_analysis=result['curr_analysis'],
        )

        self.compacted_sum = result['curr_sum']
        self.saved_state = result['curr_state']
        self.prev_history = result['status_history']


    async def _handle_summary_delta(self, event, idx):
        if idx not in self.summaries:
            self.summaries[idx] = event.delta
        else:
            self.summaries[idx] += event.delta

        if self.prev_idx is not None and idx != self.prev_idx:
            await self._flush_summary(self.prev_idx)


    async def _finalize(self):
        if not self.compacted_sum:
            return

        final = await compact_node({
            "reasoning_sums": self.buffer.return_snapshot(1),
            "last_sum": self.compacted_sum,
        })

        self.compacted_sum = final['curr_sum']
        self.renderer.update_state(
            new_phase=status.COMPLETED,
            new_summary_text="",
            new_curr_sum=self.compacted_sum,
            new_curr_analysis=self.renderer.curr_analysis,
        )


    def _build_result(self) -> dict[Any]:
        return  {
            "question_id": self.task.get("question_id"),
            "question_title": self.task.get("question_title"),
            "agent_answer":"".join(self.answer_parts),
            "frame_id": self.hb.frame_id,
            "beat_count": self.hb.beat_count,
            **self.renderer.to_dict()
        }


async def run_hb_task(task, chain, openai_client, snapshot_window, loop_iterations=25) -> dict:
    return await HbTaskRunner(task, chain, openai_client, snapshot_window, loop_iterations).run()
