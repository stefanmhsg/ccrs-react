import logging
from typing import Any
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import ToolMessage
from react_agent.state.state_ccrs_v2 import AgentState # Use CCRS v2 state


# Observation node
def ccrs_observation_node(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    
    # Extract messages from state
    messages = state.get("messages", [])
    if not messages:
        logging.warning("No messages found in state for CCRS observation node.")
        return {}

    configuration = config.get("configurable", {}) # Could later be used to configure CCRS
    # agent_name = configuration.get("agent_name", "React")

    # Need a list of what is observed.


    last = messages[-1]

    # Only interpret tool observations
    if not isinstance(last, ToolMessage):
        logging.info("Last message is not a ToolMessage; no CCRS data to extract.")
        return {}

    content = last.content
    tool_call_id = last.tool_call_id

    logging.info(f"Extracting CCRS from last tool message: {content}")

    ccrs_entries: list[dict] = []

    # Mock example for Signifier detection
    if isinstance(content, str) and "maze:green" in content:
        ccrs_entries.append(
            {
                "ccrs_type": "Signifier",
                "tool_call_id": tool_call_id,
                "signifier": "green",
                "interpretation": "Detected signifier indicating preferred direction or opportunity",
            }
        )


    if not ccrs_entries:
        logging.info("No CCRS entries extracted from the last tool message.")
        return {}
    
    logging.info(f"Extracted {len(ccrs_entries)} CCRS entries from the last tool message.")
    logging.debug(f"CCRS entries: {ccrs_entries}")

    return {"ccrs": ccrs_entries} # Return CCRS entries to be appended to state channel for CCRS
