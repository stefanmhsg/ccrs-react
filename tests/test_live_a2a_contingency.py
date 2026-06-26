"""Live A2A contingency CCRS smoke tests.

These tests are intentionally skipped unless the local key-holder A2A agent is
running. They exercise the full Java contingency strategy path from React's
Python wrapper into the Java A2A consultation strategy.
"""

from __future__ import annotations

import socket
import unittest
from urllib.error import URLError
from urllib.request import urlopen

from react_agent.ccrs.capabilities import CCRS_A2A_MODULE, CCRS_CORE_MODULE
from react_agent.ccrs.contingency import ContingencyCcrs, InMemoryCcrsContext, Situation, SituationType
from react_agent.ccrs.contingency.interaction import Interaction, InteractionOutcome
from react_agent.ccrs.rdf_adapter import RdfTripleValue


KEY_HOLDER_AGENT_URI = "http://127.0.1.1:8080/agents/key-holder-agent-1"
KEY_HOLDER_AGENT_CARD_URI = "http://127.0.0.1:8095/.well-known/agent-card.json"
REACT_AGENT_ID = "react_ccrs_mazeV2"
REACT_AGENT_URI = f"http://127.0.1.1:8080/agents/{REACT_AGENT_ID}"
LOCK_URI = "http://127.0.1.1:8080/cells/44/45"

MAZE_CONTAINS = "https://kaefer3000.github.io/2021-02-dagstuhl/vocab#contains"
A2A_AGENT_CARD = "https://example.org/a2a#agentCard"


def _key_holder_agent_is_running() -> bool:
    try:
        with urlopen(KEY_HOLDER_AGENT_CARD_URI, timeout=2) as response:
            return response.status == 200
    except (OSError, URLError, TimeoutError, socket.timeout):
        return False


@unittest.skipUnless(
    _key_holder_agent_is_running(),
    "local key-holder A2A agent is not running at "
    f"{KEY_HOLDER_AGENT_CARD_URI}",
)
class LiveA2aContingencyTest(unittest.TestCase):
    def test_contingency_ccrs_consults_live_key_holder_agent(self) -> None:
        triples = [
            RdfTripleValue(LOCK_URI, MAZE_CONTAINS, REACT_AGENT_URI),
            RdfTripleValue(LOCK_URI, MAZE_CONTAINS, KEY_HOLDER_AGENT_URI),
            RdfTripleValue(KEY_HOLDER_AGENT_URI, A2A_AGENT_CARD, KEY_HOLDER_AGENT_CARD_URI),
        ]
        interaction = Interaction(
            method="GET",
            request_uri=LOCK_URI,
            request_headers={},
            request_body=None,
            outcome=InteractionOutcome.SUCCESS,
            perceived_state=triples,
            request_timestamp=1,
            response_timestamp=2,
            logical_source=LOCK_URI,
        )
        context = InMemoryCcrsContext(
            agent_id=REACT_AGENT_ID,
            triples=triples,
            interactions=[interaction],
            current_resource=LOCK_URI,
        )
        ccrs = ContingencyCcrs.from_maven_local(
            modules=(CCRS_CORE_MODULE, CCRS_A2A_MODULE),
            discover_strategy_providers=True,
        )
        situation = Situation(
            type=SituationType.UNCERTAINTY,
            trigger="live_keyholder_a2a_smoke",
            current_resource=LOCK_URI,
            target_resource=LOCK_URI,
            failed_action="decide_next",
            error_info={"reason": "Need a blue key for the current lock."},
            metadata={"agent_name": REACT_AGENT_ID},
        )

        result = ccrs.evaluate(situation, context)

        consultation_evaluation = next(
            item for item in result["evaluations"] if item["strategy_id"] == "consultation"
        )
        self.assertEqual("APPLICABLE", consultation_evaluation["applicability"])
        self.assertEqual("suggestion", consultation_evaluation["result"]["result_type"])

        suggestion = consultation_evaluation["result"]
        self.assertEqual("post", suggestion["action_type"])
        self.assertEqual(LOCK_URI, suggestion["action_target"])
        self.assertGreaterEqual(suggestion["confidence"], 0.9)
        self.assertIn("bluekey-", suggestion["action_params"]["body"])
        self.assertIn("provide_blue_key", suggestion["action_params"]["consultationSource"])


if __name__ == "__main__":
    unittest.main()
