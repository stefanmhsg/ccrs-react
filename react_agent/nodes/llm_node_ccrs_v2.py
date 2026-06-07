import logging
from datetime import datetime, timezone
from typing import Any, Sequence
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from react_agent.ccrs.prompt_context import build_ccrs_prompt_context
from react_agent.ccrs.audit import log_ccrs_event
from react_agent.ccrs.reportability import selected_tool_target
from react_agent.ccrs.state import CcrsAgentState
from react_agent.nodes.message_window import sliding_message_window
from react_agent.tools import tools
from react_agent.prompts.react_prompt import react_prompt_ccrs


logger = logging.getLogger(__name__)


def make_llm_node(
    *,
    bound_tools: Sequence[Any] | None = None,
    prompt_template: ChatPromptTemplate | None = None,
):
    """Create a CCRS LLM node with graph-provided tools."""

    def configured_llm_node(
        state: CcrsAgentState,
        config: RunnableConfig,
    ) -> dict[str, Any]:
        return llm_node(
            state,
            config,
            bound_tools=bound_tools,
            prompt_template=prompt_template,
        )

    return configured_llm_node


# Create model and bind tools
def llm_node(
    state: CcrsAgentState,
    config: RunnableConfig,
    *,
    bound_tools: Sequence[Any] | None = None,
    prompt_template: ChatPromptTemplate | None = None,
) -> dict[str, Any]:
    
    configuration = config.get("configurable", {})
    llm_model = configuration.get("llm_model", "gpt-5-mini")
    llm_temperature = configuration.get("llm_temperature", 1.0)
    llm_reasoning_effort = configuration.get("llm_reasoning_effort", "minimal")
    max_messages = configuration.get("llm_message_window_max_messages")
    max_tokens = configuration.get("llm_message_window_max_tokens")
    agent_name = configuration.get("agent_name", "React")

    llm = ChatOpenAI(
        model=llm_model,
        temperature=llm_temperature,
        reasoning_effort=llm_reasoning_effort,
    )

    active_tools = list(bound_tools) if bound_tools is not None else list(tools)

    # Bind tools to the model. Force at least one tool to be called.
    model = llm.bind_tools(active_tools, tool_choice="any")

    active_prompt = configuration.get("react_prompt_ccrs") or prompt_template or react_prompt_ccrs
    chain = active_prompt | model
    ccrs_context = build_ccrs_prompt_context(state, config)
    messages = sliding_message_window(
        state["messages"],
        max_messages=max_messages,
        max_tokens=max_tokens,
    )

    response = chain.invoke({
        "messages": messages,
        "agent_name": agent_name,
        "ccrs" : ccrs_context.text,
    }, config)
    
    logging.debug(f"[LLM_NODE_CCRS_V2]: LLM node received response: {response}")
    logging.info(f"[LLM_NODE_CCRS_V2]: LLM node tool calls: {response.tool_calls}")
    _log_selection_events(
        response.tool_calls or [],
        state,
        config,
        ccrs_context,
    )

    next_cycle = int(state.get("cycle", {}).get("number", 0)) + 1
    updates: dict[str, Any] = {
        "messages": [response],
        "cycle": {
            "number": next_cycle,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        },
    }
    updates.update(ccrs_context.post_llm_updates())
    return updates


def _log_selection_events(
    tool_calls: Sequence[dict[str, Any]],
    state: CcrsAgentState,
    config: RunnableConfig,
    ccrs_context,
) -> None:
    configuration = config.get("configurable", {})
    cycle = state.get("cycle", {})
    for tool_call in tool_calls:
        selected_uri = selected_tool_target(tool_call)
        followed_top_opportunistic = (
            bool(selected_uri)
            and bool(ccrs_context.top_opportunistic_target)
            and selected_uri == ccrs_context.top_opportunistic_target
        )
        followed_top_contingency = (
            bool(selected_uri)
            and bool(ccrs_context.top_contingency_guidance_target)
            and selected_uri == ccrs_context.top_contingency_guidance_target
        )
        log_ccrs_event(
            logger,
            "react.ccrs.opportunistic.selection",
            {
                "cycle": str(cycle.get("number", 0)),
                "cycle_timestamp": str(cycle.get("timestamp", "")),
                "agent_name": str(configuration.get("agent_name", "React")),
                "tool_name": tool_call.get("name"),
                "tool_call_id": tool_call.get("id"),
                "selected_uri": selected_uri,
                "selection_mode": "advisory_prompt",
                "opportunistic_count": ccrs_context.opportunistic_count,
                "contingency_guidance_count": ccrs_context.contingency_guidance_count,
                "followed_top_opportunistic": followed_top_opportunistic,
                "followed_top_contingency_guidance": followed_top_contingency,
                "followed_any_top_guidance": (
                    followed_top_opportunistic or followed_top_contingency
                ),
                "top_opportunistic_target": ccrs_context.top_opportunistic_target,
                "top_contingency_guidance_target": (
                    ccrs_context.top_contingency_guidance_target
                ),
                "prompt_context_id": ccrs_context.prompt_context_id,
            },
        )
