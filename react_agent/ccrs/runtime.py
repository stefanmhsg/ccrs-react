from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Iterable, Mapping

from react_agent.ccrs.rdf_adapter import RdfTripleValue, parse_turtle_triples


logger = logging.getLogger(__name__)
LOG_PREFIX = "[Opportunistic CCRS]"


class CcrsRuntimeError(RuntimeError):
    """Raised when the Java CCRS runtime cannot be loaded or called."""


def _default_maven_repo() -> Path:
    return Path(os.environ.get("M2_REPO", Path.home() / ".m2" / "repository"))


def _default_gradle_cache() -> Path:
    return Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1"


@dataclass
class CcrsRuntime:
    """JPype-backed runtime for calling Java CCRS core from Python."""

    group: str = "io.github.stefanmhsg.ccrs"
    version: str = "0.1.0-SNAPSHOT"
    modules: tuple[str, ...] = ("ccrs-core",)
    maven_repo: Path = field(default_factory=_default_maven_repo)
    gradle_cache: Path = field(default_factory=_default_gradle_cache)
    extra_classpath: tuple[Path, ...] = ()

    _opportunistic_ccrs: Any = field(default=None, init=False, repr=False)
    _classes: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    _jvm_lock: ClassVar[threading.Lock] = threading.Lock()

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
    ) -> "CcrsRuntime":
        return cls(
            group=group,
            version=version,
            modules=tuple(modules),
            maven_repo=Path(maven_repo) if maven_repo is not None else _default_maven_repo(),
            gradle_cache=Path(gradle_cache) if gradle_cache is not None else _default_gradle_cache(),
            extra_classpath=tuple(Path(path) for path in extra_classpath),
        )

    def evaluate_turtle(
        self,
        content: str,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
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

    def scan_turtle(
        self,
        content: str,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Deprecated compatibility alias for opportunistic CCRS evaluation."""

        return self.evaluate_turtle(content, context=context)

    def evaluate_triples(
        self,
        triples: Iterable[RdfTripleValue],
        *,
        context: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        triple_values = list(triples)
        if not triple_values:
            logger.info("%s No RDF triples supplied for opportunistic CCRS.", LOG_PREFIX)
            return []

        self._ensure_runtime()

        java_triples = self._new_java_array_list()
        for triple in triple_values:
            java_triples.add(
                self._classes["RdfTriple"](triple.subject, triple.predicate, triple.object)
            )

        java_context = self._new_java_hash_map(context or {})
        logger.info(
            "%s Calling Java VocabularyMatcher.scanAll with %s RDF triples; context=%s",
            LOG_PREFIX,
            len(triple_values),
            dict(context or {}),
        )
        results = self._opportunistic_ccrs.scanAll(java_triples, java_context)
        logger.info(
            "%s Java VocabularyMatcher.scanAll returned %s opportunistic CCRS results.",
            LOG_PREFIX,
            results.size(),
        )
        return [
            self._opportunistic_result_to_dict(result, context or {})
            for result in results
        ]

    def scan_triples(
        self,
        triples: Iterable[RdfTripleValue],
        *,
        context: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Deprecated compatibility alias for opportunistic CCRS evaluation."""

        return self.evaluate_triples(triples, context=context)

    def resolve_classpath(self) -> list[Path]:
        paths: list[Path] = []

        env_classpath = os.environ.get("CCRS_JAVA_CLASSPATH")
        if env_classpath:
            paths.extend(Path(path) for path in env_classpath.split(os.pathsep) if path)
            logger.info(
                "%s Added CCRS_JAVA_CLASSPATH entries for JPype classpath.",
                LOG_PREFIX,
            )

        paths.extend(self.extra_classpath)
        paths.extend(self._resolve_module_jars())
        paths.extend(self._resolve_dependency_jars())

        seen: set[str] = set()
        unique: list[Path] = []
        for path in paths:
            resolved = path.resolve()
            key = str(resolved).lower()
            if resolved.exists() and key not in seen:
                unique.append(resolved)
                seen.add(key)

        if not unique:
            raise CcrsRuntimeError("No Java classpath entries found for CCRS.")

        logger.info(
            "%s Resolved %s Java classpath entries for JPype.",
            LOG_PREFIX,
            len(unique),
        )
        return unique

    def _ensure_runtime(self) -> None:
        jpype = self._require_jpype()

        with self._jvm_lock:
            classpath = [str(path) for path in self.resolve_classpath()]
            if jpype.isJVMStarted():
                logger.info(
                    "%s JPype JVM already started; adding CCRS classpath entries.",
                    LOG_PREFIX,
                )
                for path in classpath:
                    jpype.addClassPath(path)
            else:
                logger.info(
                    "%s Starting JPype JVM for opportunistic CCRS; classpath_entries=%s",
                    LOG_PREFIX,
                    len(classpath),
                )
                jpype.startJVM(classpath=classpath, convertStrings=True)

            self._load_classes(jpype)
            self._configure_java_logging(jpype)
            if self._opportunistic_ccrs is None:
                logger.info(
                    "%s Loading default CCRS vocabulary and creating Java "
                    "VocabularyMatcher.",
                    LOG_PREFIX,
                )
                vocabulary = self._classes["CcrsVocabularyLoader"].loadDefault()
                self._opportunistic_ccrs = self._classes["VocabularyMatcher"](vocabulary)

    def _load_classes(self, jpype: Any) -> None:
        if self._classes:
            return

        try:
            self._classes = {
                "ArrayList": jpype.JClass("java.util.ArrayList"),
                "HashMap": jpype.JClass("java.util.HashMap"),
                "RdfTriple": jpype.JClass("ccrs.core.rdf.RdfTriple"),
                "CcrsVocabularyLoader": jpype.JClass("ccrs.core.rdf.CcrsVocabularyLoader"),
                "VocabularyMatcher": jpype.JClass("ccrs.core.opportunistic.VocabularyMatcher"),
            }
            logger.info("%s Loaded Java CCRS classes through JPype.", LOG_PREFIX)
        except Exception as exc:
            raise CcrsRuntimeError(
                "Failed to load Java CCRS classes. Check that ccrs-core and its "
                "dependencies are on the JPype classpath."
            ) from exc

    def _configure_java_logging(self, jpype: Any) -> None:
        # Java CCRS uses java.util.logging; keep its loggers verbose for traces.
        try:
            java_logger = jpype.JClass("java.util.logging.Logger")
            java_level = jpype.JClass("java.util.logging.Level")
            ccrs_logger = java_logger.getLogger("ccrs")
            ccrs_logger.setLevel(java_level.FINE)
            root_logger = java_logger.getLogger("")
            for handler in root_logger.getHandlers():
                handler.setLevel(java_level.FINE)
            logger.info(
                "%s Configured Java CCRS library logging level through JPype.",
                LOG_PREFIX,
            )
        except Exception:
            logger.exception(
                "%s Failed to configure Java CCRS library logging level.",
                LOG_PREFIX,
            )

    def _resolve_module_jars(self) -> list[Path]:
        return [
            self._find_maven_artifact_jar(module)
            for module in self.modules
        ]

    def _find_maven_artifact_jar(self, artifact_id: str) -> Path:
        artifact_dir = self.maven_repo.joinpath(
            *self.group.split("."),
            artifact_id,
            self.version,
        )
        if not artifact_dir.exists():
            raise CcrsRuntimeError(
                f"Missing Maven-local CCRS artifact directory: {artifact_dir}"
            )

        candidates = sorted(
            path
            for path in artifact_dir.glob(f"{artifact_id}-{self.version}*.jar")
            if not _is_non_runtime_jar(path)
        )
        if not candidates:
            raise CcrsRuntimeError(
                f"Missing Maven-local CCRS runtime jar for {artifact_id}:{self.version}"
            )
        logger.info(
            "%s Resolved Maven-local CCRS module jar; module=%s path=%s",
            LOG_PREFIX,
            artifact_id,
            candidates[0],
        )
        return candidates[0]

    def _resolve_dependency_jars(self) -> list[Path]:
        env_dependencies = os.environ.get("CCRS_JAVA_DEPENDENCY_CLASSPATH")
        if env_dependencies:
            logger.info(
                "%s Using CCRS_JAVA_DEPENDENCY_CLASSPATH for Java dependencies.",
                LOG_PREFIX,
            )
            return [
                Path(path)
                for path in env_dependencies.split(os.pathsep)
                if path
            ]

        gradle_jars = _runtime_jars_under(self.gradle_cache)
        if gradle_jars:
            logger.debug(
                "%s Using %s runtime jars from Gradle dependency cache.",
                LOG_PREFIX,
                len(gradle_jars),
            )
            return gradle_jars

        maven_jars = _runtime_jars_under(self.maven_repo)
        logger.debug(
            "%s Using %s runtime jars from Maven local repository.",
            LOG_PREFIX,
            len(maven_jars),
        )
        return maven_jars

    def _new_java_array_list(self) -> Any:
        return self._classes["ArrayList"]()

    def _new_java_hash_map(self, values: Mapping[str, Any]) -> Any:
        java_map = self._classes["HashMap"]()
        for key, value in values.items():
            if value is not None:
                java_map.put(str(key), str(value))
        return java_map

    def _opportunistic_result_to_dict(
        self,
        result: Any,
        context: Mapping[str, Any],
    ) -> dict[str, Any]:
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
        logger.debug("%s Converted Java opportunistic CCRS result: %s", LOG_PREFIX, entry)
        return entry

    def _require_jpype(self) -> Any:
        try:
            import jpype
        except ImportError as exc:
            raise CcrsRuntimeError(
                "JPype1 is required for CCRS Java integration. Install the "
                "project requirements before running the CCRS adapter."
            ) from exc
        return jpype


def get_default_runtime() -> CcrsRuntime:
    global _default_runtime
    if _default_runtime is None:
        _default_runtime = CcrsRuntime.from_maven_local()
    return _default_runtime


def _runtime_jars_under(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*.jar")
        if not _is_non_runtime_jar(path)
    )


def _is_non_runtime_jar(path: Path) -> bool:
    name = path.name
    return name.endswith("-sources.jar") or name.endswith("-javadoc.jar")


_default_runtime: CcrsRuntime | None = None
