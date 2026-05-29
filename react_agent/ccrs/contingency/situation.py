"""Python representation of Java contingency `Situation`.

This module carries the fields Java contingency strategies read when deciding
which recovery suggestions apply.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class SituationType(str, Enum):
    """Python names for Java `Situation.Type` values."""

    FAILURE = "FAILURE"
    STUCK = "STUCK"
    UNCERTAINTY = "UNCERTAINTY"
    PROACTIVE = "PROACTIVE"


@dataclass(frozen=True)
class Situation:
    """Input data used to build Java `ccrs.core.contingency.dto.Situation`."""

    type: SituationType | str
    trigger: str | None = None
    current_resource: str | None = None
    target_resource: str | None = None
    failed_action: str | None = None
    error_info: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def type_name(self) -> str:
        if isinstance(self.type, SituationType):
            return self.type.value
        return str(self.type).upper()

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "Situation":
        """Create a `Situation` from snake_case or Java-style field names."""

        return cls(
            type=values["type"],
            trigger=values.get("trigger"),
            current_resource=values.get("current_resource") or values.get("currentResource"),
            target_resource=values.get("target_resource") or values.get("targetResource"),
            failed_action=values.get("failed_action") or values.get("failedAction"),
            error_info=values.get("error_info") or values.get("errorInfo") or {},
            metadata=values.get("metadata") or {},
        )
