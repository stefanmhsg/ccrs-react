"""Parse and render advertised maze navigation options."""

from __future__ import annotations

import json
from typing import Any

from react_agent.ccrs.rdf_adapter import CcrsRdfParseError, parse_turtle_triples

DYNMAZE_NAMESPACE = "https://paul.ti.rw.fau.de/~am52etar/dynmaze/dynmaze#"
MAZE_VOCAB_NAMESPACE = "https://kaefer3000.github.io/2021-02-dagstuhl/vocab#"
ENTERS_FROM_PREDICATE = f"{DYNMAZE_NAMESPACE}entersFrom"
CARDINAL_DIRECTIONS = ("north", "east", "south", "west")
DIRECTIONS = (*CARDINAL_DIRECTIONS, "exit")
DIRECTION_NAMESPACES = (MAZE_VOCAB_NAMESPACE, DYNMAZE_NAMESPACE)


def parse_advertised_navigation_options(
    content: str,
    *,
    current_cell: str,
    tool_call_id: str | None = None,
) -> dict[str, Any]:
    """Extract current-cell navigation options from a Turtle GET response."""

    triples = parse_turtle_triples(content)
    options: list[dict[str, str]] = []
    for direction in DIRECTIONS:
        predicates = {f"{namespace}{direction}" for namespace in DIRECTION_NAMESPACES}
        targets = sorted(
            {
                triple.object
                for triple in triples
                if triple.subject == current_cell
                and triple.predicate in predicates
                and _is_navigable_target(triple.object)
            }
        )
        for target in targets:
            options.append({"direction": direction, "target": target})

    return {
        "current_cell": current_cell,
        "source": "http_get",
        "source_tool_call_id": tool_call_id,
        "options": options,
        "cardinal_integrity": _cardinal_integrity(triples, current_cell=current_cell),
    }


def render_advertised_navigation_options(
    options_state: dict[str, Any] | None,
    *,
    agent_name: str,
    current_cell: str | None,
    contingency_escalation_tool_name: str | None = None,
) -> str:
    """Render prompt-visible concrete navigation options when still current."""

    if not options_state or not current_cell:
        return ""
    if options_state.get("current_cell") != current_cell:
        return ""

    options = options_state.get("options")
    if not isinstance(options, list):
        return ""

    lines = [
        "## Parsed Advertised Navigation Options",
        "",
        "These concrete options were parsed from a successful `http_get` of the tracked current cell.",
        "Use only these targets for navigation while the tracked current cell remains unchanged.",
        "",
        f"Current cell: `{current_cell}`",
    ]
    integrity_warning = _render_cardinal_integrity_warning(
        options_state.get("cardinal_integrity"),
        contingency_escalation_tool_name=contingency_escalation_tool_name,
    )
    if integrity_warning:
        lines.extend(["", integrity_warning])
    get_streak_warning = _render_same_cell_get_streak_warning(
        options_state.get("same_cell_get_streak")
    )
    if get_streak_warning:
        lines.extend(["", get_streak_warning])
    if not options:
        lines.extend(
            [
                "",
                "No navigable NESW/exit targets were advertised in the latest valid current-cell RDF.",
            ]
        )
        return "\n".join(lines)

    for option in options:
        if not isinstance(option, dict):
            continue
        direction = str(option.get("direction") or "").strip()
        target = str(option.get("target") or "").strip()
        if not direction or not target:
            continue
        tool_args = {
            "url": target,
            "data": (
                f"<http://127.0.1.1:8080/agents/{agent_name}> "
                f"<{ENTERS_FROM_PREDICATE}> <{current_cell}> ."
            ),
            "headers": {"Content-Type": "text/turtle"},
        }
        lines.extend(
            [
                "",
                f"- `{direction}` -> `{target}`",
                "  `http_post` arguments:",
                _indent(json.dumps(tool_args, ensure_ascii=False), "  "),
            ]
        )
    return "\n".join(lines)


def _render_same_cell_get_streak_warning(value: Any) -> str:
    try:
        streak = int(value or 0)
    except (TypeError, ValueError):
        return ""
    if streak < 2:
        return ""
    return (
        f"You have successfully perceived this same current cell {streak} times in a row. "
        "If the RDF already gives enough information, make progress with an appropriate "
        "`http_post`: either navigate to an advertised target or perform a valid interaction "
        "on the current cell."
    )


def _is_navigable_target(value: str) -> bool:
    normalized = value.strip()
    if not normalized:
        return False
    if normalized.endswith("#Wall") or normalized.endswith("/Wall"):
        return False
    return normalized.startswith("http://") or normalized.startswith("https://")


def _cardinal_integrity(triples, *, current_cell: str) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for direction in CARDINAL_DIRECTIONS:
        predicates = {f"{namespace}{direction}" for namespace in DIRECTION_NAMESPACES}
        counts[direction] = sum(
            1
            for triple in triples
            if triple.subject == current_cell and triple.predicate in predicates
        )
    ok = all(count == 1 for count in counts.values())
    return {
        "ok": ok,
        "counts": counts,
        "expected": "exactly_one_each_north_east_south_west",
    }


def _render_cardinal_integrity_warning(
    integrity: Any,
    *,
    contingency_escalation_tool_name: str | None,
) -> str:
    if not isinstance(integrity, dict) or integrity.get("ok") is not False:
        return ""
    counts = integrity.get("counts")
    if not isinstance(counts, dict):
        return ""
    count_text = ", ".join(
        f"{direction}={counts.get(direction, 0)}" for direction in CARDINAL_DIRECTIONS
    )
    lines = [
        "Unexpected maze structure noted: expected exactly one RDF predicate for each cardinal direction "
        f"(north/east/south/west), but observed {count_text}.",
    ]
    if contingency_escalation_tool_name:
        lines.append(
            f"Suggested next step: call `{contingency_escalation_tool_name}` before taking another normal maze action."
        )
    else:
        lines.append(
            "Consider whether you can do something about this; it may be important."
        )
    return "\n".join(lines)


def _indent(value: str, prefix: str) -> str:
    return "\n".join(f"{prefix}{line}" for line in value.splitlines())


__all__ = [
    "CcrsRdfParseError",
    "parse_advertised_navigation_options",
    "render_advertised_navigation_options",
]
