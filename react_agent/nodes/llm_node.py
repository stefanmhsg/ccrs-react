from typing import Any
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from react_agent.settings import settings
from react_agent.state import AgentState
from react_agent.tools import tools
from react_agent.prompts.react_prompt import react_prompt


# Create model and bind tools
def llm_node(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    
    llm = ChatOpenAI(
    model=settings.llm_model,
    temperature=settings.llm_temperature,
    ) 

    # Bind tools to the model. Force at least one tool to be called.
    model = llm.bind_tools(tools, tool_choice="any")

    chain = react_prompt | model

    response = chain.invoke({
        "messages": state["messages"],
        "agent_name": settings.agent_name,
    }, config)
    return {
        "messages": [response],
        "number_of_cycles": state.get("number_of_cycles", 0) + 1,
    }
