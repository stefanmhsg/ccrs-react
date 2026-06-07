"""HTTP tool result metadata without changing tool message content."""

from __future__ import annotations

from typing import Any

import requests


class HttpToolResult(str):
    """String response body with attached HTTP metadata for logging."""

    def __new__(
        cls,
        text: str,
        *,
        method: str,
        url: str,
        status_code: int | None,
        ok: bool | None,
        response_length: int,
        content_type: str | None = None,
    ):
        value = str.__new__(cls, text)
        value.method = method
        value.url = url
        value.status_code = status_code
        value.ok = ok
        value.response_length = response_length
        value.content_type = content_type
        return value


def from_response(method: str, url: str, response: requests.Response) -> HttpToolResult:
    """Return response text with metadata attached."""

    text = response.text
    return HttpToolResult(
        text,
        method=method,
        url=url,
        status_code=response.status_code,
        ok=response.ok,
        response_length=len(text),
        content_type=response.headers.get("Content-Type"),
    )


def metadata_from_result(result: Any) -> dict[str, Any]:
    """Extract HTTP metadata from a result when available."""

    if not isinstance(result, HttpToolResult):
        return {}
    return {
        "method": result.method,
        "target": result.url,
        "http_status": result.status_code,
        "http_ok": result.ok,
        "response_length": result.response_length,
        "content_type": result.content_type,
    }
