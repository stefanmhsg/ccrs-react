"""Non-live integration tests for the Python-to-Java contingency bridge.

These tests start a real JPype JVM and load the Maven-local ``ccrs-core``
artifact. Publish the Java module before running them:

    cd ../ccrs-bdi
    ./gradlew :ccrs-core:publishToMavenLocal
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from react_agent.ccrs.capabilities import CCRS_CORE_MODULE
from react_agent.ccrs.contingency import (
    ContingencyCcrs,
    InMemoryCcrsContext,
    Situation,
    SituationType,
)
from react_agent.ccrs.contingency.interaction import Interaction, InteractionOutcome
from react_agent.ccrs.rdf_adapter import RdfTripleValue


GROUP_PATH = Path("io/github/stefanmhsg/ccrs")
VERSION = "0.1.0-SNAPSHOT"
CURRENT = "https://example.test/cells/blocked"


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
            type=SituationType.FAILURE,
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
                type=SituationType.FAILURE,
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

    def test_immediate_stop_configuration_and_result_round_trip(self) -> None:
        ccrs = ContingencyCcrs.from_maven_local(
            contingency_configuration={
                "max_level": 0,
                "stop": {"require_exhaustion": False},
            },
        )

        result = ccrs.evaluate(
            {
                "type": "UNCERTAINTY",
                "trigger": "No safe action remains",
                "currentResource": CURRENT,
            }
        )

        stop = _evaluation(result, "stop")
        self.assertEqual("APPLICABLE", stop["applicability"])
        suggestion = stop["result"]
        self.assertEqual("suggestion", suggestion["result_type"])
        self.assertEqual("stop", suggestion["action_type"])
        self.assertIsNone(suggestion["action_target"])
        self.assertEqual("unrecoverable", suggestion["action_params"]["reason"])
        self.assertEqual("Trigger: No safe action remains", suggestion["action_params"]["finalError"])
        self.assertTrue(result["stop"])
        self.assertEqual(suggestion, result["top_suggestion"])


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


def _evaluation(result: dict[str, object], strategy_id: str) -> dict[str, object]:
    return next(
        evaluation
        for evaluation in result["evaluations"]
        if evaluation["strategy_id"] == strategy_id
    )


if __name__ == "__main__":
    unittest.main()
