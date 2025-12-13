from typing import Any
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from react_agent.state.state import AgentState
from react_agent.tools import tools
from react_agent.prompts.react_prompt import react_prompt


# Create model and bind tools
def llm_node(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    
    configuration = config.get("configurable", {})
    llm_model = configuration.get("llm_model", "gpt-5-mini")
    llm_temperature = configuration.get("llm_temperature", 1.0)
    agent_name = configuration.get("agent_name", "React")

    llm = ChatOpenAI(
        model=llm_model,
        temperature=llm_temperature,
    ) 

    # Bind tools to the model. Force at least one tool to be called.
    model = llm.bind_tools(tools, tool_choice="any")

    chain = react_prompt | model

    response = chain.invoke({
        "messages": state["messages"],
        "agent_name": agent_name,
    }, config)
    return {
        "messages": [response],
        "number_of_cycles": state.get("number_of_cycles", 0) + 1,
    }
