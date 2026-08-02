"""Reusable LangGraph confirmation gate for advisory StopStrategy results."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from react_agent.ccrs.audit import log_ccrs_event
from react_agent.ccrs.contingency.contingency_ccrs_result import (
    mark_contingency_ccrs_completed,
)


logger = logging.getLogger(__name__)

ACCEPT_STOP_TOOL_NAME = "accept_stop"
CONTINUE_RUN_TOOL_NAME = "continue_run"


class StopConfirmationChoice(str, Enum):
    """Semantic outcome returned to the graph that embeds the CCRS adapter."""

    ACCEPTED = "accepted"
    DECLINED = "declined"
    INVALID = "invalid"


class StopConfirmationInput(BaseModel):
    """Arguments binding an agent decision to one StopStrategy trace."""

    trace_id: str = Field(
        description="Trace id of the StopStrategy suggestion currently under review."
    )
    rationale: str = Field(
        description=(
            "Concise reason for accepting or declining the advisory stop according "
            "to the agent-specific decision context presented for this review."
        )
    )


@tool(ACCEPT_STOP_TOOL_NAME, args_schema=StopConfirmationInput)
def accept_stop(trace_id: str, rationale: str) -> str:
    """Accept the currently presented StopStrategy suggestion.

    This control capability is exposed only while a matching, unconsumed
    StopStrategy suggestion is being reviewed. Graph control validates the
    trace id before allowing the embedding agent to terminate.
    """

    return json.dumps(
        {
            "stop_confirmation": StopConfirmationChoice.ACCEPTED.value,
            "trace_id": trace_id,
            "rationale": rationale,
        }
    )


@tool(CONTINUE_RUN_TOOL_NAME, args_schema=StopConfirmationInput)
def continue_run(trace_id: str, rationale: str) -> str:
    """Decline the currently presented StopStrategy suggestion and continue."""

    return json.dumps(
        {
            "stop_confirmation": StopConfirmationChoice.DECLINED.value,
            "trace_id": trace_id,
            "rationale": rationale,
        }
    )


STOP_CONFIRMATION_TOOLS = (accept_stop, continue_run)

STOP_CONFIRMATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """A contingency CCRS evaluation was requested earlier in this run, either by
you or automatically by your agent program because normal execution appeared
unable to make progress.

That evaluation has returned an advisory StopStrategy suggestion. CCRS has not
stopped the run. You must decide whether to accept the suggestion according to
the agent-specific decision context below.

Only two control tools are available for this decision:

- Call `accept_stop` if the supplied agent-specific decision context supports
  stopping the run.
- Call `continue_run` if the supplied agent-specific decision context does not
  support stopping the run. Your normal action tools will become available
  again on the next agent decision.

Choose exactly one control tool and copy the supplied contingency CCRS trace id
exactly. The trace id connects your decision to the specific StopStrategy
suggestion shown below.

Contingency CCRS StopStrategy suggestion:
{stop_suggestion}

Agent-specific decision context:
{decision_context}""",
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)


ModelFactory = Callable[[RunnableConfig], Any]
MessageProvider = Callable[
    [Mapping[str, Any], RunnableConfig],
    Sequence[Any],
]


def pending_stop_suggestion(
    state: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Return the newest unconsumed suggestion produced by StopStrategy."""

    for entry in reversed(state.get("contingency_ccrs", []) or []):
        if entry.get("completed", False):
            continue
        suggestions = entry.get("suggestions") or []
        top_suggestion = entry.get("top_suggestion")
        if isinstance(top_suggestion, Mapping):
            suggestions = [top_suggestion, *suggestions]
        for suggestion in suggestions:
            if not isinstance(suggestion, Mapping):
                continue
            if (
                suggestion.get("strategy_id") == "stop"
                and suggestion.get("action_type") == "stop"
            ):
                return dict(entry), dict(suggestion)
    return None


def route_after_ccrs_node(state: Mapping[str, Any]) -> str:
    """Route a pending StopStrategy suggestion through explicit confirmation."""

    return "stop_confirmation" if pending_stop_suggestion(state) else "continue"


def make_stop_confirmation_node(
    *,
    decision_context: Any = None,
    model_factory: ModelFactory | None = None,
    message_provider: MessageProvider | None = None,
    prompt_template: ChatPromptTemplate | None = None,
):
    """Create a model-injectable node with conditionally exposed stop controls."""

    def stop_confirmation_node(
        state: Mapping[str, Any],
        config: RunnableConfig,
    ) -> dict[str, Any]:
        pending = pending_stop_suggestion(state)
        if pending is None:
            raise ValueError(
                "Stop confirmation requires an uncompleted StopStrategy suggestion."
            )
        entry, suggestion = pending
        trace_id = str(entry.get("trace_id") or "")
        if not trace_id:
            raise ValueError("StopStrategy confirmation requires a contingency trace id.")

        configuration = (config or {}).get("configurable", {})
        active_model_factory = model_factory or _default_model_factory
        llm = active_model_factory(config)
        model = llm.bind_tools(
            list(STOP_CONFIRMATION_TOOLS),
            tool_choice="any",
            parallel_tool_calls=False,
        )
        active_prompt = prompt_template or STOP_CONFIRMATION_PROMPT
        chain = active_prompt | model
        active_decision_context = configuration.get(
            "stop_decision_context",
            decision_context,
        )
        messages = list(
            (message_provider or _default_message_provider)(state, config)
        )
        response = chain.invoke(
            {
                "messages": messages,
                "stop_suggestion": _json(
                    {"trace_id": trace_id, "suggestion": suggestion}
                ),
                "decision_context": _json(active_decision_context or {}),
            },
            config,
        )

        next_cycle = int(state.get("cycle", {}).get("number", 0)) + 1
        cycle_timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        log_ccrs_event(
            logger,
            "react.ccrs.stop.presented",
            {
                "cycle": next_cycle,
                "cycle_timestamp": cycle_timestamp,
                "agent_name": str(configuration.get("agent_name", "React")),
                "trace_id": trace_id,
            },
        )
        return {
            "messages": [response],
            "cycle": {"number": next_cycle, "timestamp": cycle_timestamp},
        }

    return stop_confirmation_node


