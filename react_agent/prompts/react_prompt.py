from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

react_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an autonomous agent. Complete the user's request. Your name is {agent_name}. "
        "Use the available tools and explain your thinking through actions."
    ),
    (
    "system",
    "Course Check and Revision Strategy (CCRS) annotations derived from the most recent tool observations are provided below. "
    "They highlight potential opportunities, threats, or violated assumptions. "
    "Use them as advisory context when deciding what to do next.\n\n"
    "{ccrs}",
    ),
    MessagesPlaceholder(variable_name="messages"),
])
