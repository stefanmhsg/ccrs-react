from react_agent.state import AgentState

def should_continue(state: AgentState):
    last = state["messages"][-1]
    if not getattr(last, "tool_calls", None):
        return "end"
    return "continue"
