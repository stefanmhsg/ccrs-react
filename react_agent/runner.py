from langchain_core.messages import HumanMessage
from langsmith import traceable

async def run_query_async(graph, q: str, run_name: str, recursion_limit: int):
    @traceable(name=run_name)
    async def _inner():
        initial= {
            "messages": [HumanMessage(content=q)],
            "number_of_steps": 0,
        }
        async for step in graph.astream(
            initial,
            config={"recursion_limit": recursion_limit},
            stream_mode="values",
        ):
            last = step["messages"][-1]
            last.pretty_print()

    await _inner()


def run_query_sync(graph, q: str, run_name: str, recursion_limit: int):
    @traceable(name=run_name)
    def _inner():
        initial = {
            "messages": [HumanMessage(content=q)],
            "number_of_steps": 0,
        }
        for state in graph.stream(
            initial, 
            stream_mode="values", 
            config={"recursion_limit": recursion_limit}
        ):
            state["messages"][-1].pretty_print()
            print(f"Number of steps: {state.get('number_of_steps', 0)}")
            
    _inner()
