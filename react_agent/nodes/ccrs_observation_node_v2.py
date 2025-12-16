import logging
from typing import Any
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import ToolMessage
from react_agent.state.state_ccrs_v2 import AgentState # Use CCRS v2 state
from rdflib import Graph, Namespace


# Observation node
def ccrs_observation_node(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    
    # Extract messages from state
    messages = state.get("messages", [])
    if not messages:
        logging.warning("[CCRS_OBSERVATION_NODE_V2] No messages found in state for CCRS observation node.")
        return {}

    configuration = config.get("configurable", {}) # Could later be used to configure CCRS
    # agent_name = configuration.get("agent_name", "React")

    # Need a list of what is observed.


    last = messages[-1]

    # Only interpret tool observations
    if not isinstance(last, ToolMessage):
        logging.info("[CCRS_OBSERVATION_NODE_V2] Last message is not a ToolMessage; no CCRS data to extract.")
        return {}

    content = last.content
    tool_call_id = last.tool_call_id

    ccrs_entries: list[dict] = []

    if isinstance(content, str):
        try:
            g = Graph()
            g.parse(data=content, format="turtle")

            logging.info(f"[CCRS_OBSERVATION_NODE_V2] Extracting CCRS from last tool message: {content}")

            # Define namespaces
            MAZE = Namespace("https://kaefer3000.github.io/2021-02-dagstuhl/vocab#")
            
            # Search for signifiers (e.g., maze:green)
            # We look for any triple where the predicate is maze:green
            for s, p, o in g.triples((None, MAZE.green, None)):
                ccrs_entries.append(
                    {
                        "ccrs_type": "Signifier",
                        "tool_call_id": tool_call_id,
                        "signifier": "green",
                        "interpretation": "Detected signifier indicating preferred direction or opportunity",
                        "triple": {
                            "subject": str(s),
                            "predicate": str(p),
                            "object": str(o)
                        }
                    }
                )
        except Exception as e:
            logging.error(f"[CCRS_OBSERVATION_NODE_V2] Failed to parse RDF content: {e}")


    if not ccrs_entries:
        logging.info("[CCRS_OBSERVATION_NODE_V2] No CCRS entries extracted from the last tool message.")
        return {}
    
    logging.info(f"[CCRS_OBSERVATION_NODE_V2] Extracted {len(ccrs_entries)} CCRS entries from the last tool message.")
    logging.debug(f"[CCRS_OBSERVATION_NODE_V2] CCRS entries: {ccrs_entries}")

    return {"ccrs": ccrs_entries} # Return CCRS entries to be appended to state channel for CCRS
