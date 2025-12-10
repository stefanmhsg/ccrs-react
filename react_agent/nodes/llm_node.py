from typing import Any
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from react_agent.state import AgentState
from react_agent.tools import tools
from react_agent.prompts.react_prompt import react_prompt


# Create model and bind tools

# Create LLM class
llm = ChatOpenAI(
    model="gpt-5-mini",
    temperature=1.0, # gpt 5 only accepts 1.0
)

# Bind tools to the model. Force at least one tool to be called.
model = llm.bind_tools(tools, tool_choice="any")

chain = react_prompt | model


def llm_node(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    response = chain.invoke(state["messages"], config)
    return {
        "messages": [response],
        "number_of_steps": state.get("number_of_steps", 0) + 1,
    }
