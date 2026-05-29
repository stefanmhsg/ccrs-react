from langgraph.graph import END, StateGraph

from react_agent.ccrs.opportunistic.opportunistic import opportunistic_ccrs_node
from react_agent.ccrs.state import CcrsAgentState
from react_agent.nodes.decision_node import should_continue
from react_agent.nodes.llm_node_ccrs_v2 import llm_node
from react_agent.nodes.tool_node import tool_node


def build_graph():
    workflow = StateGraph(CcrsAgentState)

    workflow.add_node("llm", llm_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("opportunistic_ccrs", opportunistic_ccrs_node)

    workflow.set_entry_point("llm")

    workflow.add_conditional_edges(
        "llm",
        should_continue,
        {
            "continue": "tools",
            "end": END,
        },
    )

    workflow.add_edge("tools", "opportunistic_ccrs")
    workflow.add_edge("opportunistic_ccrs", "llm")

    return workflow.compile()
