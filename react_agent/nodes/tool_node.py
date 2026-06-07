import logging
import json
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from react_agent.state.state import AgentState
from react_agent.tools import tools_by_name
from react_agent.tools.http_result import metadata_from_result


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


def _tool_target(call: dict) -> str | None:
    args = call.get("args", {})
    if not isinstance(args, dict):
        return None
    target = args.get("url") or args.get("target") or args.get("uri")
    return str(target) if target is not None else None


def _result_metadata(
    *,
    call: dict,
    tool_name: str | None,
    outcome: str,
    result=None,
    error: Exception | None = None,
) -> dict:
    metadata = {
        "tool_call_id": call.get("id"),
        "tool_name": tool_name or "unknown_tool",
        "target": _tool_target(call),
        "outcome": outcome,
    }
    metadata.update(metadata_from_result(result))
    if error is not None:
        metadata["error"] = str(error)
        metadata["error_type"] = type(error).__name__
    return {key: value for key, value in metadata.items() if value is not None}


def _log_tool_result(metadata: dict) -> None:
    logging.info(
        "[TOOL_NODE] Tool result: %s",
        json.dumps(metadata, sort_keys=True),
    )


def tool_node(state: AgentState, config: RunnableConfig):
    last = state["messages"][-1]
    outputs = []

    logging.debug(f"[TOOL_NODE] Tool node received message: {last}")

    # Iterate over the tool calls in the last message
    for call in last.tool_calls:
        tool_name = call.get("name")
        status = "success"
        metadata = {}
        if tool_name not in tools_by_name:
            result = _tool_error(f"Unknown tool: {tool_name}", call)
            status = "error"
            metadata = _result_metadata(
                call=call,
                tool_name=tool_name,
                outcome="error",
                error=ValueError(f"Unknown tool: {tool_name}"),
            )
            logging.warning(f"[TOOL_NODE] {result}")
        else:
            tool = tools_by_name[tool_name]
            logging.info(f"[TOOL_NODE] Invoking tool: {tool_name} with args: {call.get('args', {})}")
            try:
                # Pass the config to the tool invocation. Tool validation/runtime errors
                # become normal tool messages so the agent can correct the next call.
                result = tool.invoke(call.get("args", {}), config)
                metadata = _result_metadata(
                    call=call,
                    tool_name=tool_name,
                    outcome="success",
                    result=result,
                )
                result = _tool_content(result)
                logging.debug(f"[TOOL_NODE] Tool result: {result}")
            except Exception as e:
                result = _tool_error(f"{tool_name} failed: {str(e)}", call)
                status = "error"
                metadata = _result_metadata(
                    call=call,
                    tool_name=tool_name,
                    outcome="error",
                    error=e,
                )
                logging.warning(f"[TOOL_NODE] Tool invocation failed: {result}")

        _log_tool_result(metadata)
        outputs.append(
            ToolMessage(
                content=result,
                name=tool_name or "unknown_tool",
                tool_call_id=call.get("id"),
                status=status,
                response_metadata=metadata,
            )
        )

    return {"messages": outputs}
