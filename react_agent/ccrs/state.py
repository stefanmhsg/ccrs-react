from operator import add
from typing import Annotated, Any, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class CcrsAgentState(TypedDict):
    """LangGraph state shape for ReAct agents equipped with CCRS."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    number_of_cycles: int
    # Opportunistic CCRS appends reusable course-check annotations here.
    ccrs: Annotated[list[dict[str, Any]], add]
