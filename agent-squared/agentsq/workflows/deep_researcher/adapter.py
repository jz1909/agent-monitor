from typing import Any


TERMINAL_NODE = "finalize_summary"
NODES_PER_LOOP = 3


def build():
    from .graph import graph
    return graph


def make_input(task):
    return {"research_topic": task['prompt']}


def make_config(loops) -> dict[Any]:
    return {
        'configurable': {"max_web_research_loops": loops},
        'recursion_limit': 10
         + NODES_PER_LOOP * (loops+2),
    }


def topology(graph):
    return graph.get_graph().draw_mermaid()


def answer_from_update(payload):
    node_summary = payload.get("finalize_summary")
    if node_summary is None:
        return None
    
    return node_summary.get("running_summary")