"""Default prompt text for injecting CCRS context into React agents."""

from __future__ import annotations

import json
from typing import Any

from react_agent.ccrs.contingency.escalation import ESCALATE_TO_CONTINGENCY_CCRS_TOOL_NAME


DEFAULT_CCRS_SYSTEM_PROMPT = """{ccrs}"""

NO_CCRS_OUTPUT_PROMPT = """Your agentic loop contains a Course Check and Revision Strategy (CCRS) component that is designed to help you to successfully complete your task even if the environment is dynamic and uncertain.

CCRS will be injected here if available - currently no CCRS output available."""

CCRS_OUTPUT_PROMPT = """Your agentic loop contains a Course Check and Revision Strategy (CCRS) component that is designed to help you to successfully complete your task even if the environment is dynamic and uncertain.

CCRS is comprised of two main components:
1. Opportunistic CCRS:
    - These are helpful annotations that may be injected into your prompt context at any time.
    - They are advisory in nature and are meant to help you to make better decisions.
    - Injected annotations relate to the currently perceived state of the environment.
    - Annotations are based on known or assumed information about the environment that may be useful for you in the current situation.

    Here are the injected opportunistic annotations.
        - "target" is the URI that the annotation is about.
        - "type" is the category of the annotation, which indicates what kind of information it conveys.
        - "utility" is a number between 0 and 1 that indicates how useful the annotation is expected to be for your decision-making in the current situation. Higher utility means more useful.

    {opportunistic_annotations}

2. Contingency CCRS:
    - These are specific strategies that are executed by the CCRS component if their execution was triggered explicitly. They take into account your current and previous interactions and the states of the environment.
        - Your agentic loop may trigger the execution of contingency CCRS based on certain conditions.
        - You may trigger the execution of contingency CCRS yourself if the {escalate_to_contingency_ccrs_tool_name} tool is available to you.
    - The result of executed contingency CCRS is prescriptive guidance for how to proceed in the current situation.
    - Contingency output can be injected in two forms:
        - "contingency_ccrs" contains direct contingency strategy results for the current situation.
        - "opportunistic_guidance_by_contingency_ccrs" contains contingency-produced opportunistic guidance that may stay relevant across multiple follow-up steps when its target matches the current RDF observation.

    Here are the injected contingency CCRS results.
    {contingency_ccrs}

    Here is the injected contingency-produced opportunistic guidance.
    {opportunistic_guidance_by_contingency_ccrs}"""


def render_ccrs_prompt_context(
    *,
    opportunistic_annotations: list[dict[str, Any]],
    contingency_ccrs: list[dict[str, Any]],
    opportunistic_guidance_by_contingency_ccrs: list[dict[str, Any]],
) -> str:
    """Render prompt-visible CCRS details or a compact no-output message."""

    if not (
        opportunistic_annotations
        or contingency_ccrs
        or opportunistic_guidance_by_contingency_ccrs
    ):
        return NO_CCRS_OUTPUT_PROMPT

    return CCRS_OUTPUT_PROMPT.format(
        escalate_to_contingency_ccrs_tool_name=ESCALATE_TO_CONTINGENCY_CCRS_TOOL_NAME,
        opportunistic_annotations=_to_json(opportunistic_annotations),
        contingency_ccrs=_to_json(contingency_ccrs),
        opportunistic_guidance_by_contingency_ccrs=_to_json(
            opportunistic_guidance_by_contingency_ccrs
        ),
    )


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)
