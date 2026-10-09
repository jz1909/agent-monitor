from agentsq.agent.stream import SummarySegmenter

# Sent when a run ends without the agent having written anything. The loop's
# natural exit is the first turn that calls no tools -- which is also the turn
# that would have produced the answer -- so a run that spends its whole budget
# searching otherwise ends with an empty agent_answer.
FINAL_NUDGE = (
    "Stop calling tools and answer now. Using only the evidence you have "
    "already gathered, write your final answer in full. If the evidence is "
    "incomplete, say so explicitly and give the best supported answer you can."
)


def stream_kwargs(experiment, specs, inputs, prev_id, tool_choice=None):
    kwargs = dict(
        model=experiment.agent_model,
        reasoning={"effort": experiment.reasoning_effort, "summary": "auto"},
        input=inputs,
        stream=True,
    )

    if specs:
        kwargs["tools"] = specs
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        elif prev_id is None:
            kwargs["tool_choice"] = "required"

    if prev_id is not None:
        kwargs["previous_response_id"] = prev_id

    return kwargs


async def consume(stream, segmenter, monitor):
    """Drain one streamed response; return its tool calls, response id and text."""
    calls, prev_id, text_parts = [], None, []

    async for event in stream:
        if event.type == "response.created":
            prev_id = event.response.id
        elif event.type == "response.output_text.delta":
            text_parts.append(event.delta)
        elif event.type == "response.reasoning_summary_text.delta":
            block = segmenter.feed(event)
            if block:
                await monitor.observe(block)
        elif event.type == "response.output_item.done":
            if event.item.type == "function_call":
                calls.append(event.item)

    block = segmenter.flush()
    if block:
        await monitor.observe(block)

    return calls, prev_id, "".join(text_parts)


async def run_task(task, experiment, monitor, client, run_dir) -> dict:
    segmenter = SummarySegmenter()
    # only the text of the turn that ends the run counts as the answer; text
    # written alongside tool calls is preamble ("let me search...")
    answer = ""
    tool_calls: list[str] = []
    prev_id = None
    stop_reason, turns_used = "max_turns", 0

    async with experiment.backend(run_dir, experiment) as backend:
        specs = await backend.specs()
        # tool outputs owed to the model: sent with the next request, so that a
        # run cut off mid-turn still answers its outstanding calls
        pending = [{"role": "user", "content": experiment.wrap(task["prompt"])}]

        for turn in range(1, experiment.max_turns + 1):
            turns_used = turn
            stream = await client.responses.create(
                **stream_kwargs(experiment, specs, pending, prev_id))
            pending = []

            calls, response_id, text = await consume(stream, segmenter, monitor)
            if response_id is not None:
                prev_id = response_id

            if not calls:
                answer = text
                stop_reason = "tools_stopped"
                if experiment.max_turns > 1:
                    print(f"[end] agent stopped calling tools on turn {turn}", flush=True)
                break

            for call in calls:
                tool_calls.append(call.name)
                pending.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": await backend.call(call.name, call.arguments),
                })
            monitor.trace.set_tool_calls(tool_calls)

        # Force an answer when the run produced no text, whether it ran out of
        # turns or stopped calling tools without writing anything. Tools are
        # switched off for this turn so the model has to reply in prose.
        forced_answer = not answer.strip()
        if forced_answer:
            print(f"[final] no answer after turn {turns_used} ({stop_reason}); "
                  "requesting one with tools off", flush=True)
            pending.append({"role": "user", "content": FINAL_NUDGE})
            stream = await client.responses.create(
                **stream_kwargs(experiment, specs, pending, prev_id, tool_choice="none"))
            _, response_id, answer = await consume(stream, segmenter, monitor)
            if response_id is not None:
                prev_id = response_id

        await monitor.finalize()

        return {
            "question_id": task.get("question_id"),
            "question_title": task.get("question_title"),
            "agent_answer": answer,
            "turns_used": turns_used,
            "stop_reason": stop_reason,
            "forced_answer": forced_answer,
            **backend.extras(),
            **monitor.trace.to_dict(),
        }
