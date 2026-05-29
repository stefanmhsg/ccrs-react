"""Python implementation of Java `CcrsContext` for contingency evaluation.

This module supplies RDF lookup, current-resource access, capability flags,
and CCRS trace history to Java contingency strategies through a JPype proxy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from langchain_core.messages import BaseMessage

from react_agent.ccrs.contingency.in_memory_ccrs_trace_history import (
    InMemoryCcrsTraceHistory,
)
from react_agent.ccrs.contingency.interaction import (
    Interaction,
    OutcomeClassifier,
    parse_tool_messages,
)
from react_agent.ccrs.rdf_adapter import RdfTripleValue


@dataclass
class InMemoryCcrsContext:
    """In-memory `CcrsContext` implementation exposed to Java via JPype."""

    agent_id: str = "React"
    triples: Iterable[RdfTripleValue] = field(default_factory=tuple)
    interactions: Iterable[Interaction] = field(default_factory=tuple)
    current_resource: str | None = None
    ccrs_history: InMemoryCcrsTraceHistory = field(default_factory=InMemoryCcrsTraceHistory)

    def __post_init__(self) -> None:
        self._triples = list(self.triples)
        self._interactions = list(self.interactions)
        self._jpype: Any | None = None
        self._classes: dict[str, Any] = {}

    @classmethod
    def from_messages(
        cls,
        messages: Sequence[BaseMessage],
        *,
        agent_id: str = "React",
        current_resource: str | None = None,
        ccrs_history: InMemoryCcrsTraceHistory | None = None,
        outcome_classifier: OutcomeClassifier | None = None,
    ) -> "InMemoryCcrsContext":
        """Build a `CcrsContext` from normal LangGraph/ReAct messages."""

        parsed_messages = parse_tool_messages(
            messages,
            outcome_classifier=outcome_classifier,
        )
        triples: list[RdfTripleValue] = []
        interactions: list[Interaction] = []
        for parsed in parsed_messages:
            triples.extend(parsed.triples)
            interactions.append(parsed.interaction)

        return cls(
            agent_id=agent_id,
            triples=triples,
            interactions=interactions,
            current_resource=current_resource,
            ccrs_history=ccrs_history or InMemoryCcrsTraceHistory(),
        )

    def as_java_proxy(
        self,
        jpype: Any,
        ccrs_context_class: Any,
        classes: dict[str, Any],
    ) -> Any:
        """Create a JPype proxy implementing Java `CcrsContext`."""

        self._jpype = jpype
        self._classes = classes
        return jpype.JProxy(ccrs_context_class, inst=self)

    def query(self, subject: str | None, predicate: str | None, object: str | None) -> Any:
        """Return Java `RdfTriple` values matching an RDF triple pattern."""

        results = self._new_array_list()
        for triple in self._triples:
            if (
                _matches(subject, triple.subject)
                and _matches(predicate, triple.predicate)
                and _matches(object, triple.object)
            ):
                results.add(self._new_rdf_triple(triple))
        return results

    def contains(self, triple: Any) -> bool:
        """Return whether the supplied Java `RdfTriple` is in this context."""

        subject = str(triple.subject)
        predicate = str(triple.predicate)
        obj = str(triple.object)
        return any(
            known.subject == subject
            and known.predicate == predicate
            and known.object == obj
            for known in self._triples
        )

    def getMemoryTriples(self, maxCount: int) -> Any:
        results = self._new_array_list()
        if maxCount <= 0:
            return results
        for triple in self._triples[: int(maxCount)]:
            results.add(self._new_rdf_triple(triple))
        return results

    def getNeighborhood(self, resource: str | None, *limits: int) -> Any:
        max_outgoing = int(limits[0]) if limits else 30
        max_incoming = int(limits[1]) if len(limits) > 1 else 20
        outgoing = self.query(resource, None, None)
        incoming = self.query(None, None, resource)
        return self._classes["Neighborhood"](
            resource,
            _bounded_java_list(outgoing, max_outgoing, self._classes["ArrayList"]),
            _bounded_java_list(incoming, max_incoming, self._classes["ArrayList"]),
        )

    def getRecentInteractions(self, maxCount: int) -> Any:
        results = self._new_array_list()
        if maxCount <= 0:
            return results
        for interaction in list(reversed(self._interactions))[: int(maxCount)]:
            results.add(self._new_interaction(interaction))
        return results

    def getLastInteraction(self) -> Any:
        if not self._interactions:
            return self._optional_empty()
        return self._classes["Optional"].of(self._new_interaction(self._interactions[-1]))

    def getInteractionsFor(self, logicalSource: str) -> Any:
        results = self._new_array_list()
        for interaction in reversed(self._interactions):
            if interaction.logical_source == logicalSource:
                results.add(self._new_interaction(interaction))
        return results

    def getLastCcrsInvocation(self) -> Any:
        trace = self.ccrs_history.getLastCcrsInvocation()
        if trace is None:
            return self._optional_empty()
        return self._classes["Optional"].of(trace)

    def getCcrsHistory(self, maxCount: int) -> Any:
        results = self._new_array_list()
        for trace in self.ccrs_history.getCcrsHistory(maxCount):
            results.add(trace)
        return results

    def recordCcrsInvocation(self, trace: Any) -> None:
        self.ccrs_history.recordCcrsInvocation(trace)

    def getCurrentResource(self) -> Any:
        if self.current_resource:
            return self._classes["Optional"].of(str(self.current_resource))
        return self._optional_empty()

    def getAgentId(self) -> str:
        return str(self.agent_id)

    def hasHistory(self) -> bool:
        return bool(self._interactions)

    def hasLlmAccess(self) -> bool:
        return False

    def hasConsultationChannel(self) -> bool:
        return False

    def _new_array_list(self) -> Any:
        return self._classes["ArrayList"]()

    def _new_rdf_triple(self, triple: RdfTripleValue) -> Any:
        return self._classes["RdfTriple"](triple.subject, triple.predicate, triple.object)

    def _new_interaction(self, interaction: Interaction) -> Any:
        perceived_state = self._new_array_list()
        for triple in interaction.perceived_state:
            perceived_state.add(self._new_rdf_triple(triple))
        return self._classes["Interaction"](
            interaction.method,
            interaction.request_uri,
            _java_string_map(self._classes["HashMap"], interaction.request_headers),
            interaction.request_body,
            self._classes["InteractionOutcome"].valueOf(interaction.outcome),
            perceived_state,
            int(interaction.request_timestamp),
            int(interaction.response_timestamp),
            interaction.logical_source,
        )

    def _optional_empty(self) -> Any:
        return self._classes["Optional"].empty()


def _matches(pattern: str | None, value: str) -> bool:
    return pattern is None or str(pattern) == value


def _bounded_java_list(values: Any, max_count: int, array_list_class: Any) -> Any:
    bounded = array_list_class()
    if max_count <= 0:
        return bounded
    for value in list(values)[:max_count]:
        bounded.add(value)
    return bounded


def _java_string_map(hash_map_class: Any, values: Mapping[str, str]) -> Any:
    java_map = hash_map_class()
    for key, value in values.items():
        java_map.put(str(key), str(value))
    return java_map
