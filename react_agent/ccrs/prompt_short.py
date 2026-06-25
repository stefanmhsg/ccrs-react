"""Short prompt text for injecting CCRS decision guidance into ReAct agents."""

from __future__ import annotations

import json
from typing import Any

from react_agent.ccrs.contingency.escalation import ESCALATE_TO_CONTINGENCY_CCRS_TOOL_NAME


NO_CCRS_OUTPUT_PROMPT = "## CCRS Decision Guidance\nNo CCRS recommendation is currently available."


def render_ccrs_prompt_context(
    *,
    opportunistic_annotations: list[dict[str, Any]],
    contingency_ccrs: list[dict[str, Any]],
    opportunistic_guidance_by_contingency_ccrs: list[dict[str, Any]],
) -> str:
    """Render compact CCRS guidance for the next ReAct decision."""

    if not (
        opportunistic_annotations
        or contingency_ccrs
        or opportunistic_guidance_by_contingency_ccrs
    ):
        return NO_CCRS_OUTPUT_PROMPT

    sections = ["## CCRS Decision Guidance"]
    sections.append(_render_opportunistic_guidance(opportunistic_annotations))
    sections.append(
        _render_contingency_guidance(
            contingency_ccrs=contingency_ccrs,
            opportunistic_guidance_by_contingency_ccrs=(
                opportunistic_guidance_by_contingency_ccrs
            ),
        )
    )
    return "\n\n".join(section for section in sections if section)


def _render_opportunistic_guidance(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "### Opportunistic CCRS\nNo opportunistic CCRS recommendation is currently available."

    ranked_entries = sorted(
        entries,
        key=lambda entry: _utility(entry),
        reverse=True,
    )
    lines = [
        "### Opportunistic CCRS",
        "Use these ranked findings as decision support. They are derived from a scan of your recent percepts.",
    ]
    if _has_unique_top_utility(ranked_entries):
        top = ranked_entries[0]
        lines.extend(
            [
                "",
                "Top recommendation:",
                f"- Target: `{_value(top, 'target')}`",
                f"- Suggested because: {_suggested_because(top)}",
                f"- Expected utility: {_utility(top):.2f} / 1.00",
            ]
        )

    lines.append("")
    lines.append("Ranked findings:")
    for rank, entry in _ranked_with_ties(ranked_entries):
        lines.append(
            f"{rank}. `{_value(entry, 'target')}` - {_suggested_because(entry)}; "
            f"expected utility {_utility(entry):.2f} / 1.00"
        )
    return "\n".join(lines)


def _render_contingency_guidance(
    *,
    contingency_ccrs: list[dict[str, Any]],
    opportunistic_guidance_by_contingency_ccrs: list[dict[str, Any]],
) -> str:
    if not (contingency_ccrs or opportunistic_guidance_by_contingency_ccrs):
        return "### Contingency CCRS\nNo contingency CCRS result is currently pending."

    return "\n".join(
        [
            "### Contingency CCRS",
            "Contingency CCRS remains verbose for debugging and recovery context.",
            f"If you are stuck, confused, or making no progress, use `{ESCALATE_TO_CONTINGENCY_CCRS_TOOL_NAME}` when available.",
            "",
            "Pending contingency results:",
            _to_json(contingency_ccrs),
            "",
            "Contingency-produced opportunistic guidance:",
            _to_json(opportunistic_guidance_by_contingency_ccrs),
        ]
    )


def _suggested_because(entry: dict[str, Any]) -> str:
    ccrs_type = str(entry.get("type") or "CCRS finding")
    pattern = _pattern_name(entry.get("pattern_id"))
    if pattern:
        return f"{ccrs_type} `{pattern}`"
    return ccrs_type


def _pattern_name(pattern_id: Any) -> str:
    if pattern_id is None:
        return ""
    value = str(pattern_id).rstrip("/#")
    for separator in ("#", "/"):
        if separator in value:
            return value.rsplit(separator, 1)[-1]
    return value


def _utility(entry: dict[str, Any]) -> float:
    try:
        value = float(entry.get("utility", 0.0))
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, value))


def _has_unique_top_utility(entries: list[dict[str, Any]]) -> bool:
    if len(entries) == 1:
        return True
    return _utility(entries[0]) > _utility(entries[1])


def _ranked_with_ties(entries: list[dict[str, Any]]) -> list[tuple[int, dict[str, Any]]]:
    ranked: list[tuple[int, dict[str, Any]]] = []
    previous_utility: float | None = None
    current_rank = 0
    for index, entry in enumerate(entries, start=1):
        utility = _utility(entry)
        if previous_utility is None or utility < previous_utility:
            current_rank = index
        ranked.append((current_rank, entry))
        previous_utility = utility
    return ranked


def _value(entry: dict[str, Any], key: str) -> str:
    value = entry.get(key)
    return str(value) if value is not None else "unknown"


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)
