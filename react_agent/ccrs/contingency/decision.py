"""LangGraph routing helpers for contingency CCRS escalation."""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from react_agent.ccrs.contingency.escalation import decide_contingency_ccrs_escalation


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
    """Return whether CCRS or the embedding agent owns the next route."""

    if state.get("contingency_situation") is not None:
        return "ccrs"
    return "agent"
