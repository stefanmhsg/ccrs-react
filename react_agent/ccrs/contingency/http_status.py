"""HTTP status extraction from normal LangGraph tool messages."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

from langchain_core.messages import ToolMessage

from react_agent.ccrs.rdf_adapter import CcrsRdfParseError, parse_turtle_triples


HTTP_STATUS_KEYS = (
    "http_status",
    "httpStatus",
    "status_code",
    "statusCode",
    "statusCodeValue",
    "errorStatusCode",
)

HTTP_STATUS_PREDICATE_SUFFIXES = (
    "statusCodeValue",
    "errorStatusCode",
)

HTTP_STATUS_TEXT_PATTERN = re.compile(
    r"(?:^|[\s;])(?:[\w.-]+:)?(?:statusCodeValue|errorStatusCode)\s+"
    r'"?(?P<status>[1-5][0-9]{2})"?(?:\^\^[\w.-]+:[\w.-]+)?',
    re.IGNORECASE,
)


def http_status_from_tool_message(message: ToolMessage) -> int | None:
    """Return an HTTP status code carried by a tool message, if one is visible."""

    status = http_status_from_mapping(message.response_metadata)
    if status is not None:
        return status
    if not isinstance(message.content, str):
        return None
    status = _http_status_from_json_content(message.content)
    if status is not None:
        return status
    status = _http_status_from_turtle_content(message.content)
    if status is not None:
        return status
    return _http_status_from_text_content(message.content)


def http_status_from_mapping(mapping: Mapping[str, Any]) -> int | None:
    """Return an HTTP status code from a mapping using common generic keys."""

    for key in HTTP_STATUS_KEYS:
        status = _coerce_http_status(mapping.get(key))
        if status is not None:
            return status
    return _http_status_from_nested_values(mapping.values())


def _http_status_from_json_content(content: str) -> int | None:
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        return None
    if isinstance(value, Mapping):
        return http_status_from_mapping(value)
    if isinstance(value, list):
        return _http_status_from_nested_values(value)
    return None


def _http_status_from_turtle_content(content: str) -> int | None:
    try:
        triples = parse_turtle_triples(content)
    except (CcrsRdfParseError, ValueError):
        return None
    for triple in triples:
        if any(triple.predicate.endswith(suffix) for suffix in HTTP_STATUS_PREDICATE_SUFFIXES):
            status = _coerce_http_status(triple.object)
            if status is not None:
                return status
    return None


def _http_status_from_text_content(content: str) -> int | None:
    for match in HTTP_STATUS_TEXT_PATTERN.finditer(content):
        status = _coerce_http_status(match.group("status"))
        if status is not None:
            return status
    return None


def _http_status_from_nested_values(values: Iterable[Any]) -> int | None:
    for value in values:
        if isinstance(value, Mapping):
            status = http_status_from_mapping(value)
            if status is not None:
                return status
        elif isinstance(value, list):
            status = _http_status_from_nested_values(value)
            if status is not None:
                return status
    return None


def _coerce_http_status(value: Any) -> int | None:
    if value is None:
        return None
    try:
        status = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if 100 <= status <= 599:
        return status
    return None
