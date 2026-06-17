import logging
from typing import Any, Mapping

from langchain_core.messages import AIMessage, ToolMessage

from react_agent.state.state import AgentState


logger = logging.getLogger(__name__)

ENTERS_FROM_PREDICATE = "https://paul.ti.rw.fau.de/~am52etar/dynmaze/dynmaze#entersFrom"
GRAPH_UPDATED_PREFIX = "Graph updated:"


def current_cell_node(state: AgentState) -> dict[str, Any]:
    """Track the embodied maze cell after successful movement POST calls."""

    current_cell = _current_cell_from_latest_tool_batch(state)
    if current_cell is None:
        return {}

    logger.info("[CURRENT_CELL_NODE] Current cell updated: %s", current_cell)
    return {"current_cell": current_cell}


def _current_cell_from_latest_tool_batch(state: Mapping[str, Any]) -> str | None:
    messages = list(state.get("messages", []))
    latest_tool_messages = _latest_tool_messages(messages)
    if not latest_tool_messages:
        return None

    latest_ai_message = _latest_ai_message_before_tool_batch(messages, len(latest_tool_messages))
    if latest_ai_message is None:
        return None

    tool_messages_by_id = {
        str(message.tool_call_id): message for message in latest_tool_messages
    }
    current_cell = None
    for call in latest_ai_message.tool_calls or []:
        tool_message = tool_messages_by_id.get(str(call.get("id")))
        if tool_message is None:
            continue
        if _is_successful_move_call(call, tool_message):
            current_cell = _tool_target_url(call)
    return current_cell


def _latest_tool_messages(messages: list[Any]) -> list[ToolMessage]:
    latest: list[ToolMessage] = []
    for message in reversed(messages):
        if not isinstance(message, ToolMessage):
            break
        latest.append(message)
    latest.reverse()
    return latest


def _latest_ai_message_before_tool_batch(
    messages: list[Any],
    tool_message_count: int,
) -> AIMessage | None:
    search_until = len(messages) - tool_message_count
    for message in reversed(messages[:search_until]):
        if isinstance(message, AIMessage):
            return message
    return None


def _is_successful_move_call(call: Mapping[str, Any], tool_message: ToolMessage) -> bool:
    if call.get("name") != "http_post":
        return False
    if tool_message.status != "success":
        return False
    if not isinstance(tool_message.content, str):
        return False
    if not tool_message.content.startswith(GRAPH_UPDATED_PREFIX):
        return False

    args = call.get("args")
    if not isinstance(args, Mapping):
        return False
    data = args.get("data")
    return isinstance(data, str) and ENTERS_FROM_PREDICATE in data


def _tool_target_url(call: Mapping[str, Any]) -> str | None:
    args = call.get("args")
    if not isinstance(args, Mapping):
        return None
    url = args.get("url")
    return str(url) if url is not None else None
