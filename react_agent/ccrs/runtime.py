from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Iterable, Mapping

from react_agent.ccrs.audit import log_ccrs_event
from react_agent.ccrs.java_logging import configure_java_ccrs_logging
from react_agent.ccrs.rdf_adapter import RdfTripleValue, parse_turtle_triples


logger = logging.getLogger(__name__)
LOG_PREFIX = "[React CCRS][Opportunistic]"


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
    _runtime_dependencies: ClassVar[tuple[tuple[str, str, str], ...]] = (
        ("org.apache.jena", "jena-rdfpatch", "5.6.0"),
        ("org.apache.jena", "jena-arq", "5.6.0"),
        ("org.apache.jena", "jena-core", "5.6.0"),
        ("org.apache.jena", "jena-base", "5.6.0"),
        ("org.apache.jena", "jena-iri3986", "5.6.0"),
        ("org.apache.jena", "jena-iri", "5.6.0"),
        ("org.apache.jena", "jena-langtag", "5.6.0"),
        ("org.apache.jena", "jena-ontapi", "5.6.0"),
        ("org.apache.jena", "jena-shacl", "5.6.0"),
        ("org.apache.jena", "jena-shex", "5.6.0"),
        ("org.apache.jena", "jena-tdb1", "5.6.0"),
        ("org.apache.jena", "jena-tdb2", "5.6.0"),
        ("org.apache.jena", "jena-dboe-storage", "5.6.0"),
        ("org.apache.jena", "jena-dboe-trans-data", "5.6.0"),
        ("org.apache.jena", "jena-dboe-transaction", "5.6.0"),
        ("org.apache.jena", "jena-dboe-base", "5.6.0"),
        ("org.apache.jena", "jena-dboe-index", "5.6.0"),
        ("org.apache.jena", "jena-rdfconnection", "5.6.0"),
        ("org.slf4j", "slf4j-api", "2.0.17"),
        ("org.slf4j", "jcl-over-slf4j", "2.0.17"),
        ("org.apache.commons", "commons-csv", "1.14.1"),
        ("commons-io", "commons-io", "2.20.0"),
        ("commons-codec", "commons-codec", "1.19.0"),
        ("org.apache.commons", "commons-lang3", "3.19.0"),
        ("org.apache.commons", "commons-compress", "1.28.0"),
        ("org.apache.commons", "commons-collections4", "4.5.0"),
        ("com.github.ben-manes.caffeine", "caffeine", "3.2.2"),
        ("org.jspecify", "jspecify", "1.0.0"),
        ("com.github.andrewoma.dexx", "collection", "0.7"),
        ("org.roaringbitmap", "RoaringBitmap", "1.3.0"),
        ("com.google.code.gson", "gson", "2.13.2"),
        ("com.google.errorprone", "error_prone_annotations", "2.41.0"),
        ("com.apicatalog", "titanium-json-ld", "1.7.0"),
        ("com.apicatalog", "titanium-jcs", "1.1.1"),
        ("com.apicatalog", "titanium-rdf-api", "1.0.0"),
        ("com.apicatalog", "titanium-rdf-n-quads", "1.0.2"),
        ("org.glassfish", "jakarta.json", "2.0.1"),
        ("com.google.protobuf", "protobuf-java", "4.32.1"),
        ("org.apache.thrift", "libthrift", "0.22.0"),
    )

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

        logger.debug(
            "%s Resolved %s Java classpath entries for JPype.",
            LOG_PREFIX,
            len(unique),
        )
        log_ccrs_event(
            logger,
            "react.ccrs.opportunistic.classpath.resolved",
            {
                "entries": len(unique),
                "modules": ",".join(self.modules),
                "maven_repo": self.maven_repo,
                "gradle_cache": self.gradle_cache,
            },
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
                logger.debug(
                    "%s Starting JPype JVM for opportunistic CCRS; classpath_entries=%s",
                    LOG_PREFIX,
                    len(classpath),
                )
                log_ccrs_event(
                    logger,
                    "react.ccrs.opportunistic.jvm.start",
                    {"classpath_entries": len(classpath)},
                )
                jpype.startJVM(classpath=classpath, convertStrings=True)

            self._load_classes(jpype)
            self._configure_java_logging(jpype)
            if self._opportunistic_ccrs is None:
                logger.debug(
                    "%s Loading default CCRS vocabulary and creating Java "
                    "VocabularyMatcher.",
                    LOG_PREFIX,
                )
                vocabulary = self._classes["CcrsVocabularyLoader"].loadDefault()
                self._opportunistic_ccrs = self._classes["VocabularyMatcher"](vocabulary)
                log_ccrs_event(
                    logger,
                    "react.ccrs.opportunistic.runtime.ready",
                    {"scanner": "ccrs.core.opportunistic.VocabularyMatcher"},
                )

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
        try:
            java_log_path = configure_java_ccrs_logging(jpype, logger)
            logger.info(
                "%s Configured Java CCRS library logging through JPype; path=%s",
                LOG_PREFIX,
                java_log_path,
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

        dependency_jars = self._resolve_declared_dependency_jars()
        logger.info(
            "%s Resolved %s declared Java dependency jars for opportunistic CCRS.",
            LOG_PREFIX,
            len(dependency_jars),
        )
        return dependency_jars

    def _resolve_declared_dependency_jars(self) -> list[Path]:
        jars: list[Path] = []
        missing: list[str] = []
        for group, artifact_id, version in self._runtime_dependencies:
            jar = self._find_dependency_jar(group, artifact_id, version)
            if jar is None:
                missing.append(f"{group}:{artifact_id}:{version}")
            else:
                jars.append(jar)

        if missing:
            logger.warning(
                "%s Missing declared dependency jars: %s",
                LOG_PREFIX,
                ", ".join(missing),
            )
            log_ccrs_event(
                logger,
                "react.ccrs.opportunistic.classpath.missing_dependencies",
                {"count": len(missing), "coordinates": ",".join(missing)},
            )
        return jars

    def _find_dependency_jar(
        self,
        group: str,
        artifact_id: str,
        version: str,
    ) -> Path | None:
        maven_jar = self._find_artifact_jar_in_maven(self.maven_repo, group, artifact_id, version)
        if maven_jar is not None:
            return maven_jar
        return self._find_artifact_jar_in_gradle_cache(group, artifact_id, version)

    def _find_artifact_jar_in_maven(
        self,
        root: Path,
        group: str,
        artifact_id: str,
        version: str,
    ) -> Path | None:
        artifact_dir = root.joinpath(*group.split("."), artifact_id, version)
        if not artifact_dir.exists():
            return None
        candidates = sorted(
            path
            for path in artifact_dir.glob(f"{artifact_id}-{version}*.jar")
            if not _is_non_runtime_jar(path)
        )
        return candidates[0] if candidates else None

    def _find_artifact_jar_in_gradle_cache(
        self,
        group: str,
        artifact_id: str,
        version: str,
    ) -> Path | None:
        artifact_dir = self.gradle_cache.joinpath(group, artifact_id, version)
        if not artifact_dir.exists():
            return None
        candidates = sorted(
            path
            for path in artifact_dir.rglob(f"{artifact_id}-{version}*.jar")
            if not _is_non_runtime_jar(path)
        )
        return candidates[0] if candidates else None

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


def _is_non_runtime_jar(path: Path) -> bool:
    name = path.name
    return name.endswith("-sources.jar") or name.endswith("-javadoc.jar")


_default_runtime: CcrsRuntime | None = None
