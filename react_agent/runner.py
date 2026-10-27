from langchain_core.messages import HumanMessage
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from datetime import datetime, timezone
import json
import logging


def _log_trace_identity(run_name: str) -> None:
    """Record this invocation's span, which anchors its full experiment subtree."""
    current = get_current_run_tree()
    record = {"event": "react.langsmith.root", "run_name": run_name,
              "status": "available" if current is not None else "unavailable",
              "root_run_id": str(current.id) if current is not None else None,
              "trace_id": str(current.trace_id) if current is not None else None}
    logging.getLogger(__name__).info("[REACT-LANGSMITH] %s", json.dumps(record, sort_keys=True))


def _initial_cycle() -> dict:
    return {
        "number": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    }

async def run_query_async(graph, q: str, run_name: str, config: dict):
    @traceable(name=run_name)
    async def _inner():
        _log_trace_identity(run_name)
        initial= {
            "messages": [HumanMessage(content=q)],
            "cycle": _initial_cycle(),
            "current_cell": None,
            "advertised_navigation_options": None,
        }
        printed_message_count = 0
        async for step in graph.astream(
            initial,
            config=config,
            stream_mode="values",
        ):
            messages = step.get("messages", [])
            for message in messages[printed_message_count:]:
                message.pretty_print()
                print(f"Cycle: {step.get('cycle', {})}")
            printed_message_count = len(messages)

    await _inner()


def run_query_sync(graph, q: str, run_name: str, config: dict):
    @traceable(name=run_name)
    def _inner():
        _log_trace_identity(run_name)
        initial = {
            "messages": [HumanMessage(content=q)],
            "cycle": _initial_cycle(),
            "current_cell": None,
            "advertised_navigation_options": None,
        }
        printed_message_count = 0
        for state in graph.stream(
            initial, 
            stream_mode="values", 
            config=config
        ):
            messages = state.get("messages", [])
            for message in messages[printed_message_count:]:
                message.pretty_print()
                print(f"Cycle: {state.get('cycle', {})}")
            printed_message_count = len(messages)
            
    _inner()
