from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import datetime

agent_name = "React"

react_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        f"You are an autonomous agent in a hypermedia environment. Complete the user's request. Your name is {agent_name}. "
        "Use the available tools and explain your thinking through actions."
    ),
    MessagesPlaceholder(variable_name="messages"),
])
