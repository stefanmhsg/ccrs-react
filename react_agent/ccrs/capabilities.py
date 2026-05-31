"""Semantic CCRS capability metadata for Java-backed adapter wiring."""

from __future__ import annotations

from enum import Enum
from typing import Iterable


CCRS_CORE_MODULE = "ccrs-core"
CCRS_LANGCHAIN4J_MODULE = "ccrs-langchain4j"
CCRS_A2A_MODULE = "ccrs-a2a"

DEFAULT_CONTINGENCY_CCRS_MODULES = (CCRS_CORE_MODULE,)


class ContingencyCapability(str, Enum):
    """Optional Java contingency capabilities exposed through adapter settings."""

    LLM_PREDICTION = "llm_prediction"
    A2A_CONSULTATION = "a2a_consultation"


CONTINGENCY_CAPABILITY_MODULES: dict[ContingencyCapability, tuple[str, ...]] = {
    ContingencyCapability.LLM_PREDICTION: (CCRS_LANGCHAIN4J_MODULE,),
    ContingencyCapability.A2A_CONSULTATION: (CCRS_A2A_MODULE,),
}


def normalize_ccrs_modules(modules: str | Iterable[str] | None) -> tuple[str, ...]:
    """Normalize explicit Java CCRS module overrides and ensure core is present."""

    if modules is None:
        return DEFAULT_CONTINGENCY_CCRS_MODULES
    if isinstance(modules, str):
        values = modules.replace(",", " ").split()
    else:
        values = [str(value) for value in modules]

    normalized = tuple(value for value in values if value)
    if not normalized:
        return DEFAULT_CONTINGENCY_CCRS_MODULES
    if CCRS_CORE_MODULE not in normalized:
        return (CCRS_CORE_MODULE, *normalized)
    return normalized


def contingency_modules_for_capabilities(
    capabilities: Iterable[ContingencyCapability | str],
    *,
    base_modules: str | Iterable[str] | None = None,
) -> tuple[str, ...]:
    """Return Java modules required by semantic contingency capabilities."""

    modules = normalize_ccrs_modules(base_modules)
    for capability in capabilities:
        capability_key = _normalize_contingency_capability(capability)
        for module in CONTINGENCY_CAPABILITY_MODULES[capability_key]:
            modules = _append_unique(modules, module)
    return modules


def _normalize_contingency_capability(
    capability: ContingencyCapability | str,
) -> ContingencyCapability:
    if isinstance(capability, ContingencyCapability):
        return capability
    try:
        return ContingencyCapability(str(capability))
    except ValueError as exc:
        known = ", ".join(item.value for item in ContingencyCapability)
        raise ValueError(f"Unknown contingency CCRS capability {capability!r}; expected one of: {known}") from exc


def _append_unique(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    if value in values:
        return values
    return (*values, value)
