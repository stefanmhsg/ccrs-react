import logging
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from react_agent.state.state import AgentState
from react_agent.tools import tools_by_name

def tool_node(state: AgentState, config: RunnableConfig):
    last = state["messages"][-1]
    outputs = []

    logging.debug(f"Tool node received message: {last}")

    # Iterate over the tool calls in the last message
    for call in last.tool_calls:
        tool = tools_by_name[call["name"]]
        logging.info(f"Invoking tool: {call['name']} with args: {call['args']}")
        # Pass the config to the tool invocation
        result = tool.invoke(call["args"], config)
        logging.debug(f"Tool result: {result}")

        outputs.append(
            ToolMessage(
                content=result,
                name=call["name"],
                tool_call_id=call["id"],
            )
        )

    return {"messages": outputs}
