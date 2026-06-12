from langgraph.graph import END, StateGraph

from react_agent.ccrs.capabilities import (
    DEFAULT_CONTINGENCY_CCRS_MODULES,
    ContingencyCapability,
    contingency_modules_for_capabilities,
)
from react_agent.ccrs.ccrs_node import make_ccrs_node
from react_agent.ccrs.contingency.contingency_ccrs import ContingencyCcrs
from react_agent.ccrs.contingency.escalation import escalate_to_contingency_ccrs
from react_agent.ccrs.contingency.in_memory_ccrs_trace_history import InMemoryCcrsTraceHistory
from react_agent.state.state_ccrs import CcrsAgentState
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
    contingency_ccrs_modules=None,
    enable_contingency_llm_prediction: bool = False,
    enable_contingency_a2a_consultation: bool = False,
    discover_contingency_strategy_providers: bool = False,
    contingency_configuration=None,
):
    workflow = StateGraph(CcrsAgentState)
    active_trace_history = ccrs_trace_history or InMemoryCcrsTraceHistory()
    active_contingency_ccrs = _contingency_ccrs_from_options(
        contingency_ccrs=contingency_ccrs,
        contingency_ccrs_modules=contingency_ccrs_modules,
        enable_contingency_llm_prediction=enable_contingency_llm_prediction,
        enable_contingency_a2a_consultation=enable_contingency_a2a_consultation,
        discover_contingency_strategy_providers=discover_contingency_strategy_providers,
        contingency_configuration=contingency_configuration,
    )
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
            contingency_ccrs=active_contingency_ccrs,
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


def _contingency_ccrs_from_options(
    *,
    contingency_ccrs=None,
    contingency_ccrs_modules=None,
    enable_contingency_llm_prediction: bool = False,
    enable_contingency_a2a_consultation: bool = False,
    discover_contingency_strategy_providers: bool = False,
    contingency_configuration=None,
):
    if contingency_ccrs is not None:
        return contingency_ccrs

    capabilities = []
    if enable_contingency_llm_prediction:
        capabilities.append(ContingencyCapability.LLM_PREDICTION)
    if enable_contingency_a2a_consultation:
        capabilities.append(ContingencyCapability.A2A_CONSULTATION)
    modules = contingency_modules_for_capabilities(
        capabilities,
        base_modules=contingency_ccrs_modules,
    )

    discover = (
        discover_contingency_strategy_providers
        or bool(capabilities)
        or modules != DEFAULT_CONTINGENCY_CCRS_MODULES
    )
    if modules == DEFAULT_CONTINGENCY_CCRS_MODULES and not discover:
        return None

    return ContingencyCcrs.from_maven_local(
        modules=modules,
        discover_strategy_providers=discover,
        contingency_configuration=contingency_configuration,
    )
