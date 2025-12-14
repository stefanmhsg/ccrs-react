from react_agent.state.state import AgentState
import logging
from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)

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
                logger.debug(f"Second last message content: {second_last.content}")
                return "end"

    # Safety check
    if not getattr(last, "tool_calls", None):
        logger.warning("No tool calls found in the last message. Ending the process.")
        logger.debug(f"Last message content: {last.content}")
        return "end" # Should not happen with tool_choice="any"
        
    return "continue"
