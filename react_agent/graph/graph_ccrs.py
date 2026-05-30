from langgraph.graph import END, StateGraph

from react_agent.ccrs.ccrs_node import make_ccrs_node
from react_agent.ccrs.contingency.escalation import escalate_to_contingency_ccrs
from react_agent.ccrs.contingency.in_memory_ccrs_trace_history import InMemoryCcrsTraceHistory
from react_agent.ccrs.state import CcrsAgentState
from react_agent.ccrs.contingency.decision import (
    make_ccrs_decision_node,
    route_after_ccrs_decision,
    route_after_ccrs_node,
)
from react_agent.nodes.llm_node_ccrs_v2 import make_llm_node
from react_agent.nodes.tool_node import tool_node
from react_agent.tools import tools


def build_graph(
    *,
    contingency_escalation_controller=None,
    contingency_ccrs=None,
    ccrs_trace_history=None,
    ccrs_prompt_template=None,
    enable_contingency_escalation_tool: bool = False,
):
    workflow = StateGraph(CcrsAgentState)
    active_trace_history = ccrs_trace_history or InMemoryCcrsTraceHistory()
    active_tools = list(tools)
    if enable_contingency_escalation_tool:
        active_tools.append(escalate_to_contingency_ccrs)

    workflow.add_node(
        "llm",
        make_llm_node(
            bound_tools=active_tools,
            prompt_template=ccrs_prompt_template,
        ),
    )
    workflow.add_node(
        "decision",
        make_ccrs_decision_node(
            contingency_escalation_controller=contingency_escalation_controller,
        ),
    )
    workflow.add_node("tools", tool_node)
    workflow.add_node(
        "ccrs",
        make_ccrs_node(
            contingency_ccrs=contingency_ccrs,
            ccrs_trace_history=active_trace_history,
        ),
    )

    workflow.set_entry_point("llm")
    workflow.add_edge("llm", "decision")

    workflow.add_conditional_edges(
        "decision",
        route_after_ccrs_decision,
        {
            "continue": "tools",
            "ccrs": "ccrs",
            "end": END,
        },
    )

    workflow.add_edge("tools", "ccrs")
    workflow.add_conditional_edges(
        "ccrs",
        route_after_ccrs_node,
        {
            "continue": "llm",
            "end": END,
        },
    )

    return workflow.compile()
