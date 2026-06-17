from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from react_agent.ccrs.prompt import DEFAULT_CCRS_SYSTEM_PROMPT


BASE_REACT_SYSTEM_PROMPT = (
    "You are an autonomous agent. Complete the user's request. Your name is {agent_name}. "
    "Use the available tools and explain your thinking through actions. "
    "Tracked current cell you are embodied in: {current_cell}. "
    "If the tracked current cell is unknown, follow the bootstrap instructions from the user request. "
    "After bootstrap, tool use is constrained by embodiment. "
    "To perceive the maze, only use http_get on the tracked current cell, with exactly this shape: "
    "{{\"url\": \"{current_cell}\"}}. "
    "Do not use http_get on adjacent cells before moving there. "
    "To navigate, choose a target cell that appeared as maze:north, maze:south, maze:east, maze:west, "
    "or maze:exit in the RDF of the tracked current cell, then call http_post with exactly this shape: "
    "{{\"url\": \"TARGET_CELL_URI\", \"data\": \"<http://127.0.1.1:8080/agents/{agent_name}> "
    "<https://paul.ti.rw.fau.de/~am52etar/dynmaze/dynmaze#entersFrom> <{current_cell}> .\", "
    "\"headers\": {{\"Content-Type\": \"text/turtle\"}}}}. "
    "Replace only TARGET_CELL_URI with the adjacent target cell URI. "
    "For non-navigation interactions, use http_post only on the tracked current cell with exactly this shape: "
    "{{\"url\": \"{current_cell}\", \"data\": \"VALID_TURTLE_BODY_FOR_THE_INTERACTION\", "
    "\"headers\": {{\"Content-Type\": \"text/turtle\"}}}}. "
    "Do not interact with adjacent cells before moving there."
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
