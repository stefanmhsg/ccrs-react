import json
import logging
from typing import Any
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import ToolMessage, AIMessage
from langchain_openai import ChatOpenAI
from react_agent.state.state_ccrs_v2 import AgentState # Use CCRS v2 state
from react_agent.tools import tools
from react_agent.prompts.react_prompt import react_prompt


# Create model and bind tools
def llm_node(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    
    configuration = config.get("configurable", {})
    llm_model = configuration.get("llm_model", "gpt-5-mini")
    llm_temperature = configuration.get("llm_temperature", 1.0)
    agent_name = configuration.get("agent_name", "React")

    llm = ChatOpenAI(
        model=llm_model,
        temperature=llm_temperature,
    )

    # Bind tools to the model. Force at least one tool to be called.
    model = llm.bind_tools(tools, tool_choice="any")

    chain = react_prompt | model

    # --- CCRS filtering logic ---

    # Extract the latest tool call IDs from the messages
    latest_tool_call_ids = get_latest_tool_call_ids(state["messages"])

    # Filter CCRS entries to only include those related to the latest tool calls
    ccrs_text = "[]"  # Default to empty list if no relevant CCRS entries found
    ccrs_context = [
        entry
        for entry in state.get("ccrs", [])
        if entry.get("tool_call_id") in latest_tool_call_ids
    ]

    if ccrs_context:
        ccrs_text = json.dumps(ccrs_context, ensure_ascii=False, indent=2) # Do not pass raw Python dicts into {ccrs}. Convert to compact JSON so the model sees a stable schema.
        logging.info(f"[LLM_NODE_CCRS_V2]: Injecting {len(ccrs_context)} relevant CCRS entries to LLM.")
        logging.info(f"[LLM_NODE_CCRS_V2]: CCRS Context: {ccrs_text}")

    # ------

    response = chain.invoke({
        "messages": state["messages"],
        "agent_name": agent_name,
        "ccrs" : ccrs_text, # Provide filtered CCRS context to the LLM
    }, config)
    
    logging.debug(f"[LLM_NODE_CCRS_V2]: LLM node received response: {response}")
    logging.info(f"[LLM_NODE_CCRS_V2]: LLM node tool calls: {response.tool_calls}")

    return {
        "messages": [response],
        "number_of_cycles": state.get("number_of_cycles", 0) + 1,
    }


def get_latest_tool_call_ids(messages):
    """Extract the latest tool call IDs from the messages. Returns all tool_call_ids belonging to the last reasoning step"""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            # An AIMessage can contain multiple tool calls
            logging.debug(f"[LLM_NODE_CCRS_V2]: Last AIMessage with tool calls found: {msg}")
            return {call["id"] for call in msg.tool_calls}
    return set()
