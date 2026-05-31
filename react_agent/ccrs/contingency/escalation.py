"""Contingency CCRS escalation decisions for React graph routing.

This module decides whether a React graph cycle should construct a Java
contingency `Situation`. It does not execute contingency CCRS; execution stays
in `ContingencyCcrs`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from react_agent.ccrs.audit import log_ccrs_event
from react_agent.ccrs.contingency.situation import Situation, SituationType


logger = logging.getLogger(__name__)
ESCALATE_TO_CONTINGENCY_CCRS_TOOL_NAME = "escalate_to_contingency_ccrs"


class EscalateToContingencyCcrsInput(BaseModel):
    """Arguments for asking graph control to invoke contingency CCRS."""

    type: str = Field(
        default=SituationType.UNCERTAINTY.value,
        description=(
            "Situation category for the recovery request. Use FAILURE for failed actions "
            "or repeated HTTP errors, STUCK when actions succeed but do not make progress, "
            "UNCERTAINTY when the next useful action is unclear, and PROACTIVE when asking "
            "for preventive guidance before spending more tool calls."
        ),
    )
    trigger: str = Field(
        default="llm_self_escalation",
        description=(
            "Short machine-readable trigger, such as blocked_navigation, "
            "repeated_unproductive_action, inaccessible_target, contradictory_observation, "
            "or llm_self_escalation."
        ),
    )
    current_resource: str | None = Field(
        default=None,
        description=(
            "Best-known current resource or state, for example the URI of the resource, page, "
            "record, or object the agent is currently at. Leave null if unknown."
        ),
    )
    target_resource: str | None = Field(
        default=None,
        description=(
            "Resource the agent is trying to reach, inspect, modify, or recover toward. "
            "Use the concrete URI or identifier when available."
        ),
    )
    failed_action: str | None = Field(
        default=None,
        description=(
            "Tool name, action, or attempted step that failed or stopped making progress, "
            "for example http_get, http_post, move east, or retry same target."
        ),
    )
    reason: str | None = Field(
        default=None,
        description=(
            "Concise explanation of why normal tool use is unlikely to help without "
            "contingency guidance. Include key observations or status codes."
        ),
    )


@tool(ESCALATE_TO_CONTINGENCY_CCRS_TOOL_NAME, args_schema=EscalateToContingencyCcrsInput)
def escalate_to_contingency_ccrs(
    type: str = SituationType.UNCERTAINTY.value,
    trigger: str = "llm_self_escalation",
    current_resource: str | None = None,
    target_resource: str | None = None,
    failed_action: str | None = None,
    reason: str | None = None,
) -> str:
    """Ask for contingency CCRS guidance instead of making another normal tool call.

    Use this when you are blocked, uncertain, repeatedly getting failed or
    unhelpful observations, cannot access an intended next resource, see
    contradictory evidence, or expect another ordinary retry to waste cycles.
    Calling this tool does not execute an environment action. It asks graph
    control to skip normal tool execution for this cycle, invoke contingency
    CCRS, and make the resulting recovery suggestion available in the next CCRS
    prompt context.
    """

    return json.dumps(
        {
            "escalate_to_contingency_ccrs": True,
            "type": type,
            "trigger": trigger,
            "current_resource": current_resource,
            "target_resource": target_resource,
            "failed_action": failed_action,
            "reason": reason,
        }
    )


@dataclass(frozen=True)
class ContingencyCcrsEscalationDecision:
    """Decision output consumed by CCRS graph routing."""

    escalate: bool
    situation: Situation | None = None
    reason: str | None = None
    skip_tool_node: bool = True


class ContingencyCcrsEscalationController(Protocol):
    """Policy object that decides whether to create a contingency `Situation`."""

    def decide(
        self,
        state: dict[str, Any],
        config: RunnableConfig,
    ) -> ContingencyCcrsEscalationDecision:
        """Return the escalation decision for the current graph cycle."""


def decide_contingency_ccrs_escalation(
    state: dict[str, Any],
    config: RunnableConfig,
    *,
    controller: ContingencyCcrsEscalationController | None = None,
) -> ContingencyCcrsEscalationDecision:
    """Decide whether the current cycle should route into contingency CCRS."""

    active_controller = _controller_from_config(config) or controller
    if active_controller is None:
        from react_agent.ccrs.contingency.default_escalation_controller import (
            DefaultContingencyCcrsEscalationController,
        )

        active_controller = DefaultContingencyCcrsEscalationController()

    log_ccrs_event(
        logger,
        "react.ccrs.contingency.escalation.considered",
        {
            "cycle": state.get("cycle", {}).get("number"),
            "controller": type(active_controller).__name__,
            "explicit_escalation_tool_call": has_explicit_escalation_tool_call(state),
        },
    )
    decision = active_controller.decide(state, config)
    _log_decision(state, decision)
    return decision


def has_explicit_escalation_tool_call(state: Mapping[str, Any]) -> bool:
    """Return whether the latest AI message requests contingency escalation."""

    latest = _latest_ai_message(state)
    if latest is None:
        return False
    return any(_is_escalation_tool_call(call) for call in latest.tool_calls or [])


def _controller_from_config(
    config: RunnableConfig,
) -> ContingencyCcrsEscalationController | None:
    configuration = (config or {}).get("configurable", {})
    configured = configuration.get("contingency_escalation_controller")
    if configured is None:
        return None
    if not hasattr(configured, "decide"):
        raise TypeError(
            "configurable.contingency_escalation_controller must provide decide(state, config)"
        )
    return configured


def explicit_contingency_ccrs_escalation_decision(
    state: dict[str, Any],
    config: RunnableConfig,
) -> ContingencyCcrsEscalationDecision | None:
    """Return a decision from the latest explicit LLM escalation tool call."""

    latest = _latest_ai_message(state)
    if latest is None:
        return None

    for call in latest.tool_calls or []:
        if not _is_escalation_tool_call(call):
            continue
        situation = _situation_from_escalation_call(call, state, config)
        return ContingencyCcrsEscalationDecision(
            escalate=True,
            situation=situation,
            reason="explicit_llm_escalation",
            skip_tool_node=True,
        )
    return None


def _situation_from_escalation_call(
    call: Mapping[str, Any],
    state: Mapping[str, Any],
    config: RunnableConfig,
) -> Situation:
    args = call.get("args") if isinstance(call.get("args"), Mapping) else {}
    configuration = (config or {}).get("configurable", {})
    return Situation(
        type=str(args.get("type") or SituationType.UNCERTAINTY.value),
        trigger=str(args.get("trigger") or "llm_self_escalation"),
        current_resource=args.get("current_resource") or configuration.get("current_resource"),
        target_resource=args.get("target_resource"),
        failed_action=args.get("failed_action"),
        error_info={
            "reason": args.get("reason"),
        },
        metadata={
            "tool_call_id": str(call.get("id") or ""),
            "tool_name": ESCALATE_TO_CONTINGENCY_CCRS_TOOL_NAME,
            "cycle": state.get("cycle", {}).get("number"),
        },
    )


def _latest_ai_message(state: Mapping[str, Any]) -> AIMessage | None:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, AIMessage):
            return message
    return None


def _is_escalation_tool_call(call: Mapping[str, Any]) -> bool:
    return call.get("name") == ESCALATE_TO_CONTINGENCY_CCRS_TOOL_NAME


def _log_decision(
    state: Mapping[str, Any],
    decision: ContingencyCcrsEscalationDecision,
) -> None:
    event = (
        "react.ccrs.contingency.escalation.activated"
        if decision.escalate
        else "react.ccrs.contingency.escalation.skipped"
    )
    situation = decision.situation
    log_ccrs_event(
        logger,
        event,
        {
            "cycle": state.get("cycle", {}).get("number"),
            "reason": decision.reason,
            "skip_tool_node": decision.skip_tool_node,
            "situation_type": situation.type_name if situation is not None else None,
            "trigger": situation.trigger if situation is not None else None,
            "current_resource": situation.current_resource if situation is not None else None,
            "target_resource": situation.target_resource if situation is not None else None,
            "failed_action": situation.failed_action if situation is not None else None,
        },
    )
