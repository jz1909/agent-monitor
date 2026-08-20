import asyncio
import json

from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
load_dotenv()

CHART_DIR = "empty_graphs"
TASK = {"answer": "Kansas City", "problem": "Consider the chart attached below.  \n\nWhich city experiences the most \"zig-zagging\" in stay at home rates with respect to the number of daily new confirmed Covid-19 cases?\n    * Your final answer must be grounded to some text that is explicitly written and relevant to the question in the chart.\n    * If you need to answer multiple terms, separate them with commas.\n    * Unless specified in the question (such as answering with a letter), you are required to answer the full names of subplots and/or labels by default.\n    ", "id": "reasoning_val_7"}

SYSTEM = f"You are answering a question about a scientific chart. The chart images are stored in the directory {CHART_DIR}. You have filesystem tools available to locate and view them. You must ground your answer in what the chart actually shows."

MODEL = 'gpt-5.5'

def mcp_result(r):
    parts = []

    for c in r.content:
        if getattr(c, "type") == "text":
            parts.append(c.text)
        elif getattr(c, "type") == "image":
            parts.append(f"[image {c.mimeType}, {len(c.data)} b64chars]")
        else:
            parts.append(f"[{getattr(c, 'type', 'unknown')}] block")

    return "".join(parts) 

async def main():
    params = StdioServerParameters(
        command='npx',
        args=["-y", "@modelcontextprotocol/server-filesystem", "."]
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            listed_tools = await session.list_tools()
            tool_specs = []

            for tool in listed_tools.tools:
                spec = {
                    "type":"function",
                    "name":tool.name,
                    "description":tool.description,
                    "parameters": tool.input_schema,
                }

                tool_specs.append(spec)

            client = AsyncOpenAI()
            input = [
                {"role":"system", "content":SYSTEM},
                {"role":"user", "content":TASK["problem"]}
            ]

            prev_id = None
            total_calls = 0
            call_hist = []
            final_text = []
            summary_text = []

            for _ in range(1, 5):

                calls = []
                
                kwarg = dict(model=MODEL, input=input, tools=tool_specs, reasoning={"effort":"high", "summary":"detailed"}, stream = True)
                if prev_id:
                    kwarg["previous_response_id"] = prev_id
                else:
                    kwarg["tool_choice"]="required"

                stream_response = await client.responses.create(**kwarg)

                prev_id = None

                async for item in stream_response:
                    if item.type == "response.created":
                        prev_id = item.response.id
                    elif item.type == "response.output_item.done":
                        if item.item.type=="function_call":
                            calls.append(item.item)
                    elif item.type == "response.output_text.delta":
                        final_text.append(item.delta)
                    elif item.type == "response.reasoning_summary_text.delta":
                        summary_text.append(item.delta)

                if not calls:
                    print(f"Stopped due to no tool calls, total of {total_calls} tool calls")
                    print(f"final answer: {final_text}")
                    print(summary_text)
                    print(call_hist)
                    return

                input = []

                for call in calls:
                    total_calls+=1
                    call_hist.append(call.name)
                    args = json.loads(call.arguments)
                    r = await session.call_tool(call.name, args)
                    output = mcp_result(r)
                    input.append({
                        "type":"function_call_output",
                        "call_id":call.call_id,
                        "output": output
                    })

            print(f"exceeded max calls, returning..")
            print(f"final answer: {final_text}")
            print(summary_text)
            print(call_hist)
                    

if __name__ == '__main__':
    asyncio.run(main())