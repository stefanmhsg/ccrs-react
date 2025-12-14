from typing import Annotated,Sequence, TypedDict
from operator import add

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages # helper function to add messages to the state


class AgentState(TypedDict):
    """The state of the agent."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    number_of_cycles: int
    ccrs: Annotated[list[dict], add] # CCRS data generated from the CCRS Observation Node. Reducer is `add` to only append new CCRS data.
