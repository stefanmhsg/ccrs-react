from langchain_core.messages import HumanMessage
from langsmith import traceable
from datetime import datetime, timezone


def _initial_cycle() -> dict:
    return {
        "number": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    }

async def run_query_async(graph, q: str, run_name: str, config: dict):
    @traceable(name=run_name)
    async def _inner():
        initial= {
            "messages": [HumanMessage(content=q)],
            "cycle": _initial_cycle(),
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
        initial = {
            "messages": [HumanMessage(content=q)],
            "cycle": _initial_cycle(),
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
