"""Python representation of Java contingency `Interaction`.

This module derives Java-style interaction records from normal LangGraph
messages. RDF parsing is kept as perceived state, while outcome classification
is pluggable so scenario-specific policies stay outside `CcrsContext`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from react_agent.ccrs.rdf_adapter import CcrsRdfParseError, RdfTripleValue, parse_turtle_triples


class InteractionOutcome:
    """Python names for Java `Interaction.Outcome` values."""

    SUCCESS = "SUCCESS"
    CLIENT_FAILURE = "CLIENT_FAILURE"
    SERVER_FAILURE = "SERVER_FAILURE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Interaction:
    """Input data used to build Java `ccrs.core.contingency.dto.Interaction`."""

    method: str
    request_uri: str
    request_headers: Mapping[str, str]
    request_body: str | None
    outcome: str
    perceived_state: list[RdfTripleValue]
    request_timestamp: int
    response_timestamp: int
    logical_source: str


@dataclass(frozen=True)
class ParsedToolMessage:
    """Parsed RDF and interaction data derived from one `ToolMessage`."""

    triples: list[RdfTripleValue]
    interaction: Interaction


OutcomeClassifier = Callable[
    [ToolMessage, Mapping[str, Any], list[RdfTripleValue]],
    str,
]


def parse_tool_messages(
    messages: Sequence[BaseMessage],
    *,
    outcome_classifier: OutcomeClassifier | None = None,
) -> list[ParsedToolMessage]:
    """Derive RDF triples and Java-style interactions from message history."""

    classifier = outcome_classifier or default_outcome_classifier
    tool_calls: dict[str, tuple[dict[str, Any], int]] = {}
    parsed: list[ParsedToolMessage] = []

    for index, message in enumerate(messages):
        if isinstance(message, AIMessage):
            for call in message.tool_calls or []:
                call_id = call.get("id")
                if call_id:
                    tool_calls[str(call_id)] = (call, index)
            continue

        if not isinstance(message, ToolMessage):
            continue

        content = message.content if isinstance(message.content, str) else ""
        triples = parse_tool_content(content)
        call, request_index = tool_calls.get(str(message.tool_call_id), ({}, index))
        interaction = interaction_from_tool_message(
            message,
            call,
            triples,
            outcome_classifier=classifier,
            request_timestamp=request_index,
            response_timestamp=index,
        )
        parsed.append(ParsedToolMessage(triples=triples, interaction=interaction))

    return parsed


def parse_tool_content(content: str) -> list[RdfTripleValue]:
    """Parse a tool message body as Turtle, returning no triples for non-RDF text."""

    if not content.strip():
        return []
    try:
        return parse_turtle_triples(content)
    except CcrsRdfParseError:
        return []


def interaction_from_tool_message(
    message: ToolMessage,
    call: Mapping[str, Any],
    triples: list[RdfTripleValue],
    *,
    outcome_classifier: OutcomeClassifier | None = None,
    request_timestamp: int,
    response_timestamp: int,
) -> Interaction:
    """Create a Java-style `Interaction` from one tool call and response."""

    args = call.get("args") if isinstance(call.get("args"), Mapping) else {}
    tool_name = str(message.name or call.get("name") or "unknown_tool")
    request_uri = str(args.get("url") or "")
    request_headers = args.get("headers") if isinstance(args.get("headers"), Mapping) else {}
    request_body = args.get("data")
    classifier = outcome_classifier or default_outcome_classifier

    return Interaction(
        method=method_from_tool_name(tool_name),
        request_uri=request_uri,
        request_headers={str(key): str(value) for key, value in request_headers.items()},
        request_body=str(request_body) if request_body is not None else None,
        outcome=classifier(message, call, triples),
        perceived_state=triples,
        request_timestamp=request_timestamp,
        response_timestamp=response_timestamp,
        logical_source=request_uri or tool_name,
    )


def default_outcome_classifier(
    message: ToolMessage,
    call: Mapping[str, Any],
    triples: list[RdfTripleValue],
) -> str:
    """Classify transport outcome using only generic LangGraph message fields."""

    status = _http_status_from_metadata(message.response_metadata)
    if status is not None:
        if status >= 500:
            return InteractionOutcome.SERVER_FAILURE
        if status >= 400:
            return InteractionOutcome.CLIENT_FAILURE
        return InteractionOutcome.SUCCESS

    if message.status == "error":
        return InteractionOutcome.UNKNOWN

    if isinstance(message.content, str) and _is_tool_error_json(message.content):
        return InteractionOutcome.UNKNOWN
    return InteractionOutcome.SUCCESS


def method_from_tool_name(tool_name: str) -> str:
    """Map common React HTTP tool names to Java `Interaction.method` values."""

    normalized = tool_name.lower()
    if normalized == "http_get":
        return "GET"
    if normalized == "http_post":
        return "POST"
    return normalized.upper()


def _http_status_from_metadata(metadata: Mapping[str, Any]) -> int | None:
    value = metadata.get("http_status")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_tool_error_json(content: str) -> bool:
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        return False
    return isinstance(value, Mapping) and bool(value.get("error"))
