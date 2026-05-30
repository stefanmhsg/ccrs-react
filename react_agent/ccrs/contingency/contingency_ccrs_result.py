"""Prompt lifecycle helpers for Java `ContingencyCcrs` results."""

from __future__ import annotations

from typing import Any

from react_agent.ccrs.state import CcrsAgentState


def get_pending_contingency_ccrs(state: CcrsAgentState) -> list[dict[str, Any]]:
    """Return contingency CCRS entries that have not yet been injected."""

    return [
        entry
        for entry in state.get("contingency_ccrs", [])
        if not entry.get("completed", False)
    ]


def mark_contingency_ccrs_completed(
    pending_contingency_ccrs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build completion updates for one-shot contingency CCRS prompt entries."""

    return [
        {**entry, "completed": True}
        for entry in pending_contingency_ccrs
    ]
