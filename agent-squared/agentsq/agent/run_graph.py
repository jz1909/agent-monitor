from agentsq.agent.stream import LCSSegmenter


async def run_graph_task(task, experiment, monitor, client, run_dir) -> dict:
    segmenter = LCSSegmenter()
    answer = None


    adapter = experiment.workflow
    graph = adapter.build()

    monitor.topos = adapter.topology(graph) if experiment.use_topos else ""

    stream = graph.astream(
        adapter.make_input(task),
        adapter.make_config(experiment.loops, experiment.agent_model, experiment.reasoning_effort),
        stream_mode=["messages", "updates"],
    )

    async for mode, payload in stream:
        if mode == "updates":
            answer = adapter.answer_from_update(payload) or answer
            continue

        chunk, meta = payload
        node = meta["langgraph_node"]

        content = chunk.content
        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict) or block.get("type") != "reasoning":
                continue
            for summary in block.get("summary", []):
                text = summary.get("text", "")
                if not text:
                    continue
                block_result = segmenter.feed(node, summary["index"], text)
                if block_result:
                    await monitor.observe(block_result)

  
    block = segmenter.flush()
    if block:
        await monitor.observe(block)

    await monitor.finalize()

    return {
        "question_id": task.get("question_id"),
        "question_title": task.get("question_title"),
        "agent_answer": answer or "",
        **monitor.trace.to_dict(),
    }
