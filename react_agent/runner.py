from langchain_core.messages import HumanMessage
from langsmith import traceable

async def run_query_async(graph, q: str, run_name: str, config: dict):
    @traceable(name=run_name)
    async def _inner():
        initial= {
            "messages": [HumanMessage(content=q)],
            "number_of_cycles": 0,
        }
        async for step in graph.astream(
            initial,
            config=config,
            stream_mode="values",
        ):
            last = step["messages"][-1]
            last.pretty_print()
            print(f"Number of cycles: {step.get('number_of_cycles', 0)}")

    await _inner()


def run_query_sync(graph, q: str, run_name: str, config: dict):
    @traceable(name=run_name)
    def _inner():
        initial = {
            "messages": [HumanMessage(content=q)],
            "number_of_cycles": 0,
        }
        for state in graph.stream(
            initial, 
            stream_mode="values", 
            config=config
        ):
            state["messages"][-1].pretty_print()
            print(f"Number of cycles: {state.get('number_of_cycles', 0)}")
            
    _inner()
