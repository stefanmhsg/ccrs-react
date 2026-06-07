import logging
from datetime import datetime, timezone
from typing import Any
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from react_agent.ccrs.audit import log_ccrs_event
from react_agent.state.state import AgentState
from react_agent.tools import tools
from react_agent.prompts.react_prompt import react_prompt
from react_agent.nodes.message_window import sliding_message_window

logger = logging.getLogger(__name__)

# Create model and bind tools
def llm_node(
    state: AgentState,
    config: RunnableConfig,
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

    # Bind tools to the model. Force at least one tool to be called.
    model = llm.bind_tools(tools, tool_choice="any")

    chain = react_prompt | model
    messages = sliding_message_window(
        state["messages"],
        max_messages=max_messages,
        max_tokens=max_tokens,
    )

    response = chain.invoke({
        "messages": messages,
        "agent_name": agent_name,
    }, config)
    
    logging.debug(f"LLM node received response: {response}")
    logging.info(f"LLM node tool calls: {response.tool_calls}")

    next_cycle = int(state.get("cycle", {}).get("number", 0)) + 1
    cycle_timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    log_ccrs_event(
        logger,
        "react.loop.cycle",
        {
            "cycle": next_cycle,
            "cycle_timestamp": cycle_timestamp,
            "agent_name": agent_name,
            "tool_call_count": len(response.tool_calls or []),
        },
    )
    return {
        "messages": [response],
        "cycle": {
            "number": next_cycle,
            "timestamp": cycle_timestamp,
        },
    }
