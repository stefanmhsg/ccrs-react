from langchain_core.messages import ToolMessage
from react_agent.state import AgentState
from react_agent.tools import tools_by_name

def tool_node(state: AgentState):
    last = state["messages"][-1]
    outputs = []

    # Iterate over the tool calls in the last message
    for call in last.tool_calls:
        tool = tools_by_name[call["name"]]
        result = tool.invoke(call["args"])

        outputs.append(
            ToolMessage(
                content=result,
                name=call["name"],
                tool_call_id=call["id"],
            )
        )

    return {"messages": outputs}
