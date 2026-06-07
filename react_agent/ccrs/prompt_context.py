"""Build the JSON CCRS context injected into the React prompt."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from langchain_core.runnables import RunnableConfig

from react_agent.ccrs.contingency.contingency_ccrs_result import (
    get_pending_contingency_ccrs,
    mark_contingency_ccrs_completed,
)
from react_agent.ccrs.contingency.opportunistic_guidance import (
    get_opportunistic_guidance_by_contingency_ccrs,
)
from react_agent.ccrs.opportunistic.opportunistic_result import (
    get_opportunistic_ccrs_for_latest_tool_calls,
)
from react_agent.ccrs.prompt import render_ccrs_prompt_context
from react_agent.ccrs.audit import log_ccrs_event
from react_agent.ccrs.reportability import (
    new_prompt_context_id,
    top_contingency_guidance_target,
    top_opportunistic_target,
)
from react_agent.ccrs.state import CcrsAgentState


logger = logging.getLogger(__name__)


def print_ccrs_prompt_context(text: str) -> None:
    """Print the CCRS context that is about to be injected into the LLM prompt."""

    print("\n[CCRS PROMPT CONTEXT]")
    print(text)
    print("[/CCRS PROMPT CONTEXT]\n")


@dataclass(frozen=True)
class CcrsPromptContext:
    """Prompt-ready CCRS payload and state updates after LLM consumption."""

    text: str
    payload: dict[str, Any]
    pending_contingency_ccrs: list[dict[str, Any]]
    prompt_context_id: str
    opportunistic_count: int
    contingency_guidance_count: int
    top_opportunistic_target: str | None
    top_contingency_guidance_target: str | None

    def post_llm_updates(self) -> dict[str, Any]:
        """Return state updates that should be applied after the LLM sees this context."""

        if not self.pending_contingency_ccrs:
            return {}
        return {
            "contingency_ccrs": mark_contingency_ccrs_completed(
                self.pending_contingency_ccrs
            )
        }


def build_ccrs_prompt_context(
    state: CcrsAgentState,
    config: RunnableConfig,
) -> CcrsPromptContext:
    """Collect CCRS state channels and render the prompt-visible JSON context."""

    opportunistic_context = get_opportunistic_ccrs_for_latest_tool_calls(state)
    pending_contingency_ccrs = get_pending_contingency_ccrs(state)
    contingency_opportunistic_guidance = get_opportunistic_guidance_by_contingency_ccrs(
        state,
        config,
    )
    prompt_opportunistic_annotations = _prompt_opportunistic_annotations(
        opportunistic_context
    )
    prompt_context_id = new_prompt_context_id()
    top_opportunistic = top_opportunistic_target(prompt_opportunistic_annotations)
    top_contingency_guidance = top_contingency_guidance_target(
        contingency_opportunistic_guidance
    )
    payload = {
        "prompt_context_id": prompt_context_id,
        "opportunistic_annotations": prompt_opportunistic_annotations,
        "contingency_ccrs": pending_contingency_ccrs,
        "opportunistic_guidance_by_contingency_ccrs": contingency_opportunistic_guidance,
    }
    text = render_ccrs_prompt_context(
        opportunistic_annotations=prompt_opportunistic_annotations,
        contingency_ccrs=pending_contingency_ccrs,
        opportunistic_guidance_by_contingency_ccrs=contingency_opportunistic_guidance,
    )

    if (
        opportunistic_context
        or pending_contingency_ccrs
        or contingency_opportunistic_guidance
    ):
        logger.info(
            "Injecting %s opportunistic CCRS entries, %s pending contingency CCRS entries, and %s contingency-produced opportunistic guidance entries to LLM.",
            len(opportunistic_context),
            len(pending_contingency_ccrs),
            len(contingency_opportunistic_guidance),
        )
        log_ccrs_event(
            logger,
            "react.ccrs.prompt_context.visible",
            {
                **_cycle_fields(state, config),
                "opportunistic_count": len(prompt_opportunistic_annotations),
                "contingency_pending_count": len(pending_contingency_ccrs),
                "contingency_guidance_count": len(contingency_opportunistic_guidance),
                "top_opportunistic_target": top_opportunistic.get("target"),
                "top_opportunistic_score": top_opportunistic.get("score"),
                "top_contingency_guidance_target": top_contingency_guidance.get("target"),
                "top_contingency_guidance_score": top_contingency_guidance.get("score"),
                "prompt_context_id": prompt_context_id,
            },
        )
        logger.info("CCRS prompt context: %s", text)
        print_ccrs_prompt_context(text)

    return CcrsPromptContext(
        text=text,
        payload=payload,
        pending_contingency_ccrs=pending_contingency_ccrs,
        prompt_context_id=prompt_context_id,
        opportunistic_count=len(prompt_opportunistic_annotations),
        contingency_guidance_count=len(contingency_opportunistic_guidance),
        top_opportunistic_target=top_opportunistic.get("target"),
        top_contingency_guidance_target=top_contingency_guidance.get("target"),
    )


def _prompt_opportunistic_annotations(
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [_prompt_opportunistic_annotation(entry) for entry in entries]


def _prompt_opportunistic_annotation(entry: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(entry.get("metadata") or {})
    prompt_entry = {
        "type": entry.get("type"),
        "target": entry.get("target"),
        "pattern_id": entry.get("pattern_id"),
        "utility": entry.get("utility"),
        "metadata": metadata,
    }
    return {key: value for key, value in prompt_entry.items() if value is not None}


def _cycle_fields(state: CcrsAgentState, config: RunnableConfig) -> dict[str, Any]:
    configuration = (config or {}).get("configurable", {})
    cycle = state.get("cycle", {})
    return {
        "cycle": str(cycle.get("number", 0)),
        "cycle_timestamp": str(cycle.get("timestamp", "")),
        "agent_name": str(configuration.get("agent_name", "React")),
    }
