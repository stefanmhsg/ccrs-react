"""Prompt selection for Java `OpportunisticResult` values."""

from __future__ import annotations

import logging

from langchain_core.messages import AIMessage

from react_agent.ccrs.state import CcrsAgentState


def get_opportunistic_ccrs_for_latest_tool_calls(
    state: CcrsAgentState,
) -> list[dict]:
    """Return opportunistic CCRS entries linked to the latest LLM tool calls."""

    latest_tool_call_ids = get_latest_tool_call_ids(state["messages"])
    return [
        entry
        for entry in state.get("opportunistic_ccrs", [])
        if entry.get("tool_call_id") in latest_tool_call_ids
    ]


def get_latest_tool_call_ids(messages) -> set[str]:
    """Return all tool call ids belonging to the last LLM reasoning step."""

    for message in reversed(messages):
        if isinstance(message, AIMessage) and message.tool_calls:
            logging.debug("[LLM_NODE_CCRS_V2]: Last AIMessage with tool calls found: %s", message)
            return {call["id"] for call in message.tool_calls}
    return set()
