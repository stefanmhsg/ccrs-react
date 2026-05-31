"""Message-window helpers for LLM prompt inputs."""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, trim_messages
from langchain_core.messages.utils import count_tokens_approximately


def sliding_message_window(
    messages: Sequence[BaseMessage],
    *,
    max_messages: int | None = None,
    max_tokens: int | None = None,
) -> list[BaseMessage]:
    """Trim message history while preserving system prompts and the first user query."""

    preserved, history = _split_preserved_messages(messages)
    trimmed_history = list(history)

    if max_messages is not None and max_messages >= 0:
        trimmed_history = trim_messages(
            trimmed_history,
            max_tokens=max_messages,
            token_counter=len,
            strategy="last",
        )

    if max_tokens is not None and max_tokens > 0:
        trimmed_history = trim_messages(
            trimmed_history,
            max_tokens=max_tokens,
            token_counter=count_tokens_approximately,
            strategy="last",
        )

    return [*preserved, *trimmed_history]


def _split_preserved_messages(
    messages: Sequence[BaseMessage],
) -> tuple[list[BaseMessage], list[BaseMessage]]:
    preserved: list[BaseMessage] = []
    history: list[BaseMessage] = []
    first_human_preserved = False

    for message in messages:
        if isinstance(message, SystemMessage):
            preserved.append(message)
            continue
        if isinstance(message, HumanMessage) and not first_human_preserved:
            preserved.append(message)
            first_human_preserved = True
            continue
        history.append(message)

    return preserved, history
