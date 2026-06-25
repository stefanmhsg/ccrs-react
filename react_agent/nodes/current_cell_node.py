import logging
from typing import Any, Mapping

from langchain_core.messages import AIMessage, ToolMessage

from react_agent.ccrs.rdf_adapter import CcrsRdfParseError
from react_agent.nodes.advertised_navigation import parse_advertised_navigation_options
from react_agent.state.state import AgentState


logger = logging.getLogger(__name__)

ENTERS_FROM_PREDICATE = "https://paul.ti.rw.fau.de/~am52etar/dynmaze/dynmaze#entersFrom"
GRAPH_UPDATED_PREFIX = "Graph updated:"


def current_cell_node(state: AgentState) -> dict[str, Any]:
    """Track the embodied maze cell and current-cell navigation advertisements."""

    current_cell = _current_cell_from_latest_tool_batch(state)
    if current_cell is not None:
        logger.info("[CURRENT_CELL_NODE] Current cell updated: %s", current_cell)
        return {
            "current_cell": current_cell,
            "advertised_navigation_options": None,
        }

    advertised_options = _advertised_navigation_options_from_latest_tool_batch(state)
    if advertised_options is not None:
        logger.info(
            "[CURRENT_CELL_NODE] Advertised navigation options refreshed: current_cell=%s options=%s",
            advertised_options.get("current_cell"),
            len(advertised_options.get("options", [])),
        )
        return {"advertised_navigation_options": advertised_options}

    return {}


def _current_cell_from_latest_tool_batch(state: Mapping[str, Any]) -> str | None:
    messages = list(state.get("messages", []))
    latest_tool_messages = _latest_tool_messages(messages)
    if not latest_tool_messages:
        return None

    latest_ai_message = _latest_ai_message_before_tool_batch(
        messages,
        len(latest_tool_messages),
    )
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


def _advertised_navigation_options_from_latest_tool_batch(
    state: Mapping[str, Any],
) -> dict[str, Any] | None:
    current_cell = state.get("current_cell")
    if not current_cell:
        return None

    messages = list(state.get("messages", []))
    latest_tool_messages = _latest_tool_messages(messages)
    if not latest_tool_messages:
        return None

    latest_ai_message = _latest_ai_message_before_tool_batch(
        messages,
        len(latest_tool_messages),
    )
    if latest_ai_message is None:
        return None

    tool_messages_by_id = {
        str(message.tool_call_id): message for message in latest_tool_messages
    }
    latest_options = None
    for call in latest_ai_message.tool_calls or []:
        tool_message = tool_messages_by_id.get(str(call.get("id")))
        if tool_message is None or not _is_successful_current_cell_get(
            call,
            tool_message,
            str(current_cell),
        ):
            continue
        if not isinstance(tool_message.content, str):
            continue
        try:
            latest_options = parse_advertised_navigation_options(
                tool_message.content,
                current_cell=str(current_cell),
                tool_call_id=str(tool_message.tool_call_id),
            )
            latest_options["same_cell_get_streak"] = (
                _same_cell_get_streak(state, current_cell=str(current_cell)) + 1
            )
        except CcrsRdfParseError:
            logger.info(
                "[CURRENT_CELL_NODE] Preserving previous advertised navigation options; "
                "current-cell GET was not valid Turtle."
            )
            continue
    return latest_options


def _same_cell_get_streak(state: Mapping[str, Any], *, current_cell: str) -> int:
    options_state = state.get("advertised_navigation_options")
    if not isinstance(options_state, Mapping):
        return 0
    if options_state.get("current_cell") != current_cell:
        return 0
    try:
        return int(options_state.get("same_cell_get_streak") or 0)
    except (TypeError, ValueError):
        return 0


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


def _is_successful_current_cell_get(
    call: Mapping[str, Any],
    tool_message: ToolMessage,
    current_cell: str,
) -> bool:
    if call.get("name") != "http_get":
        return False
    if tool_message.status != "success":
        return False
    if _tool_target_url(call) != current_cell:
        return False

    metadata = getattr(tool_message, "response_metadata", {}) or {}
    http_ok = metadata.get("http_ok")
    if http_ok is False:
        return False
    status = metadata.get("http_status")
    return not isinstance(status, int) or status < 400


def _tool_target_url(call: Mapping[str, Any]) -> str | None:
    args = call.get("args")
    if not isinstance(args, Mapping):
        return None
    url = args.get("url")
    return str(url) if url is not None else None
