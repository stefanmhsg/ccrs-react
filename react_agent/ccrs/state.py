from operator import add
from typing import Annotated, Any, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class CcrsAgentState(TypedDict):
    """LangGraph state shape for ReAct agents equipped with CCRS."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    cycle: dict[str, Any]
    # Opportunistic CCRS appends derived annotations; prompt injection filters by tool call.
    ccrs: Annotated[list[dict[str, Any]], add]
