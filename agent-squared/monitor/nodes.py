# Nodes
from state import MonitorState, status
from config import monitor_model

async def compact_node(state: MonitorState):

    total_sum = "".join(state["reasoning_sums"])

    prompt = f"""You are monitoring an AI agent's reasoning process in real time, by reading periodic summaries of its internal reasoning as it works through a problem. Your job right now is purely to consolidate — not to judge or analyze, just to merge information into a clean running record.

    Below are two pieces of context:

    1. PRIOR CONTEXT (a condensed record of everything that happened before this point):
    {state['last_sum']}

    2. NEW ACTIVITY (the most recent summaries since the last check-in):
    {total_sum}

    Write an updated, single condensed narrative of the reasoning process so far, folding the new activity into the prior context. Requirements:
    - Roughly 50 words.
    - Chronological: earlier events first, most recent last.
    - Preserve concrete specifics that matter for tracking progress — what approach is being tried, what's been ruled out, what's been decided, any numbers/entities/results mentioned. Don't flatten everything into vague generalities.
    - If the new activity contradicts, revises, or abandons something from the prior context, reflect that change rather than just appending both versions.
    - Write it as a plain narrative paragraph, not a bulleted list.
    - Do not add commentary, opinions, or predictions about where this is headed — that happens in a later step. This is a factual consolidation only.

    Return only the narrative text, with no preamble or labels."""

    msg = await monitor_model.ainvoke(prompt)

    return {"curr_sum": msg.content}


async def analyze_node(state: MonitorState):

    prompt = f"""You are monitoring an AI agent's reasoning process. You've been given a condensed narrative of its progress so far. Your job is to assess *how the reasoning process itself is unfolding* — not to solve the underlying problem, and not to judge whether the agent's conclusions are correct.

    CONDENSED REASONING NARRATIVE:
    {state['curr_sum']}

    Write a roughly 20-word analysis addressing:
    - Is the reasoning moving toward a resolution, or circling without new progress?
    - Is it repeating the same approach/idea it already tried, or genuinely trying something new?
    - Are there signs of productive struggle (working through real difficulty) versus unproductive struggle (confusion, contradiction, or drift)?
    - Any concrete signal that it's converging on an answer soon, or conversely that it's diverging further from one?

    Base your analysis strictly on what's described in the narrative — do not speculate beyond it. Write it as plain prose, not a list. Return only the analysis text, with no preamble or labels."""

    msg = await monitor_model.ainvoke(prompt)
    return {"curr_analysis": msg.content}


async def classify_node(state: MonitorState):

    prompt = f"""You are the final classification step in a reasoning-monitor pipeline. Based on the analysis below, classify the current state of the AI agent's reasoning process into exactly one of these three categories:

        - Stuck: reasoning is not measurably closer to the goal than in the prior step. This covers repetition, contradiction, cycling between approaches, revisiting the same obstacle from a new angle without addressing it, exploring options that don't rule anything in or out, or generating plans and restatements without producing evidence that constrains the answer. Effort, novelty, and thoroughness are not progress on their own.
        - Progressing: reasoning has demonstrably reduced the distance to the answer since the prior step — a hypothesis ruled in or out, evidence gathered that narrows the answer space, a subproblem resolved, an ambiguity settled, a confirmed step built upon. The movement must be toward the answer itself, not toward more exploration.
        - Completed: the reasoning has reached a clear conclusion or final answer.

        ANALYSIS:
        {state['curr_analysis']}

        Respond with exactly one word: STUCK, PROGRESSING, or COMPLETED. No punctuation, no explanation, no additional text — the word alone, spelled and capitalized exactly as shown above."""

    msg = await monitor_model.ainvoke(prompt)
    type_enum = status[msg.content]
    return {"curr_state": type_enum}

def report_node(state:MonitorState):
    new_status_history = state['status_history']
    new_status_history.append(state['curr_state'])

    return {"status_history":new_status_history}