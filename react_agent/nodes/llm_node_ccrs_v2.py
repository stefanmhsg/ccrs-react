import logging
from datetime import datetime, timezone
from typing import Any, Sequence
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from react_agent.ccrs.prompt_context import build_ccrs_prompt_context
from react_agent.ccrs.state import CcrsAgentState
from react_agent.tools import tools
from react_agent.prompts.react_prompt import react_prompt_ccrs


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

    response = chain.invoke({
        "messages": state["messages"],
        "agent_name": agent_name,
        "ccrs" : ccrs_context.text,
    }, config)
    
    logging.debug(f"[LLM_NODE_CCRS_V2]: LLM node received response: {response}")
    logging.info(f"[LLM_NODE_CCRS_V2]: LLM node tool calls: {response.tool_calls}")

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
