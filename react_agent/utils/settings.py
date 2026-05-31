from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    run_mode: str = Field("sync")  # "sync" or "async"

    agent_name: str = Field("React")
    langchain_project: str = Field("react")

    llm_model: str = Field("gpt-5-mini-2025-08-07") # gpt-5-nano-2025-08-07 or gpt-5-mini-2025-08-07
    llm_temperature: float = Field(1.0) # gpt 5 only accepts 1.0
    llm_reasoning_effort: str = Field("minimal") # gpt-5-nano does not support "none"; "minimal" is the lowest effort
    llm_message_window_max_messages: int | None = Field(60) # Trim message history to the last N messages. 
    llm_message_window_max_tokens: int | None = Field(350000) # Trim message history to fit within N tokens. Models both have 400k token limits

    recursion_limit: int = Field(10000)

    log_level: str = Field("INFO")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
