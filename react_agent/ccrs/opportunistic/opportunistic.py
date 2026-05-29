"""LangGraph node for Java-backed opportunistic CCRS scans.

The node inspects the latest `ToolMessage`, sends Turtle observations to the
Java `VocabularyMatcher` wrapper, and appends opportunistic CCRS annotations to
LangGraph state.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig

from react_agent.ccrs.audit import log_ccrs_event
from react_agent.ccrs.java_runtime import CcrsJavaRuntimeError
from react_agent.ccrs.rdf_adapter import CcrsRdfParseError
from react_agent.ccrs.opportunistic.vocabulary_matcher import (
    VocabularyMatcher,
    get_default_vocabulary_matcher,
)


logger = logging.getLogger(__name__)
LOG_PREFIX = "[React CCRS][Opportunistic]"


def make_opportunistic_ccrs_node(vocabulary_matcher: VocabularyMatcher | None = None):
    """Create a LangGraph node backed by Java `VocabularyMatcher`."""

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

        active_matcher = _vocabulary_matcher_from_config(config) or vocabulary_matcher or get_default_vocabulary_matcher()
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
            ccrs_entries = active_matcher.evaluate_turtle(last.content, context=context)
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
        except CcrsJavaRuntimeError:
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


def _vocabulary_matcher_from_config(config: RunnableConfig) -> VocabularyMatcher | None:
    configuration = (config or {}).get("configurable", {})
    vocabulary_matcher = configuration.get("vocabulary_matcher")
    if vocabulary_matcher is not None and not isinstance(vocabulary_matcher, VocabularyMatcher):
        raise TypeError("configurable.vocabulary_matcher must be a VocabularyMatcher instance")
    return vocabulary_matcher


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


opportunistic_ccrs_node = make_opportunistic_ccrs_node()
