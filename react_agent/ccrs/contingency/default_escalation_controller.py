"""Default contingency CCRS escalation policy for React agents.

The default policy is intentionally small and message-driven. It recognizes an
explicit LLM escalation request first, then escalates after configurable
consecutive HTTP API errors or tool invocation failures.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from react_agent.ccrs.contingency.escalation import (
    ContingencyCcrsEscalationDecision,
    explicit_contingency_ccrs_escalation_decision,
)
from react_agent.ccrs.contingency.http_status import http_status_from_tool_message
from react_agent.ccrs.contingency.situation import Situation, SituationType


@dataclass
class DefaultContingencyCcrsEscalationController:
    """Default controller for explicit escalation and repeated tool problems."""

    failed_tool_threshold: int = 2
    http_error_threshold: int = 5

    def decide(
        self,
        state: dict[str, Any],
        config: RunnableConfig,
    ) -> ContingencyCcrsEscalationDecision:
        explicit = explicit_contingency_ccrs_escalation_decision(state, config)
        if explicit is not None:
            return explicit

        configuration = (config or {}).get("configurable", {})
        http_error_threshold = _configured_threshold(
            configuration,
            key="contingency_http_error_threshold",
            default=self.http_error_threshold,
        )
        http_error_decision = _consecutive_http_error_decision(
            state,
            config,
            http_error_threshold=http_error_threshold,
        )
        if http_error_decision.escalate:
            return http_error_decision

        failed_tool_threshold = _configured_threshold(
            configuration,
            key="contingency_failed_tool_threshold",
            default=self.failed_tool_threshold,
        )
        return _repeated_tool_failure_decision(
            state,
            config,
            failed_tool_threshold=failed_tool_threshold,
        )


def _configured_threshold(
    configuration: Mapping[str, Any],
    *,
    key: str,
    default: int,
) -> int:
    try:
        return max(1, int(configuration.get(key, default)))
    except (TypeError, ValueError):
        return max(1, int(default))


def _consecutive_http_error_decision(
    state: dict[str, Any],
    config: RunnableConfig,
    *,
    http_error_threshold: int,
) -> ContingencyCcrsEscalationDecision:
    errors = _latest_consecutive_http_error_responses(state)
    if len(errors) < max(1, int(http_error_threshold)):
        return ContingencyCcrsEscalationDecision(
            escalate=False,
            reason="no_escalation_condition_met",
        )

    latest_error = errors[0]
    call = _tool_call_for_message(state, latest_error)
    configuration = (config or {}).get("configurable", {})
    args = call.get("args") if isinstance(call.get("args"), Mapping) else {}
    tool_name = str(latest_error.name or call.get("name") or "unknown_tool")
    status_codes = [
        status
        for status in (http_status_from_tool_message(message) for message in errors)
        if status is not None
    ]
    situation = Situation(
        type=SituationType.FAILURE,
        trigger="consecutive_http_api_errors",
        current_resource=configuration.get("current_resource"),
        target_resource=args.get("url") if isinstance(args, Mapping) else None,
        failed_action=tool_name,
        error_info={
            "http_error_count": len(errors),
            "http_error_threshold": max(1, int(http_error_threshold)),
            "latest_http_status": status_codes[0] if status_codes else None,
            "status_codes": status_codes,
        },
        metadata={
            "tool_call_id": str(latest_error.tool_call_id),
            "tool_name": tool_name,
            "cycle": state.get("cycle", {}).get("number"),
        },
    )
    return ContingencyCcrsEscalationDecision(
        escalate=True,
        situation=situation,
        reason="consecutive_http_api_errors",
        skip_tool_node=True,
    )


def _repeated_tool_failure_decision(
    state: dict[str, Any],
    config: RunnableConfig,
    *,
    failed_tool_threshold: int,
) -> ContingencyCcrsEscalationDecision:
    failures = _latest_consecutive_tool_failures(state)
    if len(failures) < max(1, int(failed_tool_threshold)):
        return ContingencyCcrsEscalationDecision(
            escalate=False,
            reason="no_escalation_condition_met",
        )

    latest_failure = failures[0]
    call = _tool_call_for_message(state, latest_failure)
    configuration = (config or {}).get("configurable", {})
    args = call.get("args") if isinstance(call.get("args"), Mapping) else {}
    tool_name = str(latest_failure.name or call.get("name") or "unknown_tool")
    situation = Situation(
        type=SituationType.FAILURE,
        trigger="repeated_tool_failure",
        current_resource=configuration.get("current_resource"),
        target_resource=args.get("url") if isinstance(args, Mapping) else None,
        failed_action=tool_name,
        error_info={
            "failed_tool_count": len(failures),
            "latest_tool_status": latest_failure.status,
        },
        metadata={
            "tool_call_id": str(latest_failure.tool_call_id),
            "tool_name": tool_name,
            "cycle": state.get("cycle", {}).get("number"),
        },
    )
    return ContingencyCcrsEscalationDecision(
        escalate=True,
        situation=situation,
        reason="repeated_tool_failure",
        skip_tool_node=True,
    )


def _latest_consecutive_tool_failures(state: Mapping[str, Any]) -> list[ToolMessage]:
    failures: list[ToolMessage] = []
    for message in reversed(state.get("messages", [])):
        if isinstance(message, AIMessage):
            if failures:
                continue
            continue
        if not isinstance(message, ToolMessage):
            continue
        if _is_failed_tool_message(message):
            failures.append(message)
            continue
        break
    return failures


def _latest_consecutive_http_error_responses(state: Mapping[str, Any]) -> list[ToolMessage]:
    errors: list[ToolMessage] = []
    for message in reversed(state.get("messages", [])):
        if isinstance(message, AIMessage):
            continue
        if not isinstance(message, ToolMessage):
            continue
        status = http_status_from_tool_message(message)
        if status is not None and status >= 400:
            errors.append(message)
            continue
        break
    return errors


def _is_failed_tool_message(message: ToolMessage) -> bool:
    if message.status == "error":
        return True
    if isinstance(message.content, str):
        try:
            value = json.loads(message.content)
        except json.JSONDecodeError:
            return False
        return isinstance(value, Mapping) and bool(value.get("error"))
    return False


def _tool_call_for_message(state: Mapping[str, Any], tool_message: ToolMessage) -> dict[str, Any]:
    target_id = str(tool_message.tool_call_id)
    for message in reversed(state.get("messages", [])):
        if not isinstance(message, AIMessage):
            continue
        for call in message.tool_calls or []:
            if str(call.get("id")) == target_id:
                return call
    return {}
