"""LangGraph routing helpers for contingency CCRS escalation."""

from __future__ import annotations

import logging

from langchain_core.runnables import RunnableConfig

from react_agent.ccrs.contingency.escalation import decide_contingency_ccrs_escalation
from react_agent.nodes.decision_node import should_continue


logger = logging.getLogger(__name__)


def make_ccrs_decision_node(contingency_escalation_controller=None):
    """Create the CCRS graph decision node."""

    def ccrs_decision_node(state: dict, config: RunnableConfig) -> dict:
        decision = decide_contingency_ccrs_escalation(
            state,
            config,
            controller=contingency_escalation_controller,
        )
        return {
            "contingency_situation": decision.situation if decision.escalate else None,
        }

    return ccrs_decision_node


def route_after_ccrs_decision(state: dict) -> str:
    """Route after the CCRS decision node has had a chance to set a Situation."""

    if state.get("contingency_situation") is not None:
        return "ccrs"
    return should_continue(state)


def route_after_ccrs_node(state: dict) -> str:
    """Terminate when contingency CCRS returns an uncompleted stop suggestion."""

    for entry in reversed(state.get("contingency_ccrs", []) or []):
        if entry.get("completed"):
            continue
        if entry.get("stop"):
            logger.info("Contingency CCRS returned stop. Ending process.")
            return "end"
        break
    return "continue"
