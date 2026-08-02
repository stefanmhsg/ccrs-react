"""Non-live integration tests for the Python-to-Java contingency bridge.

These tests start a real JPype JVM and load the Maven-local ``ccrs-core``
artifact. Publish the Java module before running them:

    cd ../ccrs-bdi
    ./gradlew :ccrs-core:publishToMavenLocal
"""

from __future__ import annotations

import logging
import os
import unittest
from pathlib import Path

from react_agent.ccrs.capabilities import CCRS_CORE_MODULE
from react_agent.ccrs.contingency import (
    ContingencyCcrs,
    InMemoryCcrsContext,
    Situation,
)
from react_agent.ccrs.contingency.interaction import Interaction, InteractionOutcome
from react_agent.ccrs.contingency.stop_confirmation import pending_stop_suggestion
from react_agent.ccrs.rdf_adapter import RdfTripleValue


GROUP_PATH = Path("io/github/stefanmhsg/ccrs")
VERSION = "0.1.0-SNAPSHOT"
CURRENT = "https://example.test/cells/blocked"
LOGGER = logging.getLogger(__name__)


def _maven_repo() -> Path:
    return Path(os.environ.get("M2_REPO", Path.home() / ".m2" / "repository"))


def _core_artifact_available() -> bool:
    artifact_dir = _maven_repo() / GROUP_PATH / CCRS_CORE_MODULE / VERSION
    return any(
        path.is_file()
        and not path.name.endswith("-sources.jar")
        and not path.name.endswith("-javadoc.jar")
        for path in artifact_dir.glob(f"{CCRS_CORE_MODULE}-{VERSION}*.jar")
    )


