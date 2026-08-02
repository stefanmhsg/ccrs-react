"""Routing regressions for contingency escalation and advisory stop control."""

from __future__ import annotations

import unittest

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from react_agent.ccrs.contingency.decision import route_after_ccrs_decision
from react_agent.ccrs.contingency.stop_confirmation import (
    ACCEPT_STOP_TOOL_NAME,
    CONTINUE_RUN_TOOL_NAME,
    STOP_CONFIRMATION_PROMPT,
    pending_stop_suggestion,
    make_stop_confirmation_node,
    route_after_ccrs_node,
    route_after_stop_confirmation,
    stop_confirmation_control_node,
)
from react_agent.graph.graph_ccrs import build_graph
from react_agent.tools import tools


def _stop_entry(*, trace_id: str = "trace-stop", completed: bool = False) -> dict:
    suggestion = {
        "strategy_id": "stop",
        "action_type": "stop",
        "confidence": 1.0,
        "rationale": "Repeated contingency guidance did not restore progress.",
    }
    return {
        "trace_id": trace_id,
        "completed": completed,
        "stop": True,
        "top_suggestion": suggestion,
        "suggestions": [suggestion],
    }


def _confirmation_message(name: str, trace_id: str = "trace-stop") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": name,
                "args": {
                    "trace_id": trace_id,
                    "rationale": "The run-specific checks support this decision.",
                },
                "id": "confirmation-call",
                "type": "tool_call",
            }
        ],
    )


