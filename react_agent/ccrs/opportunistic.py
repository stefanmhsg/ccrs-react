from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig

from react_agent.ccrs.runtime import CcrsRuntime, CcrsRuntimeError, get_default_runtime


logger = logging.getLogger(__name__)
LOG_PREFIX = "[Opportunistic CCRS]"


def make_opportunistic_ccrs_node(runtime: CcrsRuntime | None = None):
    """Create a LangGraph node that derives opportunistic CCRS from Turtle."""

    def opportunistic_ccrs_node(state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        # Opportunistic CCRS runs after tools so it can interpret fresh RDF observations.
        messages = state.get("messages", [])
        if not messages:
            logger.warning("%s No messages found in state.", LOG_PREFIX)
            return {}

        last = messages[-1]
        if not isinstance(last, ToolMessage):
            logger.info(
                "%s Last message is not a ToolMessage; skipping opportunistic CCRS.",
                LOG_PREFIX,
            )
            return {}

        if not isinstance(last.content, str):
            logger.info(
                "%s ToolMessage content is not text/Turtle; skipping opportunistic CCRS.",
                LOG_PREFIX,
            )
            return {}

        active_runtime = _runtime_from_config(config) or runtime or get_default_runtime()
        context = _tool_message_context(last)
        logger.info(
            "%s Evaluating tool observation with Java VocabularyMatcher.scanAll; "
            "tool_call_id=%s tool_name=%s content_length=%s",
            LOG_PREFIX,
            context.get("tool_call_id"),
            context.get("tool_name"),
            len(last.content),
        )

        try:
            ccrs_entries = active_runtime.evaluate_turtle(last.content, context=context)
        except CcrsRuntimeError:
            logger.exception("%s Java CCRS runtime failed.", LOG_PREFIX)
            return {}
        except Exception:
            logger.exception("%s Failed to evaluate tool observation.", LOG_PREFIX)
            return {}

        if not ccrs_entries:
            logger.info(
                "%s Java opportunistic CCRS returned no entries; tool_call_id=%s",
                LOG_PREFIX,
                context.get("tool_call_id"),
            )
            return {}

        logger.info(
            "%s Java opportunistic CCRS returned %s entries; tool_call_id=%s",
            LOG_PREFIX,
            len(ccrs_entries),
            context.get("tool_call_id"),
        )
        logger.debug("%s CCRS entries: %s", LOG_PREFIX, ccrs_entries)
        return {"ccrs": ccrs_entries}

    return opportunistic_ccrs_node


def _runtime_from_config(config: RunnableConfig) -> CcrsRuntime | None:
    configuration = (config or {}).get("configurable", {})
    runtime = configuration.get("ccrs_runtime")
    if runtime is not None and not isinstance(runtime, CcrsRuntime):
        raise TypeError("configurable.ccrs_runtime must be a CcrsRuntime instance")
    return runtime


def _tool_message_context(message: ToolMessage) -> dict[str, str]:
    context = {
        "tool_call_id": str(message.tool_call_id),
    }
    if message.name:
        context["tool_name"] = str(message.name)
    return context
