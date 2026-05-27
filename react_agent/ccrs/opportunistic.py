from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig

from react_agent.ccrs.audit import log_ccrs_event
from react_agent.ccrs.rdf_adapter import CcrsRdfParseError
from react_agent.ccrs.runtime import CcrsRuntime, CcrsRuntimeError, get_default_runtime


logger = logging.getLogger(__name__)
LOG_PREFIX = "[React CCRS][Opportunistic]"


def make_opportunistic_ccrs_node(runtime: CcrsRuntime | None = None):
    """Create a LangGraph node that derives opportunistic CCRS from Turtle."""

    def opportunistic_ccrs_node(state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        # Opportunistic CCRS runs after tools so it can interpret fresh RDF observations.
        messages = state.get("messages", [])
        if not messages:
            _log_cycle_event("react.ccrs.opportunistic.skipped", state, config, {"reason": "no_messages"})
            return {}

        last = messages[-1]
        if not isinstance(last, ToolMessage):
            _log_cycle_event("react.ccrs.opportunistic.skipped", state, config, {"reason": "not_tool_message"})
            return {}

        if not isinstance(last.content, str):
            _log_cycle_event(
                "react.ccrs.opportunistic.skipped",
                state,
                config,
                {
                    "reason": "non_text_tool_content",
                    "tool_call_id": str(last.tool_call_id),
                    "tool_name": last.name,
                },
            )
            return {}

        active_runtime = _runtime_from_config(config) or runtime or get_default_runtime()
        context = _tool_message_context(last, state, config)
        log_ccrs_event(
            logger,
            "react.ccrs.opportunistic.evaluate",
            {
                **_cycle_fields(state, config),
                "tool_call_id": context.get("tool_call_id"),
                "tool_name": context.get("tool_name"),
                "content_length": len(last.content),
            },
        )

        try:
            ccrs_entries = active_runtime.evaluate_turtle(last.content, context=context)
        except CcrsRdfParseError:
            _log_cycle_event(
                "react.ccrs.opportunistic.skipped",
                state,
                config,
                {
                    "reason": "invalid_turtle",
                    "tool_call_id": context.get("tool_call_id"),
                    "tool_name": context.get("tool_name"),
                    "content_length": len(last.content),
                },
            )
            return {}
        except CcrsRuntimeError:
            logger.exception("%s Java CCRS runtime failed.", LOG_PREFIX)
            _log_cycle_event(
                "react.ccrs.opportunistic.failed",
                state,
                config,
                {
                    "reason": "runtime_error",
                    "tool_call_id": context.get("tool_call_id"),
                    "tool_name": context.get("tool_name"),
                },
            )
            return {}
        except Exception:
            logger.exception("%s Failed to evaluate tool observation.", LOG_PREFIX)
            _log_cycle_event(
                "react.ccrs.opportunistic.failed",
                state,
                config,
                {
                    "reason": "evaluation_error",
                    "tool_call_id": context.get("tool_call_id"),
                    "tool_name": context.get("tool_name"),
                },
            )
            return {}

        if not ccrs_entries:
            _log_cycle_event(
                "react.ccrs.opportunistic.no_annotations",
                state,
                config,
                {
                    "tool_call_id": context.get("tool_call_id"),
                    "tool_name": context.get("tool_name"),
                    "entries": 0,
                },
            )
            return {}

        for entry in ccrs_entries:
            log_ccrs_event(
                logger,
                "react.ccrs.opportunistic.detected",
                {
                    **_cycle_fields(state, config),
                    "tool_call_id": context.get("tool_call_id"),
                    "tool_name": context.get("tool_name"),
                    "target": entry.get("target"),
                    "type": entry.get("type"),
                    "pattern_id": entry.get("pattern_id"),
                    "utility": entry.get("utility"),
                },
            )
        _log_cycle_event(
            "react.ccrs.opportunistic.cycle_annotations",
            state,
            config,
            {
                "tool_call_id": context.get("tool_call_id"),
                "tool_name": context.get("tool_name"),
                "entries": len(ccrs_entries),
            },
        )
        logger.debug("%s Appending CCRS entries: %s", LOG_PREFIX, ccrs_entries)
        return {"ccrs": ccrs_entries}

    return opportunistic_ccrs_node


def _runtime_from_config(config: RunnableConfig) -> CcrsRuntime | None:
    configuration = (config or {}).get("configurable", {})
    runtime = configuration.get("ccrs_runtime")
    if runtime is not None and not isinstance(runtime, CcrsRuntime):
        raise TypeError("configurable.ccrs_runtime must be a CcrsRuntime instance")
    return runtime


def _tool_message_context(
    message: ToolMessage,
    state: dict[str, Any],
    config: RunnableConfig,
) -> dict[str, str]:
    context = {
        "tool_call_id": str(message.tool_call_id),
        "origin": "react-opportunistic-ccrs",
    }
    if message.name:
        context["tool_name"] = str(message.name)
    context.update(_cycle_fields(state, config))
    return context


def _cycle_fields(state: dict[str, Any], config: RunnableConfig) -> dict[str, str]:
    configuration = (config or {}).get("configurable", {})
    cycle = state.get("cycle", {})
    fields = {
        "agent_name": str(configuration.get("agent_name", "React")),
        "cycle": str(cycle.get("number", 0)),
        "cycle_timestamp": str(cycle.get("timestamp", "")),
    }
    return fields


def _log_cycle_event(
    event: str,
    state: dict[str, Any],
    config: RunnableConfig,
    fields: dict[str, Any],
) -> None:
    log_ccrs_event(logger, event, {**_cycle_fields(state, config), **fields})
