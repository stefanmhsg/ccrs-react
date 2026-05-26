import logging
import json
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from react_agent.state.state import AgentState
from react_agent.tools import tools_by_name


def _tool_error(message: str, call: dict) -> str:
    return json.dumps(
        {
            "error": True,
            "message": message,
            "tool_call": {
                "name": call.get("name"),
                "args": call.get("args", {}),
            },
        }
    )


def _tool_content(result) -> str:
    if isinstance(result, str):
        return result
    return json.dumps(result)


def tool_node(state: AgentState, config: RunnableConfig):
    last = state["messages"][-1]
    outputs = []

    logging.debug(f"[TOOL_NODE] Tool node received message: {last}")

    # Iterate over the tool calls in the last message
    for call in last.tool_calls:
        tool_name = call.get("name")
        if tool_name not in tools_by_name:
            result = _tool_error(f"Unknown tool: {tool_name}", call)
            logging.warning(f"[TOOL_NODE] {result}")
        else:
            tool = tools_by_name[tool_name]
            logging.info(f"[TOOL_NODE] Invoking tool: {tool_name} with args: {call.get('args', {})}")
            try:
                # Pass the config to the tool invocation. Tool validation/runtime errors
                # become normal tool messages so the agent can correct the next call.
                result = tool.invoke(call.get("args", {}), config)
                result = _tool_content(result)
                logging.debug(f"[TOOL_NODE] Tool result: {result}")
            except Exception as e:
                result = _tool_error(f"{tool_name} failed: {str(e)}", call)
                logging.warning(f"[TOOL_NODE] Tool invocation failed: {result}")

        outputs.append(
            ToolMessage(
                content=result,
                name=tool_name or "unknown_tool",
                tool_call_id=call.get("id"),
            )
        )

    return {"messages": outputs}
