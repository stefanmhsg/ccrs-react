from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import datetime

agent_name = "React"

react_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        f"You are a helpful assistant. Your name is {agent_name}. "
        "Use the available tools when needed and explain your thinking through actions."
    ),
    MessagesPlaceholder(variable_name="messages"),
])
