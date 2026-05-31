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
        if isinstance(self.type, Enum):
            return str(self.type.value).upper()
        raw = str(self.type)
        if raw.startswith("SituationType."):
            raw = raw.rsplit(".", 1)[-1]
        return raw.upper()

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "Situation":
        """Create a `Situation` from snake_case or Java-style field names."""

        if _is_embedded_escalation_tool_call(values):
            args = values.get("args")
            if isinstance(args, Mapping):
                return cls.from_mapping(args)

        type_value = (
            values.get("type")
            or values.get("situation_type")
            or values.get("situationType")
            or values.get("type_name")
            or values.get("typeName")
        )
        if type_value is None:
            keys = ", ".join(sorted(str(key) for key in values.keys()))
            raise ValueError(f"Contingency situation is missing a type field. Keys: {keys}")

        return cls(
            type=type_value,
            trigger=values.get("trigger"),
            current_resource=values.get("current_resource") or values.get("currentResource"),
            target_resource=values.get("target_resource") or values.get("targetResource"),
            failed_action=values.get("failed_action") or values.get("failedAction"),
            error_info=values.get("error_info") or values.get("errorInfo") or {},
            metadata=values.get("metadata") or {},
        )

    @classmethod
    def from_value(cls, value: "Situation | Mapping[str, Any] | Any") -> "Situation":
        """Normalize mapping or same-shaped situation objects.

        Notebook reloads can leave modules holding different `Situation` class
        objects. Accepting the structural shape keeps the adapter boundary
        robust without leaking that concern into graph routing.
        """

        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls.from_mapping(value)

        type_value = _attribute(value, "type_name", "typeName", "type", "getType")
        if type_value is None:
            raise TypeError(
                "Contingency situation must be a Situation, mapping, or same-shaped object"
            )

        return cls(
            type=type_value,
            trigger=_attribute(value, "trigger", "getTrigger"),
            current_resource=_attribute(
                value,
                "current_resource",
                "currentResource",
                "getCurrentResource",
            ),
            target_resource=_attribute(
                value,
                "target_resource",
                "targetResource",
                "getTargetResource",
            ),
            failed_action=_attribute(value, "failed_action", "failedAction", "getFailedAction"),
            error_info=_attribute(value, "error_info", "errorInfo", "getErrorInfo") or {},
            metadata=_attribute(value, "metadata", "getMetadata") or {},
        )


def _attribute(value: Any, *names: str) -> Any:
    for name in names:
        if hasattr(value, name):
            attr = getattr(value, name)
            return attr() if callable(attr) and name.startswith("get") else attr
    return None


def _is_embedded_escalation_tool_call(values: Mapping[str, Any]) -> bool:
    """Return whether a LangChain tool-call wrapper was supplied by mistake."""

    return (
        values.get("name") == "escalate_to_contingency_ccrs"
        and isinstance(values.get("args"), Mapping)
    )
