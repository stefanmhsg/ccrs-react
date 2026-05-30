from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from react_agent.ccrs.prompt import DEFAULT_CCRS_SYSTEM_PROMPT


BASE_REACT_SYSTEM_PROMPT = (
    "You are an autonomous agent. Complete the user's request. Your name is {agent_name}. "
    "Use the available tools and explain your thinking through actions."
)


def make_react_prompt(
    *,
    system_prompt: str = BASE_REACT_SYSTEM_PROMPT,
) -> ChatPromptTemplate:
    """Create the baseline React prompt."""

    return ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )


def make_react_prompt_ccrs(
    *,
    system_prompt: str = BASE_REACT_SYSTEM_PROMPT,
    ccrs_system_prompt: str = DEFAULT_CCRS_SYSTEM_PROMPT,
) -> ChatPromptTemplate:
    """Create a React prompt with an overridable CCRS system fragment."""

    return ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("system", ccrs_system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )


react_prompt = make_react_prompt()
react_prompt_ccrs = make_react_prompt_ccrs()
