"""Python trace-history store matching Java `InMemoryCcrsTraceHistory`.

This module stores recent Java `CcrsTrace` objects for a `CcrsContext` so Java
contingency strategies can inspect recent CCRS invocations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class InMemoryCcrsTraceHistory:
    """Bounded in-memory store for Java `CcrsTrace` values."""

    max_size: int = 25
    traces: Iterable[Any] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        self._traces = list(self.traces)
        self.max_size = max(1, int(self.max_size))

    def getLastCcrsInvocation(self) -> Any | None:
        """Return the most recent Java `CcrsTrace`, if present."""

        if not self._traces:
            return None
        return self._traces[0]

    def getCcrsHistory(self, maxCount: int) -> list[Any]:
        """Return recent Java `CcrsTrace` values, newest first."""

        count = max(0, min(int(maxCount), len(self._traces)))
        return list(self._traces[:count])

    def recordCcrsInvocation(self, trace: Any) -> None:
        """Store a Java `CcrsTrace` and enforce the history size limit."""

        if trace is None:
            return
        self._traces.insert(0, trace)
        del self._traces[self.max_size :]
