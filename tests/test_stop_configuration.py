"""Tests for the existing Settings-to-CLI stop configuration flow."""

from __future__ import annotations

import unittest

from main import (
    parse_args,
    stop_configuration_from_args,
    stop_decision_context_from_args,
)


class StopConfigurationTest(unittest.TestCase):
    def test_settings_defaults_flow_into_stop_configuration(self) -> None:
        args = parse_args(["--graph-name", "graph_ccrs"])

        self.assertEqual(
            {
                "no_suggestion_invocation_threshold": 2,
                "low_confidence_invocation_threshold": 3,
                "low_confidence_threshold": 0.5,
                "selection_reset_count_before_stop": 1,
                "trace_history_lookback_limit": 30,
            },
            stop_configuration_from_args(args),
        )

    def test_cli_overrides_all_stop_configuration_and_decision_criteria(self) -> None:
        args = parse_args(
            [
                "--graph-name",
                "graph_ccrs",
                "--stop-no-suggestion-invocation-threshold",
                "4",
                "--stop-low-confidence-invocation-threshold",
                "6",
                "--stop-low-confidence-threshold",
                "0.25",
                "--stop-selection-reset-count-before-stop",
                "2",
                "--stop-trace-history-lookback-limit",
                "40",
                "--stop-decision-accept-when",
                "agent accepts by custom rule",
                "--stop-decision-continue-when",
                "agent continues by custom rule",
            ]
        )

        self.assertEqual(
            {
                "no_suggestion_invocation_threshold": 4,
                "low_confidence_invocation_threshold": 6,
                "low_confidence_threshold": 0.25,
                "selection_reset_count_before_stop": 2,
                "trace_history_lookback_limit": 40,
            },
            stop_configuration_from_args(args),
        )
        self.assertEqual(
            {
                "decision_criteria": {
                    "accept_stop_when": ["agent accepts by custom rule"],
                    "continue_run_when": ["agent continues by custom rule"],
                },
            },
            stop_decision_context_from_args(args),
        )


if __name__ == "__main__":
    unittest.main()
