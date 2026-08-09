"""Application-level integration checks for the external ccrs-langgraph adapter."""

from __future__ import annotations

import unittest

from ccrs_langgraph.contingency.stop_confirmation import (
    ACCEPT_STOP_TOOL_NAME,
    CONTINUE_RUN_TOOL_NAME,
)
from react_agent.graph.graph_ccrs import build_graph
from react_agent.tools import tools


class CcrsLangGraphIntegrationTest(unittest.TestCase):
    def test_ccrs_graph_contains_conditional_stop_confirmation_gate(self) -> None:
        graph = build_graph().get_graph()
        edges = {(edge.source, edge.target) for edge in graph.edges}

        self.assertIn("stop_confirmation", graph.nodes)
        self.assertIn("stop_control", graph.nodes)
        self.assertIn(("ccrs", "stop_confirmation"), edges)
        self.assertIn(("stop_confirmation", "stop_control"), edges)
        self.assertIn(("stop_control", "__end__"), edges)
        self.assertIn(("stop_control", "llm"), edges)

    def test_stop_control_tools_are_not_normal_agent_tools(self) -> None:
        normal_names = {getattr(entry, "name", None) for entry in tools}

        self.assertNotIn(ACCEPT_STOP_TOOL_NAME, normal_names)
        self.assertNotIn(CONTINUE_RUN_TOOL_NAME, normal_names)


if __name__ == "__main__":
    unittest.main()
