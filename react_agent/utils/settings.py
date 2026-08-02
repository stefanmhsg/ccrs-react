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

    recursion_limit: int = Field(20000)

    stop_no_suggestion_invocation_threshold: int = Field(2)
    stop_low_confidence_invocation_threshold: int = Field(3)
    stop_low_confidence_threshold: float = Field(0.5)
    stop_selection_reset_count_before_stop: int = Field(1)
    stop_trace_history_lookback_limit: int = Field(30)
    stop_decision_accept_when: list[str] = Field(
        default_factory=lambda: [
            (
                "The latest maze observations and contingency guidance contain no "
                "concrete, valid, untried navigation or interaction that can still "
                "advance the task."
            ),
            (
                "Continuing would only repeat exhausted or already unsuccessful "
                "behavior without new environmental evidence."
            ),
        ]
    )
    stop_decision_continue_when: list[str] = Field(
        default_factory=lambda: [
            (
                "A concrete valid action remains that has not been exhausted, or new "
                "environmental evidence makes a previously attempted action worth "
                "reconsidering."
            ),
        ]
    )

    log_level: str = Field("INFO")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