def stop_confirmation_control_node(
    state: Mapping[str, Any],
    config: RunnableConfig,
) -> dict[str, Any]:
    """Validate and acknowledge the latest stop confirmation tool call."""

    pending = pending_stop_suggestion(state)
    decision, _, reason = _read_confirmation_decision(state, pending)
    configuration = (config or {}).get("configurable", {})
    trace_id = str(pending[0].get("trace_id")) if pending is not None else None
    event = {
        StopConfirmationChoice.ACCEPTED: "react.ccrs.stop.accepted",
        StopConfirmationChoice.DECLINED: "react.ccrs.stop.declined",
        StopConfirmationChoice.INVALID: "react.ccrs.stop.invalid",
    }[decision]
    log_ccrs_event(
        logger,
        event,
        {
            "cycle": state.get("cycle", {}).get("number"),
            "agent_name": str(configuration.get("agent_name", "React")),
            "trace_id": trace_id,
            "reason": reason,
        },
    )

    updates: dict[str, Any] = {}
    latest = _latest_ai_message(state)
    calls_to_ack = list(latest.tool_calls or []) if latest is not None else []
    if calls_to_ack:
        updates["messages"] = [
            ToolMessage(
                content=json.dumps(
                    {
                        "stop_confirmation": decision.value,
                        "trace_id": trace_id,
                        "reason": reason,
                    }
                ),
                name=str(control_call.get("name") or "stop_confirmation"),
                tool_call_id=str(control_call.get("id") or "stop-confirmation"),
                status=(
                    "success"
                    if decision is not StopConfirmationChoice.INVALID
                    else "error"
                ),
                response_metadata={"ccrs_stop_confirmation": decision.value},
            )
            for control_call in calls_to_ack
        ]
    if pending is not None and decision is not StopConfirmationChoice.INVALID:
        updates["contingency_ccrs"] = mark_contingency_ccrs_completed([pending[0]])
    return updates


def route_after_stop_confirmation(state: Mapping[str, Any]) -> str:
    """Return the semantic result recorded by the stop control node."""

    for message in reversed(state.get("messages", []) or []):
        if isinstance(message, ToolMessage):
            value = message.response_metadata.get("ccrs_stop_confirmation")
            if value in {choice.value for choice in StopConfirmationChoice}:
                return str(value)
        if isinstance(message, AIMessage):
            break
    return StopConfirmationChoice.INVALID.value


def _read_confirmation_decision(
    state: Mapping[str, Any],
    pending: tuple[dict[str, Any], dict[str, Any]] | None,
) -> tuple[StopConfirmationChoice, Mapping[str, Any] | None, str]:
    latest = _latest_ai_message(state)
    calls = list(latest.tool_calls or []) if latest is not None else []
    if len(calls) != 1:
        return (
            StopConfirmationChoice.INVALID,
            calls[0] if calls else None,
            "exactly_one_control_call_required",
        )
    call = calls[0]
    name = call.get("name")
    if name not in {ACCEPT_STOP_TOOL_NAME, CONTINUE_RUN_TOOL_NAME}:
        return StopConfirmationChoice.INVALID, call, "unknown_control_call"
    if pending is None:
        return StopConfirmationChoice.INVALID, call, "no_pending_stop_suggestion"
    args = call.get("args") if isinstance(call.get("args"), Mapping) else {}
    expected_trace_id = str(pending[0].get("trace_id") or "")
    if not expected_trace_id or str(args.get("trace_id") or "") != expected_trace_id:
        return StopConfirmationChoice.INVALID, call, "trace_id_mismatch"
    if name == ACCEPT_STOP_TOOL_NAME:
        return StopConfirmationChoice.ACCEPTED, call, "agent_accepted_stop"
    return StopConfirmationChoice.DECLINED, call, "agent_declined_stop"


def _latest_ai_message(state: Mapping[str, Any]) -> AIMessage | None:
    for message in reversed(state.get("messages", []) or []):
        if isinstance(message, AIMessage):
            return message
    return None


def _default_model_factory(config: RunnableConfig) -> ChatOpenAI:
    configuration = (config or {}).get("configurable", {})
    return ChatOpenAI(
        model=configuration.get("llm_model", "gpt-5-mini"),
        temperature=configuration.get("llm_temperature", 1.0),
        reasoning_effort=configuration.get("llm_reasoning_effort", "minimal"),
    )


def _default_message_provider(
    state: Mapping[str, Any],
    config: RunnableConfig,
) -> Sequence[Any]:
    """Return conversation messages without assuming an agent-specific window."""

    del config
    return state.get("messages", []) or []


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)
