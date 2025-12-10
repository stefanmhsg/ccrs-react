from react_agent.state import AgentState
from react_agent.logging_config import setup_logging
from langchain_core.messages import ToolMessage

logger = setup_logging()

def should_continue(state: AgentState):
    messages = state["messages"]
    last = messages[-1]
    exit_verification = "<http://127.0.1.1:8080/cells/999> a maze:Cell;"



    if len(messages) > 1:
        second_last = messages[-2]
        
        # Ensure it is actually a tool output and contains the verification string
        if isinstance(second_last, ToolMessage):
            if exit_verification in second_last.content:
                logger.info("Exit verification succeeded in previous step. Ending process.")
                return "end"

    # Safety check
    if not getattr(last, "tool_calls", None):
        logger.warning("No tool calls found in the last message. Ending the process.")
        return "end" # Should not happen with tool_choice="any"
        
    return "continue"
