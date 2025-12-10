from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

react_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an autonomous agent. Complete the user's request. Your name is {agent_name}. "
        "Use the available tools and explain your thinking through actions."
    ),
    MessagesPlaceholder(variable_name="messages"),
])
