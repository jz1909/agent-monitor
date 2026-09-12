from agentsq.agent.stream import SummarySegmenter


def stream_kwargs(experiment, specs, inputs, prev_id):
    kwargs = dict(
        model=experiment.agent_model,
        reasoning={"effort": experiment.reasoning_effort, "summary": "auto"},
        input=inputs,
        stream=True,
    )

    if specs:
        kwargs["tools"] = specs
        if prev_id is None:
            kwargs["tool_choice"] = "required"

    if prev_id is not None:
        kwargs["previous_response_id"] = prev_id

    return kwargs


async def run_task(task, experiment, monitor, client, run_dir) -> dict:
    segmenter = SummarySegmenter()
    answer_parts: list[str] = []
    tool_calls: list[str] = []
    prev_id = None

    async with experiment.backend(run_dir) as backend:
        specs = await backend.specs()
        inputs = [{"role": "user", "content": experiment.wrap(task["prompt"])}]

        for turn in range(1, experiment.max_turns + 1):
            stream = await client.responses.create(**stream_kwargs(experiment, specs, inputs, prev_id))

            calls = []
            async for event in stream:
                if event.type == "response.created":
                    prev_id = event.response.id
                elif event.type == "response.output_text.delta":
                    answer_parts.append(event.delta)
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

            if not calls:
                if experiment.max_turns > 1:
                    print(f"[end] agent stopped calling tools on turn {turn}", flush=True)
                break

            inputs = []
            for call in calls:
                tool_calls.append(call.name)
                inputs.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": await backend.call(call.name, call.arguments),
                })
            monitor.trace.set_tool_calls(tool_calls)

        await monitor.finalize()

        return {
            "question_id": task.get("question_id"),
            "question_title": task.get("question_title"),
            "agent_answer": "".join(answer_parts),
            **backend.extras(),
            **monitor.trace.to_dict(),
        }
