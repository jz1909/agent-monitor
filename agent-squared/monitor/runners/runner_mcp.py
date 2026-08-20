import json

from state import status
from typing import Any

from buffer import stream_buffer
from nodes import compact_node
from render import renderState
from config import AGENT_EFFORT, AGENT_MODEL
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class McpTaskRunner:

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
            
            


    async def run(self) -> dict:

        params = StdioServerParameters(
        command='npx',
        args=["-y", "@modelcontextprotocol/server-filesystem", "."])

        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed_tools = await session.list_tools()
                

                for tool in listed_tools.tools:
                    spec = {
                        "type":"function",
                        "name":tool.name,
                        "description":tool.description,
                        "parameters": tool.input_schema,
                    }

                    self.tool_specs.append(spec)

                self.input = [{"role":"user", "content":self.task["prompt"]}]

                for _ in range(self.loop_iterations):
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
                        break 

                    self.input = await self._call_tool(session=session, tool_calls = calls)
                    self.renderer.update_tool_call(self.tool_call_hist)

                                
                                
                await self._finalize()
                return self._build_result()

    async def _call_tool(self, session, tool_calls) -> list[Any]:
        input = []
        for tool_call in tool_calls:
            self.tool_call_count += 1
            self.tool_call_hist.append(tool_call.name)
            args = json.loads(tool_call.arguments)
            r = await session.call_tool(tool_call.name, args)
            output = self._mcp_result(r)
            input.append({
                        "type":"function_call_output",
                        "call_id":tool_call.call_id,
                        "output": output
                    })
        return input
        

    def _mcp_result(self, r):
        parts = []

        for c in r.content:
            if getattr(c, "type") == "text":
                parts.append(c.text)
            elif getattr(c, "type") == "image":
                parts.append(f"[image {c.mimeType}, {len(c.data)} b64chars]")
            else:
                parts.append(f"[{getattr(c, 'type', 'unknown')}] block")

        return "".join(parts) 
         
    
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

        """When we're completed with a entire block of summary, we export it and reset stuff
        """
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
            **self.renderer.to_dict()
        }
    
async def run_mcp_task(task, chain, openai_client, snapshot_window, loop_iterations=10) -> dict:
    return await McpTaskRunner(task, chain, openai_client, snapshot_window, loop_iterations).run()
    