from agentsq.monitor.state import MonitorState, Phase

async def compact_node(state: MonitorState):

    total_sum = "".join(state["reasoning_sums"])

    prompt = f"""You are monitoring an AI agent's reasoning process in real time, by reading periodic summaries of its internal reasoning as it works through a problem. Your job right now is purely to consolidate — not to judge or analyze, just to merge information into a clean running record.

    Below are two pieces of context:

    1. PRIOR CONTEXT (a condensed record of everything that happened before this point):
    {state['last_sum']}

    2. NEW ACTIVITY (the most recent summaries since the last check-in):
    {total_sum}

    Write an updated, single condensed narrative of the reasoning process so far, folding the new activity into the prior context. Requirements:
    - As long as needed to preserve everything relevant to tracking progress. Don't pad, but don't drop specifics just to stay short. As the record grows, compress older history more aggressively and keep recent events detailed.
    - Chronological: earlier events first, most recent last.
    - Preserve concrete specifics that matter for tracking progress — what approach is being tried, what's been ruled out, what's been decided, any numbers/entities/results mentioned. Don't flatten everything into vague generalities.
    - If the new activity contradicts, revises, or abandons something from the prior context, reflect that change rather than just appending both versions.
    - Write it as a plain narrative paragraph, not a bulleted list.
    - Do not add commentary, opinions, or predictions about where this is headed — that happens in a later step. This is a factual consolidation only.

    Return only the narrative text, with no preamble or labels."""

    msg = await state['monitor_llm'].ainvoke(prompt)

    return {"curr_sum": msg.content}


async def analyze_node(state: MonitorState):

    topology = state.get("topology", "")
    plan = ""
    plan_bullet = ""
    if topology:
        plan = f"""
    WORKFLOW STRUCTURE — the agent is executing a predefined workflow, given below as a graph. Nodes are stages of the process; edges are the transitions allowed between them. An edge pointing back to an earlier node is a loop the workflow is designed to repeat:
    {topology}

    Use this to ground your assessment. Reaching a later stage is evidence of Progressing. Re-entering a loop is NOT by itself Stuck — the workflow is built to repeat, and a pass that produces something the previous pass did not is Progressing. Stuck is repeated passes through the same loop that fail to produce what would satisfy its exit condition.
"""
        plan_bullet = "    - Which stage of the workflow does this reasoning appear to be in, and is it advancing through the graph or re-treading a stage it already passed?\n"

    prompt = f"""You are monitoring an AI agent's reasoning process. You've been given a condensed narrative of its progress so far (prior context plus the latest activity). Your job is to assess *how the reasoning process itself is unfolding* — not to solve the underlying problem, and not to judge whether the agent's conclusions are correct — and then assign a status.

    CONDENSED REASONING NARRATIVE:
    {state['curr_sum']}
{plan}
    First, write a roughly 30-word analysis addressing:
    - Is the reasoning moving toward a resolution, or circling without new progress?
    - Is it repeating an approach it already tried, or genuinely trying something new?
    - Is this productive struggle (working through real difficulty) or unproductive struggle (confusion, contradiction, drift)?
    - Any concrete signal that it's converging on an answer, or diverging from one?
{plan_bullet}
    Base the analysis strictly on what's described in the narrative — do not speculate beyond it. Write it as plain prose, not a list.

    Then classify the current state into exactly one of these categories:
    - STUCK: reasoning is not measurably closer to the goal than in the prior step. This covers repetition, contradiction, cycling between approaches, revisiting the same obstacle from a new angle without addressing it, exploring options that don't rule anything in or out, or generating plans and restatements without producing evidence that constrains the answer. Effort, novelty, and thoroughness are not progress on their own.
    - PROGRESSING: reasoning has demonstrably reduced the distance to the answer since the prior step — a hypothesis ruled in or out, evidence gathered that narrows the answer space, a subproblem resolved, an ambiguity settled, a confirmed step built upon. The movement must be toward the answer itself, not toward more exploration.
    - COMPLETED: the reasoning has reached a clear conclusion or final answer.

    Format: the analysis text, then a final line of exactly `STATUS: STUCK`, `STATUS: PROGRESSING`, or `STATUS: COMPLETED`. No preamble or other labels."""

    msg = await state['monitor_llm'].ainvoke(prompt)
    text = msg.content.strip()

    lines = text.splitlines()
    last = lines[-1].upper() if lines else ""
    analysis = text
    phase = state["curr_state"]
    if "STATUS:" in last:
        analysis = "\n".join(lines[:-1]).strip()
        for name in ("COMPLETED", "PROGRESSING", "STUCK"):
            if name in last:
                phase = Phase[name]
                break

    return {"curr_analysis": analysis, "curr_state": phase}


def report_node(state: MonitorState):
    return {"status_history": [*state['status_history'], state['curr_state']]}