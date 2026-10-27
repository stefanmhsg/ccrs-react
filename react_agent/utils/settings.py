from dataclasses import dataclass

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


@dataclass(frozen=True)
class LlmModelProfile:
    """The OpenAI parameters supported by a named model configuration."""

    model: str
    temperature: float
    reasoning_effort: str
    seed: int | None = None


LLM_MODEL_PROFILES: dict[str, LlmModelProfile] = {
    # Keep older profiles available for explicit selection.
    "gpt_5_mini": LlmModelProfile(
        model="gpt-5-mini-2025-08-07",
        temperature=1.0, # gpt 5 only accepts 1.0
        reasoning_effort="minimal",
    ),
    "gpt_5_6_luna": LlmModelProfile(
        model="gpt-5.6-luna",
        temperature=0.0,
        # `minimal` is not supported by Luna; `none` is its lowest effort.
        reasoning_effort="none",
        seed=42,
    ),
    "gpt_6_luna": LlmModelProfile(
        model="gpt-6-luna",
        temperature=0.0,
        reasoning_effort="none",
        seed=42,
    ),
}


class Settings(BaseSettings):
    run_mode: str = Field("sync")  # "sync" or "async"

    agent_name: str = Field("React")
    langchain_project: str = Field("react")

    # Select a profile here or with LLM_MODEL_PROFILE in .env.
    # Available profiles: gpt_5_mini, gpt_5_6_luna, gpt_6_luna.
    llm_model_profile: str = Field("gpt_6_luna")
    llm_message_window_max_messages: int | None = Field(None) # None disables trimming; e.g. 60 keeps the last N non-preserved messages.
    llm_message_window_max_tokens: int | None = Field(None) # None disables trimming; e.g. 350000 limits non-preserved history to approximately N tokens.

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

    @field_validator("llm_model_profile")
    @classmethod
    def validate_llm_model_profile(cls, value: str) -> str:
        if value not in LLM_MODEL_PROFILES:
            available_profiles = ", ".join(LLM_MODEL_PROFILES)
            raise ValueError(
                f"Unknown LLM model profile {value!r}. "
                f"Available profiles: {available_profiles}."
            )
        return value

    @property
    def llm_profile(self) -> LlmModelProfile:
        return LLM_MODEL_PROFILES[self.llm_model_profile]

    @property
    def llm_model(self) -> str:
        return self.llm_profile.model

    @property
    def llm_temperature(self) -> float:
        return self.llm_profile.temperature

    @property
    def llm_reasoning_effort(self) -> str:
        return self.llm_profile.reasoning_effort

    @property
    def llm_seed(self) -> int | None:
        return self.llm_profile.seed


settings = Settings()
