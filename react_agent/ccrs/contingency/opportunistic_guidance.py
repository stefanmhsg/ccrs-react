"""Contingency-produced opportunistic guidance handling."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig

from react_agent.ccrs.audit import log_ccrs_event
from react_agent.ccrs.rdf_adapter import CcrsRdfParseError, RdfTripleValue, parse_turtle_triples
from react_agent.ccrs.state import CcrsAgentState


logger = logging.getLogger(__name__)


def get_opportunistic_guidance_by_contingency_ccrs(
    state: CcrsAgentState,
    config: RunnableConfig,
) -> list[dict[str, Any]]:
    """Return contingency-produced guidance whose target matches the latest RDF response."""

    guidance = state.get("opportunistic_guidance_by_contingency_ccrs", []) or []
    if not guidance:
        return []

    latest_tool_message = _latest_tool_message(state["messages"])
    if latest_tool_message is None or not isinstance(latest_tool_message.content, str):
        _log_guidance_event(
            "react.ccrs.opportunistic_guidance_by_contingency_ccrs.skipped",
            state,
            config,
            {"reason": "no_parseable_tool_response", "active_entries": len(guidance)},
        )
        return []

    try:
        triples = parse_turtle_triples(latest_tool_message.content)
    except CcrsRdfParseError:
        _log_guidance_event(
            "react.ccrs.opportunistic_guidance_by_contingency_ccrs.skipped",
            state,
            config,
            {
                "reason": "invalid_turtle",
                "tool_call_id": str(latest_tool_message.tool_call_id),
                "tool_name": latest_tool_message.name,
                "active_entries": len(guidance),
            },
        )
        return []

    rdf_resources = _subject_object_values(triples)
    matches = [
        dict(entry)
        for entry in guidance
        if entry.get("target") is not None and str(entry.get("target")) in rdf_resources
    ]
    if matches:
        _log_guidance_event(
            "react.ccrs.opportunistic_guidance_by_contingency_ccrs.matched",
            state,
            config,
            {
                "tool_call_id": str(latest_tool_message.tool_call_id),
                "tool_name": latest_tool_message.name,
                "active_entries": len(guidance),
                "matched_entries": len(matches),
                "targets": ",".join(str(entry.get("target")) for entry in matches),
            },
        )
    else:
        _log_guidance_event(
            "react.ccrs.opportunistic_guidance_by_contingency_ccrs.no_match",
            state,
            config,
            {
                "tool_call_id": str(latest_tool_message.tool_call_id),
                "tool_name": latest_tool_message.name,
                "active_entries": len(guidance),
                "matched_entries": 0,
            },
        )
    return matches


def opportunistic_guidance_from_contingency_ccrs_result(
    contingency_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract replacement guidance from one Java `ContingencyCcrs` result."""

    trace_id = contingency_result.get("trace_id")
    guidance: list[dict[str, Any]] = []
    for guidance_entry in contingency_result.get("opportunistic_guidance", []) or []:
        enriched = dict(guidance_entry)
        if trace_id is not None:
            enriched.setdefault("trace_id", trace_id)
        guidance.append(enriched)
    return guidance


def _latest_tool_message(messages) -> ToolMessage | None:
    for message in reversed(messages):
        if isinstance(message, ToolMessage):
            return message
    return None


def _subject_object_values(triples: list[RdfTripleValue]) -> set[str]:
    values: set[str] = set()
    for triple in triples:
        values.add(triple.subject)
        values.add(triple.object)
    return values


def _log_guidance_event(
    event: str,
    state: CcrsAgentState,
    config: RunnableConfig,
    fields: dict[str, Any],
) -> None:
    configuration = (config or {}).get("configurable", {})
    cycle = state.get("cycle", {})
    log_ccrs_event(
        logger,
        event,
        {
            "agent_name": str(configuration.get("agent_name", "React")),
            "cycle": str(cycle.get("number", 0)),
            "cycle_timestamp": str(cycle.get("timestamp", "")),
            **fields,
        },
    )