@unittest.skipUnless(
    _core_artifact_available(),
    "Maven-local ccrs-core artifact is unavailable; publish :ccrs-core first",
)
class JpypeContingencyIntegrationTest(unittest.TestCase):
    """Exercise the production JPype runtime and conversion path end to end."""

    def test_runtime_loads_core_classes_and_default_strategies(self) -> None:
        ccrs = ContingencyCcrs.from_maven_local()

        ccrs._ensure_runtime()

        self.assertEqual(
            {"retry", "backtrack", "stop"},
            set(ccrs._registered_strategy_ids().split(",")),
        )
        self.assertEqual(
            "ccrs.core.contingency.dto.Situation",
            str(ccrs._classes["Situation"].class_.getName()),
        )
        self.assertEqual(
            "ccrs.core.rdf.CcrsContext",
            str(ccrs._classes["CcrsContext"].class_.getName()),
        )

    def test_retry_configuration_and_result_round_trip(self) -> None:
        ccrs = ContingencyCcrs.from_maven_local(
            contingency_configuration={
                "max_level": 1,
                "retry": {
                    "max_attempts": 4,
                    "initial_delay_ms": 125,
                    "backoff_multiplier": 3.0,
                    "retriable_codes": ["429"],
                },
            },
        )
        situation = Situation(
            trigger="rate_limited",
            current_resource=CURRENT,
            target_resource="https://example.test/api/orders",
            failed_action="POST",
            error_info={"httpStatus": 429, "message": "Slow down"},
            metadata={"agent_name": "integration-agent", "cycle": 7},
        )

        result = ccrs.evaluate(situation)

        retry = _evaluation(result, "retry")
        self.assertEqual("APPLICABLE", retry["applicability"])
        suggestion = retry["result"]
        self.assertEqual("suggestion", suggestion["result_type"])
        self.assertEqual("retry", suggestion["action_type"])
        self.assertEqual("https://example.test/api/orders", suggestion["action_target"])
        self.assertEqual("POST", suggestion["action_params"]["originalAction"])
        self.assertEqual(125, suggestion["action_params"]["delayMs"])
        self.assertEqual(1, suggestion["action_params"]["attemptNumber"])
        self.assertEqual(4, suggestion["action_params"]["maxAttempts"])
        self.assertEqual(429, result["situation"]["error_info"]["httpStatus"])
        self.assertEqual(7, result["situation"]["metadata"]["cycle"])
        self.assertEqual("PARALLEL", result["strategy_selection"]["escalation_policy"])

    def test_learned_selection_configuration_round_trip(self) -> None:
        ccrs = ContingencyCcrs.from_maven_local(
            contingency_configuration={
                "learned_selection": False,
                "learning_history_limit": 13,
                "minimum_learning_samples": 4,
                "minimum_expected_confidence_gain": 0.23,
                "high_confidence_evaluation_floor": 0.87,
                "cheap_evaluation_time_ms": 777,
            },
        )

        ccrs._ensure_runtime()

        java_config = ccrs._contingency_ccrs.getConfig()
        self.assertFalse(java_config.isLearnedSelectionEnabled())
        self.assertEqual(13, java_config.getLearningHistoryLimit())
        self.assertEqual(4, java_config.getMinimumLearningSamples())
        self.assertAlmostEqual(0.23, java_config.getMinimumExpectedConfidenceGain())
        self.assertAlmostEqual(0.87, java_config.getHighConfidenceEvaluationFloor())
        self.assertEqual(777, java_config.getCheapEvaluationTimeMs())
        self.assertEqual(
            "TraceBasedStrategySelectionPolicy",
            str(ccrs._contingency_ccrs.getStrategySelectionPolicy().getDescription()),
        )

    def test_learned_gate_consumes_python_held_trace_history(self) -> None:
        checkpoint = "https://example.test/cells/checkpoint"
        transit = "https://example.test/cells/transit"
        link = "https://example.test/vocab#link"
        context = InMemoryCcrsContext(
            agent_id="integration-agent",
            triples=[
                RdfTripleValue(checkpoint, link, transit),
                RdfTripleValue(transit, link, CURRENT),
            ],
            interactions=[
                _interaction(
                    checkpoint,
                    InteractionOutcome.SUCCESS,
                    [RdfTripleValue(checkpoint, link, transit)],
                    1,
                ),
                _interaction(
                    transit,
                    InteractionOutcome.SUCCESS,
                    [RdfTripleValue(transit, link, CURRENT)],
                    2,
                ),
                _interaction(CURRENT, InteractionOutcome.SERVER_FAILURE, [], 3),
            ],
            current_resource=CURRENT,
        )
        ccrs = ContingencyCcrs.from_maven_local(
            contingency_configuration={
                "max_level": 2,
                "learned_selection": True,
                "learning_history_limit": 5,
                "minimum_learning_samples": 1,
                "minimum_expected_confidence_gain": 0.1,
                "high_confidence_evaluation_floor": 0.95,
                "cheap_evaluation_time_ms": 0,
            },
        )
        ccrs._ensure_runtime()
        _record_no_help_trace(
            ccrs,
            context,
            strategy_id="backtrack",
            escalation_level=2,
            evaluation_time_ms=500,
        )

        result = ccrs.evaluate(
            Situation(
                trigger="service_unavailable_while_navigation_is_blocked",
                current_resource=CURRENT,
                target_resource=CURRENT,
                failed_action="GET",
                error_info={"httpStatus": 503, "message": "Unavailable"},
            ),
            context,
        )

        self.assertEqual("retry", result["top_suggestion"]["strategy_id"])
        self.assertEqual(
            ["retry"],
            [evaluation["strategy_id"] for evaluation in result["evaluations"]],
        )
        recorded_trace = context.ccrs_history.getCcrsHistory(1)[0]
        self.assertTrue(recorded_trace.wasStrategyEvaluated("retry"))
        self.assertFalse(recorded_trace.wasStrategyEvaluated("backtrack"))

    def test_backtrack_crosses_exhausted_transit_via_python_context_proxy(self) -> None:
        checkpoint = "https://example.test/cells/checkpoint"
        transit = "https://example.test/cells/transit"
        unexplored = "https://example.test/cells/unexplored"
        link = "https://example.test/vocab#link"
        interactions = [
            _interaction(
                checkpoint,
                InteractionOutcome.SUCCESS,
                [
                    RdfTripleValue(checkpoint, link, transit),
                    RdfTripleValue(checkpoint, link, unexplored),
                ],
                1,
            ),
            _interaction(
                transit,
                InteractionOutcome.SUCCESS,
                [RdfTripleValue(transit, link, CURRENT)],
                2,
            ),
            _interaction(CURRENT, InteractionOutcome.SERVER_FAILURE, [], 3),
        ]
        context = InMemoryCcrsContext(
            agent_id="integration-agent",
            triples=[triple for interaction in interactions for triple in interaction.perceived_state],
            interactions=interactions,
            current_resource=CURRENT,
        )
        ccrs = ContingencyCcrs.from_maven_local(
            contingency_configuration={"max_level": 2},
        )

        result = ccrs.evaluate(
            Situation(
                trigger="dead_end",
                current_resource=CURRENT,
            ),
            context,
        )

        backtrack = _evaluation(result, "backtrack")
        self.assertEqual("APPLICABLE", backtrack["applicability"])
        suggestion = backtrack["result"]
        self.assertEqual("suggestion", suggestion["result_type"])
        self.assertEqual(checkpoint, suggestion["action_target"])
        self.assertEqual([transit, checkpoint], suggestion["action_params"]["backtrackPath"])
        self.assertEqual(2, suggestion["action_params"]["backtrackDistance"])
        self.assertEqual([unexplored], suggestion["action_params"]["alternativesByCheckpoint"][checkpoint])
        recorded_trace = context.ccrs_history.getCcrsHistory(10)[0]
        self.assertEqual(
            ["retry", "backtrack"],
            [str(item.getStrategyId()) for item in recorded_trace.getEvaluations()],
        )

    def test_stop_configuration_and_multi_invocation_result_round_trip(self) -> None:
        ccrs = ContingencyCcrs.from_maven_local(
            contingency_configuration={
                "max_level": 0,
                "stop": {
                    "no_suggestion_invocation_threshold": 2,
                    "low_confidence_invocation_threshold": 3,
                    "low_confidence_threshold": 0.4,
                    "selection_reset_count_before_stop": 1,
                    "trace_history_lookback_limit": 11,
                },
            },
        )
        context = InMemoryCcrsContext(
            agent_id="integration-agent",
            current_resource=CURRENT,
        )
        request = {
            "trigger": "no_safe_action_remains",
            "currentResource": CURRENT,
        }

        first = ccrs.evaluate(request, context)
        second = ccrs.evaluate(request, context)
        reconsideration = ccrs.evaluate(request, context)
        result = ccrs.evaluate(request, context)

        self.assertIsNone(first["top_suggestion"])
        self.assertIsNone(second["top_suggestion"])
        reset = _evaluation(reconsideration, "stop")["result"]
        self.assertEqual("no_help", reset["result_type"])
        self.assertEqual("SELECTION_RECONSIDERATION_REQUESTED", reset["reason"])

        stop = _evaluation(result, "stop")
        self.assertEqual("APPLICABLE", stop["applicability"])
        suggestion = stop["result"]
        self.assertEqual("suggestion", suggestion["result_type"])
        self.assertEqual("stop", suggestion["strategy_id"])
        self.assertEqual("stop", suggestion["action_type"])
        self.assertIsNone(suggestion["action_target"])
        self.assertEqual(2, suggestion["action_params"]["noSuggestionInvocationThreshold"])
        self.assertEqual(3, suggestion["action_params"]["lowConfidenceInvocationThreshold"])
        self.assertEqual(0.4, suggestion["action_params"]["lowConfidenceThreshold"])
        self.assertEqual(1, suggestion["action_params"]["selectionResetCountBeforeStop"])
        self.assertEqual(11, suggestion["action_params"]["traceHistoryLookbackLimit"])
        self.assertIn("agent retains the final decision", suggestion["rationale"])
        self.assertTrue(result["stop"])
        self.assertEqual(suggestion, result["top_suggestion"])
        pending = pending_stop_suggestion(
            {"contingency_ccrs": [{**result, "completed": False}]}
        )
        self.assertIsNotNone(pending)
        self.assertEqual(result["trace_id"], pending[0]["trace_id"])

        java_options = ccrs._contingency_ccrs.getConfig().getStopStrategyOptions()
        self.assertEqual(2, java_options.getNoSuggestionInvocationThreshold())
        self.assertEqual(3, java_options.getLowConfidenceInvocationThreshold())
        self.assertEqual(0.4, java_options.getLowConfidenceThreshold())
        self.assertEqual(1, java_options.getSelectionResetCountBeforeStop())
        self.assertEqual(11, java_options.getTraceHistoryLookbackLimit())


