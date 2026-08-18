from langgraph.graph import StateGraph, START, END

from state import MonitorState
from nodes import compact_node, analyze_node, classify_node, report_node

def build_chain():
    workflow = StateGraph(MonitorState)

    workflow.add_node("compact_node", compact_node)
    workflow.add_node("analyze_node", analyze_node)
    workflow.add_node("classify_node", classify_node)
    workflow.add_node("report_node", report_node)


    workflow.add_edge(START, "compact_node")
    workflow.add_edge("compact_node", "analyze_node")
    workflow.add_edge("analyze_node", "classify_node")
    workflow.add_edge("classify_node", "report_node")
    workflow.add_edge("report_node", END)

    chain = workflow.compile()
    return chain