from openai import AsyncOpenAI

from agentsq.agent.run import FINAL_NUDGE
from agentsq.agent.stream import TokenSegmenter
from agentsq.settings import TOKENS_SPENT

BASE_URLS = {
    "SOPHIA": "https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1",
    "MINERVA": "https://inference-api.alcf.anl.gov/resource_server/minerva/api/v1",
}


def make_client(base_url) -> AsyncOpenAI:
    from inference_auth_token import get_access_token
    return AsyncOpenAI(api_key=get_access_token(), base_url=base_url)


def to_chat_specs(specs):
    return [
        {
            "type": "function",
            "function": {
                "name": spec["name"],
                "description": spec.get("description") or "",
                "parameters": spec.get("parameters") or {"type": "object", "properties": {}},
            },
        }
        for spec in specs
    ]


def stream_kwargs(experiment, specs, messages, tool_choice=None):
    kwargs = dict(
        model=experiment.agent_model,
        reasoning_effort=experiment.reasoning_effort,
        messages=messages,
        stream=True,
        # final chunk carries token usage, logged per turn
        stream_options={"include_usage": True},
    )

    if specs:
        kwargs["tools"] = specs
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

    return kwargs


async def consume(stream, segmenter, monitor):
    text_parts: list[str] = []
    calls: dict[int, dict] = {}
    info = {"finish_reason": None, "prompt_tokens": None,
            "completion_tokens": None, "reasoning_chunks": 0}

    async for chunk in stream:
        # the usage chunk arrives last, with no choices
        if getattr(chunk, "usage", None):
            info["prompt_tokens"] = chunk.usage.prompt_tokens
            info["completion_tokens"] = chunk.usage.completion_tokens
        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        if choice.finish_reason:
            info["finish_reason"] = choice.finish_reason
        delta = choice.delta

        reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
        if reasoning:
            info["reasoning_chunks"] += 1
            block = segmenter.feed(reasoning)
            if block:
                await monitor.observe(block)

        if delta.content:
            text_parts.append(delta.content)

        for tc in delta.tool_calls or []:
            call = calls.setdefault(tc.index, {"id": None, "name": "", "arguments": ""})
            if tc.id:
                call["id"] = tc.id
            if tc.function is not None:
                if tc.function.name:
                    call["name"] = tc.function.name
                if tc.function.arguments:
                    call["arguments"] += tc.function.arguments

    block = segmenter.flush()
    if block:
        await monitor.observe(block)

    return "".join(text_parts), [calls[i] for i in sorted(calls)], info


def log_turn(turn_log, turn, text, calls, info):
    """Record why a turn ended, to tell a full context from a dropped tool call."""
    entry = {"turn": turn, **info, "n_calls": len(calls), "text_len": len(text)}
    turn_log.append(entry)
    print(f"[turn {turn}] finish={info['finish_reason']} prompt={info['prompt_tokens']} "
          f"completion={info['completion_tokens']} calls={len(calls)} text={len(text)}",
          flush=True)


def assistant_message(text, calls):
    message = {"role": "assistant", "content": text or None}
    if calls:
        message["tool_calls"] = [
            {
                "id": call["id"],
                "type": "function",
                "function": {"name": call["name"], "arguments": call["arguments"] or "{}"},
            }
            for call in calls
        ]
    return message


async def run_cont_task(task, experiment, monitor, client, run_dir) -> dict:
    client = make_client(BASE_URLS[experiment.cluster])
    segmenter = TokenSegmenter(TOKENS_SPENT)
    tool_calls: list[str] = []
    turn_log: list[dict] = []
    answer = ""
    stop_reason, turns_used = "max_turns", 0

    async with experiment.backend(run_dir, experiment) as backend:
        specs = to_chat_specs(await backend.specs())
        messages = [{"role": "user", "content": experiment.wrap(task["prompt"])}]

        for turn in range(1, experiment.max_turns + 1):
            turns_used = turn
            stream = await client.chat.completions.create(
                **stream_kwargs(experiment, specs, messages))
            # stream = await client.chat.completions.create(
            #     **stream_kwargs(experiment, specs, messages,
            #                     tool_choice="required" if turn == 1 else None))

            text, calls, info = await consume(stream, segmenter, monitor)
            log_turn(turn_log, turn, text, calls, info)
            messages.append(assistant_message(text, calls))

            if not calls:
                answer = text
                stop_reason = "tools_stopped"
                if experiment.max_turns > 1:
                    print(f"[end] agent stopped calling tools on turn {turn}", flush=True)
                break

            for call in calls:
                tool_calls.append(call["name"])
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": await backend.call(call["name"], call["arguments"] or "{}"),
                })
            monitor.trace.set_tool_calls(tool_calls)

        # Force an answer when the run produced no text, whether it ran out of
        # turns or stopped calling tools without writing anything. Tools are
        # switched off for this turn so the model has to reply in prose.
        forced_answer = not answer.strip()
        if forced_answer:
            print(f"[final] no answer after turn {turns_used} ({stop_reason}); "
                  "requesting one with tools off", flush=True)
            messages.append({"role": "user", "content": FINAL_NUDGE})
            stream = await client.chat.completions.create(
                **stream_kwargs(experiment, specs, messages, tool_choice="none"))
            answer, calls, info = await consume(stream, segmenter, monitor)
            log_turn(turn_log, "final", answer, calls, info)

        await monitor.finalize()

        return {
            "question_id": task.get("question_id"),
            "question_title": task.get("question_title"),
            "agent_answer": answer,
            "turns_used": turns_used,
            "stop_reason": stop_reason,
            "forced_answer": forced_answer,
            "tokens_spent": TOKENS_SPENT,
            "turn_log": turn_log,
            **backend.extras(),
            **monitor.trace.to_dict(),
        }
