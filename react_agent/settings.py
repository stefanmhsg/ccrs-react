from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    run_mode: str = Field("sync")  # "sync" or "async"

    agent_name: str = Field("React")
    langchain_project: str = Field("react")

    llm_model: str = Field("gpt-5-mini")
    llm_temperature: float = Field(1.0) # gpt 5 only accepts 1.0

    recursion_limit: int = Field(10000)

    log_level: str = Field("INFO")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