class ContingencyDecisionTest(unittest.TestCase):
    def test_confirmation_prompt_explains_origin_without_prescribing_criteria(self) -> None:
        prompt = STOP_CONFIRMATION_PROMPT.format_messages(
            messages=[],
            stop_suggestion='{"trace_id": "trace-stop"}',
            decision_context='{"custom_rule": "agent-defined"}',
        )[0].content

        self.assertIn("requested earlier in this run", prompt)
        self.assertIn("either by\nyou or automatically by your agent program", prompt)
        self.assertIn("agent-specific decision context supports", prompt)
        self.assertIn("normal action tools will become available", prompt)
        self.assertNotIn("token or cost budget", prompt)
        self.assertNotIn("safety constraints", prompt)

    def test_ccrs_graph_contains_conditional_stop_confirmation_gate(self) -> None:
        graph = build_graph().get_graph()
        edges = {(edge.source, edge.target) for edge in graph.edges}

        self.assertIn("stop_confirmation", graph.nodes)
        self.assertIn("stop_control", graph.nodes)
        self.assertIn(("ccrs", "stop_confirmation"), edges)
        self.assertIn(("stop_confirmation", "stop_control"), edges)
        self.assertIn(("stop_control", "__end__"), edges)
        self.assertIn(("stop_control", "llm"), edges)

    def test_reusable_decision_route_delegates_non_ccrs_control_to_agent(self) -> None:
        self.assertEqual("ccrs", route_after_ccrs_decision({"contingency_situation": {}}))
        self.assertEqual("agent", route_after_ccrs_decision({}))

    def test_pending_stop_routes_to_confirmation(self) -> None:
        state = {"contingency_ccrs": [_stop_entry()]}

        pending = pending_stop_suggestion(state)

        self.assertIsNotNone(pending)
        self.assertEqual("trace-stop", pending[0]["trace_id"])
        self.assertEqual("stop_confirmation", route_after_ccrs_node(state))

    def test_completed_or_non_stop_results_do_not_expose_confirmation(self) -> None:
        non_stop = _stop_entry(trace_id="trace-retry")
        non_stop["top_suggestion"] = {
            "strategy_id": "retry",
            "action_type": "retry",
        }
        non_stop["suggestions"] = [non_stop["top_suggestion"]]

        self.assertEqual(
            "continue",
            route_after_ccrs_node(
                {"contingency_ccrs": [_stop_entry(completed=True), non_stop]}
            ),
        )

    def test_stop_control_tools_are_not_normal_agent_tools(self) -> None:
        normal_names = {getattr(entry, "name", None) for entry in tools}

        self.assertNotIn(ACCEPT_STOP_TOOL_NAME, normal_names)
        self.assertNotIn(CONTINUE_RUN_TOOL_NAME, normal_names)

    def test_confirmation_node_binds_only_stop_control_tools(self) -> None:
        observed: dict = {}

        class RecordingModel:
            def bind_tools(self, bound_tools, **kwargs):
                observed["tool_names"] = [entry.name for entry in bound_tools]
                observed["bind_options"] = kwargs

                def respond(prompt):
                    observed["prompt"] = "\n".join(
                        str(message.content) for message in prompt.to_messages()
                    )
                    return _confirmation_message(CONTINUE_RUN_TOOL_NAME)

                return RunnableLambda(respond)

        node = make_stop_confirmation_node(
            decision_context={
                "custom_agent_criterion": "configured-by-agent-designer"
            },
            model_factory=lambda _config: RecordingModel(),
        )

        updates = node(
            {
                "messages": [],
                "contingency_ccrs": [_stop_entry()],
                "cycle": {"number": 2},
            },
            {},
        )

        self.assertEqual(
            [ACCEPT_STOP_TOOL_NAME, CONTINUE_RUN_TOOL_NAME],
            observed["tool_names"],
        )
        self.assertFalse(observed["bind_options"]["parallel_tool_calls"])
        self.assertIn("configured-by-agent-designer", observed["prompt"])
        self.assertEqual(CONTINUE_RUN_TOOL_NAME, updates["messages"][0].tool_calls[0]["name"])

    def test_acceptance_completes_trace_and_returns_accepted(self) -> None:
        state = {
            "messages": [_confirmation_message(ACCEPT_STOP_TOOL_NAME)],
            "contingency_ccrs": [_stop_entry()],
            "cycle": {"number": 7},
        }

        updates = stop_confirmation_control_node(state, {})

        self.assertTrue(updates["contingency_ccrs"][0]["completed"])
        self.assertEqual(
            "accepted",
            route_after_stop_confirmation({"messages": updates["messages"]}),
        )

    def test_declining_completes_trace_and_returns_to_agent(self) -> None:
        state = {
            "messages": [_confirmation_message(CONTINUE_RUN_TOOL_NAME)],
            "contingency_ccrs": [_stop_entry()],
        }

        updates = stop_confirmation_control_node(state, {})

        self.assertTrue(updates["contingency_ccrs"][0]["completed"])
        self.assertEqual(
            "declined",
            route_after_stop_confirmation({"messages": updates["messages"]}),
        )

    def test_stale_trace_cannot_authorize_stop(self) -> None:
        state = {
            "messages": [_confirmation_message(ACCEPT_STOP_TOOL_NAME, "stale-trace")],
            "contingency_ccrs": [_stop_entry()],
        }

        updates = stop_confirmation_control_node(state, {})

        self.assertNotIn("contingency_ccrs", updates)
        self.assertEqual(1, len(updates["messages"]))
        self.assertEqual(
            "invalid",
            route_after_stop_confirmation({"messages": updates["messages"]}),
        )

    def test_missing_control_call_does_not_reuse_an_older_decision(self) -> None:
        state = {
            "messages": [AIMessage(content="I cannot decide.")],
            "contingency_ccrs": [_stop_entry()],
        }

        updates = stop_confirmation_control_node(state, {})

        self.assertEqual({}, updates)
        self.assertEqual("invalid", route_after_stop_confirmation(state))

    def test_multiple_control_calls_cannot_authorize_stop(self) -> None:
        message = _confirmation_message(ACCEPT_STOP_TOOL_NAME)
        message.tool_calls.append(
            {
                "name": CONTINUE_RUN_TOOL_NAME,
                "args": {"trace_id": "trace-stop", "rationale": "conflict"},
                "id": "second-call",
                "type": "tool_call",
            }
        )
        state = {
            "messages": [message],
            "contingency_ccrs": [_stop_entry()],
        }

        updates = stop_confirmation_control_node(state, {})

        self.assertNotIn("contingency_ccrs", updates)
        self.assertEqual(2, len(updates["messages"]))
        self.assertEqual(
            "invalid",
            route_after_stop_confirmation({"messages": updates["messages"]}),
        )


if __name__ == "__main__":
    unittest.main()
