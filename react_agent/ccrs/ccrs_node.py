"""LangGraph node that coordinates React-side CCRS state updates."""

from __future__ import annotations

from typing import Any

import json
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from react_agent.ccrs.contingency.ccrs_context import InMemoryCcrsContext
from react_agent.ccrs.contingency.contingency_ccrs import (
    ContingencyCcrs,
    get_default_contingency_ccrs,
)
from react_agent.ccrs.contingency.escalation import (
    ESCALATE_TO_CONTINGENCY_CCRS_TOOL_NAME,
)
from react_agent.ccrs.contingency.opportunistic_guidance import (
    opportunistic_guidance_from_contingency_ccrs_result,
)
from react_agent.ccrs.contingency.situation import Situation
from react_agent.ccrs.opportunistic.vocabulary_matcher import (
    VocabularyMatcher,
    evaluate_latest_tool_observation,
)


CONTINGENCY_SITUATION_STATE_KEY = "contingency_situation"


def make_ccrs_node(
    vocabulary_matcher: VocabularyMatcher | None = None,
    contingency_ccrs: ContingencyCcrs | None = None,
    ccrs_trace_history: Any | None = None,
):
    """Create the graph-facing CCRS node used by the CCRS graph variant."""

    def ccrs_node(state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        updates: dict[str, Any] = {}

        opportunistic_entries = evaluate_latest_tool_observation(
            state,
            config,
            vocabulary_matcher=vocabulary_matcher,
        )
        if opportunistic_entries:
            updates["opportunistic_ccrs"] = opportunistic_entries

        contingency_result = _evaluate_contingency_if_requested(
            state,
            config,
            contingency_ccrs=contingency_ccrs,
            ccrs_trace_history=ccrs_trace_history,
        )
        if contingency_result is not None:
            updates["contingency_ccrs"] = [contingency_result]
            updates["opportunistic_guidance_by_contingency_ccrs"] = (
                opportunistic_guidance_from_contingency_ccrs_result(contingency_result)
            )
            updates[CONTINGENCY_SITUATION_STATE_KEY] = None
            tool_messages = _acknowledge_escalation_tool_calls(state, contingency_result)
            if tool_messages:
                updates["messages"] = tool_messages

        return updates

    return ccrs_node


def _evaluate_contingency_if_requested(
    state: dict[str, Any],
    config: RunnableConfig,
    *,
    contingency_ccrs: ContingencyCcrs | None = None,
    ccrs_trace_history: Any | None = None,
) -> dict[str, Any] | None:
    situation = _contingency_situation_from_state_or_config(state, config)
    if situation is None:
        return None

    configuration = (config or {}).get("configurable", {})
    active_contingency_ccrs = (
        _contingency_ccrs_from_config(config)
        or contingency_ccrs
        or get_default_contingency_ccrs()
    )
    context = _contingency_context_from_config(config)
    if context is None:
        context = InMemoryCcrsContext.from_messages(
            state.get("messages", []),
            agent_id=str(configuration.get("agent_name", "React")),
            current_resource=configuration.get("current_resource"),
            ccrs_history=configuration.get("ccrs_trace_history") or ccrs_trace_history,
            outcome_classifier=configuration.get("ccrs_outcome_classifier"),
        )

    result = active_contingency_ccrs.evaluate(situation, context=context)
    result.setdefault("completed", False)
    return result


def _contingency_situation_from_state_or_config(
    state: dict[str, Any],
    config: RunnableConfig,
) -> Situation | dict[str, Any] | None:
    if state.get(CONTINGENCY_SITUATION_STATE_KEY) is not None:
        return state[CONTINGENCY_SITUATION_STATE_KEY]
    configuration = (config or {}).get("configurable", {})
    return configuration.get(CONTINGENCY_SITUATION_STATE_KEY)


def _contingency_ccrs_from_config(config: RunnableConfig) -> ContingencyCcrs | None:
    configuration = (config or {}).get("configurable", {})
    configured = configuration.get("contingency_ccrs")
    if configured is not None and not isinstance(configured, ContingencyCcrs):
        raise TypeError("configurable.contingency_ccrs must be a ContingencyCcrs instance")
    return configured


def _contingency_context_from_config(config: RunnableConfig) -> Any | None:
    configuration = (config or {}).get("configurable", {})
    return configuration.get("ccrs_context")


def _acknowledge_escalation_tool_calls(
    state: dict[str, Any],
    contingency_result: dict[str, Any],
) -> list[ToolMessage]:
    latest = state.get("messages", [])[-1] if state.get("messages") else None
    if not isinstance(latest, AIMessage):
        return []

    messages: list[ToolMessage] = []
    for call in latest.tool_calls or []:
        tool_name = call.get("name") or "unknown_tool"
        if tool_name == ESCALATE_TO_CONTINGENCY_CCRS_TOOL_NAME:
            content = {
                "contingency_ccrs_escalation": "accepted",
                "trace_id": contingency_result.get("trace_id"),
                "top_suggestion": contingency_result.get("top_suggestion"),
                "stop": contingency_result.get("stop"),
            }
            status = "success"
        else:
            content = {
                "skipped": True,
                "reason": "contingency_ccrs_escalation_selected",
                "tool_name": tool_name,
            }
            status = "error"

        messages.append(
            ToolMessage(
                content=json.dumps(content),
                name=str(tool_name),
                tool_call_id=call.get("id"),
                status=status,
            )
        )
    return messages


ccrs_node = make_ccrs_node()
