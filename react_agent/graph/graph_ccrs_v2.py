from langgraph.graph import StateGraph, END
from react_agent.state.state_ccrs_v2 import AgentState # Use CCRS v2 state
from react_agent.nodes.llm_node_ccrs_v2 import llm_node # Use CCRS v2 LLM node
from react_agent.nodes.tool_node import tool_node
from react_agent.nodes.ccrs_observation_node_v2 import ccrs_observation_node # CCRS v2 observation node
from react_agent.nodes.decision_node import should_continue

def build_graph():
    # Define a new graph with the AgentState
    workflow = StateGraph(AgentState)

    # Add nodes to the graph
    workflow.add_node("llm", llm_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("ccrs_observation", ccrs_observation_node) # Add CCRS observation node

    # Set the entrypoint as `llm`, this is the first node called
    workflow.set_entry_point("llm")

    # Add a conditional edge after the `llm` node is called.
    workflow.add_conditional_edges(
        # Edge is used after the `llm` node is called.
        "llm",
        # The function that will determine which node is called next.
        should_continue,
        # Mapping for where to go next, keys are strings from the function return, and the values are other nodes.
        # END is a special node marking that the graph is finish.
        {
            # If `continue`, then we call the tool node.
            "continue": "tools",
            # Otherwise we finish.
            "end": END,
        },
    )

    # Add a normal edges
    workflow.add_edge("tools", "ccrs_observation") # After tools, call CCRS observation
    workflow.add_edge("ccrs_observation", "llm") # After CCRS observation, call LLM

    return workflow.compile()
