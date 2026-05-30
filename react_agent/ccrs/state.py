from operator import add
from typing import Annotated, Any, NotRequired, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def merge_contingency_ccrs(
    current: list[dict[str, Any]] | None,
    updates: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Append contingency CCRS entries and merge completion updates by trace id."""

    merged = [dict(entry) for entry in (current or [])]
    for update in updates or []:
        key = _contingency_ccrs_key(update)
        if key is None:
            merged.append(dict(update))
            continue

        for index, existing in enumerate(merged):
            if _contingency_ccrs_key(existing) == key:
                merged[index] = {**existing, **update}
                break
        else:
            merged.append(dict(update))
    return merged


def _contingency_ccrs_key(entry: dict[str, Any]) -> str | None:
    for key in ("trace_id", "id", "invocation_id", "ccrs_id"):
        value = entry.get(key)
        if value is not None:
            return f"{key}:{value}"
    return None


class CcrsAgentState(TypedDict):
    """LangGraph state shape for ReAct agents equipped with CCRS."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    cycle: dict[str, Any]
    # Java VocabularyMatcher annotations derived from concrete tool observations.
    opportunistic_ccrs: Annotated[list[dict[str, Any]], add]
    # Java contingency evaluations. Pending entries are injected once, then marked completed.
    contingency_ccrs: Annotated[list[dict[str, Any]], merge_contingency_ccrs]
    # Contingency-produced opportunistic guidance, replaced by each contingency evaluation.
    opportunistic_guidance_by_contingency_ccrs: list[dict[str, Any]]
    # Transient input that asks the CCRS node to run contingency evaluation.
    contingency_situation: NotRequired[Any | None]
