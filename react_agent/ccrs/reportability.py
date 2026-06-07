"""Reportability helpers for React CCRS experiment logs."""

from __future__ import annotations

from typing import Any
from uuid import uuid4


def new_prompt_context_id() -> str:
    """Return a compact id that correlates prompt-visible and selection events."""

    return f"prompt-{uuid4().hex}"


def selected_tool_target(tool_call: dict[str, Any]) -> str | None:
    """Extract the URI-like target selected by an LLM tool call."""

    args = tool_call.get("args")
    if isinstance(args, dict):
        url = args.get("url")
        if url is not None:
            return str(url)
        target = args.get("target") or args.get("uri")
        if target is not None:
            return str(target)
    return None


def top_opportunistic_target(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the highest utility opportunistic entry, or an empty dict."""

    return _top_target(entries, ("utility",))


def top_contingency_guidance_target(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the highest-ranked contingency-produced guidance entry."""

    return _top_target(entries, ("utility", "confidence", "rank"))


def _top_target(
    entries: list[dict[str, Any]],
    score_keys: tuple[str, ...],
) -> dict[str, Any]:
    if not entries:
        return {}

    best_entry: dict[str, Any] | None = None
    best_score: float | None = None
    best_score_key: str | None = None
    best_index = len(entries)

    for index, entry in enumerate(entries):
        score_key, score = _first_numeric_score(entry, score_keys)
        if best_entry is None:
            best_entry = entry
            best_score = score
            best_score_key = score_key
            best_index = index
            continue

        if score is not None:
            if best_score is None or score > best_score:
                best_entry = entry
                best_score = score
                best_score_key = score_key
                best_index = index
        elif best_score is None and index < best_index:
            best_entry = entry
            best_index = index

    if best_entry is None:
        return {}

    result: dict[str, Any] = {
        "target": best_entry.get("target"),
        "score": best_score,
        "score_key": best_score_key,
    }
    return {key: value for key, value in result.items() if value is not None}


def _first_numeric_score(
    entry: dict[str, Any],
    score_keys: tuple[str, ...],
) -> tuple[str | None, float | None]:
    for key in score_keys:
        value = entry.get(key)
        try:
            if value is None or value == "":
                continue
            return key, float(value)
        except (TypeError, ValueError):
            continue
    return None, None