def _interaction(
    uri: str,
    outcome: str,
    perceived_state: list[RdfTripleValue],
    timestamp: int,
) -> Interaction:
    return Interaction(
        method="GET",
        request_uri=uri,
        request_headers={},
        request_body=None,
        outcome=outcome,
        perceived_state=perceived_state,
        request_timestamp=timestamp,
        response_timestamp=timestamp,
        logical_source="integration-test",
    )


def _record_no_help_trace(
    ccrs: ContingencyCcrs,
    context: InMemoryCcrsContext,
    *,
    strategy_id: str,
    escalation_level: int,
    evaluation_time_ms: int,
) -> None:
    jpype = ccrs.java_runtime.ensure_jvm(
        audit_event_namespace="react.ccrs.contingency.integration_test",
        log=LOGGER,
        log_prefix="[React CCRS][JPype test]",
    )
    ccrs_trace = ccrs.java_runtime.class_(
        jpype,
        "ccrs.core.contingency.dto.CcrsTrace",
    )
    strategy_result = ccrs.java_runtime.class_(
        jpype,
        "ccrs.core.contingency.dto.StrategyResult",
    )
    no_help_reason = ccrs.java_runtime.class_(
        jpype,
        "ccrs.core.contingency.dto.StrategyResult$NoHelpReason",
    )
    applicability = ccrs.java_runtime.class_(
        jpype,
        "ccrs.core.contingency.CcrsStrategy$Applicability",
    )
    java_situation = ccrs._classes["Situation"].builder().trigger("seed history").build()
    no_help = strategy_result.noHelp(
        strategy_id,
        no_help_reason.INSUFFICIENT_CONTEXT,
        "deterministic learned-selection fixture",
    )
    trace = (
        ccrs_trace.builder(java_situation)
        .addEvaluation(
            strategy_id,
            escalation_level,
            applicability.APPLICABLE,
            no_help,
            evaluation_time_ms,
        )
        .build()
    )
    context.ccrs_history.recordCcrsInvocation(trace)


def _evaluation(result: dict[str, object], strategy_id: str) -> dict[str, object]:
    return next(
        evaluation
        for evaluation in result["evaluations"]
        if evaluation["strategy_id"] == strategy_id
    )


if __name__ == "__main__":
    unittest.main()
