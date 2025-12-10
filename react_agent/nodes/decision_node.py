from react_agent.state import AgentState
from react_agent.logging_config import setup_logging

logger = setup_logging()

def should_continue(state: AgentState):
    last = state["messages"][-1]

    # Safety check
    if not getattr(last, "tool_calls", None):
        logger.warning("No tool calls found in the last message. Ending the process.")
        return "end" # Should not happen with tool_choice="any"

    # Check if the agent reached the exit
    exit_verification = "<http://127.0.1.1:8080/cells/999> a maze:Cell;"
    # Verify that the agent is indeed in the exit cell. Check last tool outputs.
    if exit_verification in last.content:
        logger.info("Exit verification succeeded. Ending the process.")
        return "end"
        
    return "continue"
