"""Python wrapper for Java opportunistic `VocabularyMatcher`.

This module scans RDF observations with Java `VocabularyMatcher.scanAll(...)`
and converts Java `OpportunisticResult` values into dictionaries used by the
React/LangGraph adapter.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from react_agent.ccrs.audit import log_ccrs_event
from react_agent.ccrs.java_runtime import (
    CcrsJavaRuntime,
    CcrsJavaRuntimeError,
    get_default_java_runtime,
)
from react_agent.ccrs.rdf_adapter import RdfTripleValue, parse_turtle_triples


logger = logging.getLogger(__name__)
LOG_PREFIX = "[React CCRS][Opportunistic]"


@dataclass
class VocabularyMatcher:
    """Runs Java opportunistic CCRS vocabulary matching over RDF triples."""

    java_runtime: CcrsJavaRuntime = field(default_factory=get_default_java_runtime)

    _vocabulary_matcher: Any = field(default=None, init=False, repr=False)
    _classes: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def from_maven_local(
        cls,
        *,
        group: str = "io.github.stefanmhsg.ccrs",
        version: str = "0.1.0-SNAPSHOT",
        modules: Iterable[str] = ("ccrs-core",),
        maven_repo: str | Path | None = None,
        gradle_cache: str | Path | None = None,
        extra_classpath: Iterable[str | Path] = (),
    ) -> "VocabularyMatcher":
        return cls(
            java_runtime=CcrsJavaRuntime.from_maven_local(
                group=group,
                version=version,
                modules=modules,
                maven_repo=maven_repo,
                gradle_cache=gradle_cache,
                extra_classpath=extra_classpath,
            )
        )

    def evaluate_turtle(
        self,
        content: str,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Parse Turtle and scan its RDF triples for opportunistic CCRS results."""

        logger.info(
            "%s Parsing Turtle observation for opportunistic CCRS; content_length=%s",
            LOG_PREFIX,
            len(content),
        )
        triples = parse_turtle_triples(content)
        if not triples:
            logger.info("%s Parsed Turtle observation has no RDF triples.", LOG_PREFIX)
            return []
        return self.evaluate_triples(triples, context=context)

    def evaluate_triples(
        self,
        triples: Iterable[RdfTripleValue],
        *,
        context: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Scan RDF triples with Java `VocabularyMatcher.scanAll(...)`."""

        triple_values = list(triples)
        if not triple_values:
            logger.info("%s No RDF triples supplied for opportunistic CCRS.", LOG_PREFIX)
            return []

        jpype = self._ensure_matcher()

        java_triples = self.java_runtime.new_array_list(jpype)
        rdf_triple = self._classes["RdfTriple"]
        for triple in triple_values:
            java_triples.add(rdf_triple(triple.subject, triple.predicate, triple.object))

        java_context = self.java_runtime.new_hash_map(jpype, context or {})
        logger.info(
            "%s Calling Java VocabularyMatcher.scanAll with %s RDF triples; context=%s",
            LOG_PREFIX,
            len(triple_values),
            dict(context or {}),
        )
        results = self._vocabulary_matcher.scanAll(java_triples, java_context)
        logger.info(
            "%s Java VocabularyMatcher.scanAll returned %s opportunistic CCRS results.",
            LOG_PREFIX,
            results.size(),
        )
        return [self._opportunistic_result_to_dict(result, context or {}) for result in results]

    def _ensure_matcher(self) -> Any:
        """Load Java vocabulary classes and create the Java matcher instance."""

        jpype = self.java_runtime.ensure_jvm(
            audit_event_namespace="react.ccrs.opportunistic",
            log=logger,
            log_prefix=LOG_PREFIX,
        )
        self._load_classes(jpype)
        if self._vocabulary_matcher is None:
            vocabulary = self._classes["CcrsVocabularyLoader"].loadDefault()
            self._vocabulary_matcher = self._classes["VocabularyMatcher"](vocabulary)
            log_ccrs_event(
                logger,
                "react.ccrs.opportunistic.runtime.ready",
                {"scanner": "ccrs.core.opportunistic.VocabularyMatcher"},
            )
        return jpype

    def _load_classes(self, jpype: Any) -> None:
        if self._classes:
            return
        try:
            self._classes = {
                "RdfTriple": self.java_runtime.class_(jpype, "ccrs.core.rdf.RdfTriple"),
                "CcrsVocabularyLoader": self.java_runtime.class_(jpype, "ccrs.core.rdf.CcrsVocabularyLoader"),
                "VocabularyMatcher": self.java_runtime.class_(jpype, "ccrs.core.opportunistic.VocabularyMatcher"),
            }
            logger.info("%s Loaded Java opportunistic CCRS classes through JPype.", LOG_PREFIX)
        except Exception as exc:
            raise CcrsJavaRuntimeError(
                "Failed to load Java opportunistic CCRS classes. Check that ccrs-core "
                "and its dependencies are on the JPype classpath."
            ) from exc

    def _opportunistic_result_to_dict(self, result: Any, context: Mapping[str, Any]) -> dict[str, Any]:
        metadata = {
            str(entry.getKey()): str(entry.getValue())
            for entry in result.getMetadataMap().entrySet()
        }
        tool_call_id = context.get("tool_call_id") or metadata.get("tool_call_id")
        entry: dict[str, Any] = {
            "ccrs_type": "opportunistic",
            "type": str(result.type),
            "target": str(result.target),
            "pattern_id": str(result.patternId),
            "utility": float(result.utility),
            "metadata": metadata,
        }
        if tool_call_id is not None:
            entry["tool_call_id"] = str(tool_call_id)
        return entry


def get_default_vocabulary_matcher() -> VocabularyMatcher:
    """Return the process-local Java `VocabularyMatcher` wrapper."""

    global _default_vocabulary_matcher
    if _default_vocabulary_matcher is None:
        _default_vocabulary_matcher = VocabularyMatcher.from_maven_local()
    return _default_vocabulary_matcher


_default_vocabulary_matcher: VocabularyMatcher | None = None
