from langgraph.graph import StateGraph, END
from react_agent.state import AgentState
from react_agent.nodes.llm_node import llm_node
from react_agent.nodes.tool_node import tool_node
from react_agent.nodes.decision_node import should_continue

def build_graph():
    # Define a new graph with the AgentState
    workflow = StateGraph(AgentState)

    # Add nodes to the graph
    workflow.add_node("llm", llm_node)
    workflow.add_node("tools", tool_node)

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
            # If `tools`, then we call the tool node.
            "continue": "tools",
            # Otherwise we finish.
            "end": END,
        },
    )

    # Add a normal edge after `tools` is called, `llm` node is called next.
    workflow.add_edge("tools", "llm")

    return workflow.compile()
