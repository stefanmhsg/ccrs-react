"""Shared Java runtime support for CCRS adapter wrappers.

This module provides the JPype JVM, Maven/Gradle classpath resolution, Java
class lookup, and Java logging setup used by the Python wrappers for Java CCRS
features.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Iterable, Mapping

from react_agent.ccrs.audit import log_ccrs_event
from react_agent.ccrs.capabilities import (
    CCRS_A2A_MODULE,
    CCRS_CORE_MODULE,
    CCRS_LANGCHAIN4J_MODULE,
)
from react_agent.ccrs.java_logging import configure_java_ccrs_logging


logger = logging.getLogger(__name__)
LOG_PREFIX = "[React CCRS][JavaRuntime]"


class CcrsJavaRuntimeError(RuntimeError):
    """Raised when Java CCRS runtime setup or calls fail."""


def _default_maven_repo() -> Path:
    return Path(os.environ.get("M2_REPO", Path.home() / ".m2" / "repository"))


def _default_gradle_cache() -> Path:
    return Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1"


@dataclass
class CcrsJavaRuntime:
    """Resolves and starts the Java environment used by CCRS wrappers."""

    group: str = "io.github.stefanmhsg.ccrs"
    version: str = "0.1.0-SNAPSHOT"
    modules: tuple[str, ...] = (CCRS_CORE_MODULE,)
    maven_repo: Path = field(default_factory=_default_maven_repo)
    gradle_cache: Path = field(default_factory=_default_gradle_cache)
    extra_classpath: tuple[Path, ...] = ()

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
    _module_runtime_dependencies: ClassVar[dict[str, tuple[tuple[str, str, str], ...]]] = {
        CCRS_LANGCHAIN4J_MODULE: (
            ("dev.langchain4j", "langchain4j-open-ai", "1.10.0"),
            ("dev.langchain4j", "langchain4j", "1.10.0"),
            ("dev.langchain4j", "langchain4j-core", "1.10.0"),
            ("dev.langchain4j", "langchain4j-http-client", "1.10.0"),
            ("dev.langchain4j", "langchain4j-http-client-jdk", "1.10.0"),
            ("com.knuddels", "jtokkit", "1.1.0"),
            ("io.github.cdimascio", "dotenv-java", "3.0.0"),
        ),
        CCRS_A2A_MODULE: (
            ("io.github.cdimascio", "dotenv-java", "3.0.0"),
            ("io.github.a2asdk", "a2a-java-sdk-reference-rest", "0.3.3.Final"),
            ("io.github.a2asdk", "a2a-java-sdk-client", "0.3.3.Final"),
            ("io.github.a2asdk", "a2a-java-sdk-client-transport-rest", "0.3.3.Final"),
            ("io.github.a2asdk", "a2a-java-sdk-client-transport-spi", "0.3.3.Final"),
            ("io.github.a2asdk", "a2a-java-sdk-common", "0.3.3.Final"),
            ("io.github.a2asdk", "a2a-java-sdk-http-client", "0.3.3.Final"),
            ("io.github.a2asdk", "a2a-java-sdk-spec", "0.3.3.Final"),
        ),
    }

    @classmethod
    def from_maven_local(
        cls,
        *,
        group: str = "io.github.stefanmhsg.ccrs",
        version: str = "0.1.0-SNAPSHOT",
        modules: Iterable[str] = (CCRS_CORE_MODULE,),
        maven_repo: str | Path | None = None,
        gradle_cache: str | Path | None = None,
        extra_classpath: Iterable[str | Path] = (),
    ) -> "CcrsJavaRuntime":
        return cls(
            group=group,
            version=version,
            modules=tuple(modules),
            maven_repo=Path(maven_repo) if maven_repo is not None else _default_maven_repo(),
            gradle_cache=Path(gradle_cache) if gradle_cache is not None else _default_gradle_cache(),
            extra_classpath=tuple(Path(path) for path in extra_classpath),
        )

    def ensure_jvm(
        self,
        *,
        audit_event_namespace: str,
        log: logging.Logger,
        log_prefix: str,
    ) -> Any:
        """Start JPype or attach classpath entries before a Java CCRS call."""

        jpype = require_jpype()
        with self._jvm_lock:
            classpath = [str(path) for path in self.resolve_classpath(audit_event_namespace)]
            if jpype.isJVMStarted():
                log.info("%s JPype JVM already started; adding CCRS classpath entries.", log_prefix)
                for path in classpath:
                    jpype.addClassPath(path)
            else:
                log_ccrs_event(
                    log,
                    f"{audit_event_namespace}.jvm.start",
                    {"classpath_entries": len(classpath)},
                )
                jpype.startJVM(classpath=classpath, convertStrings=True)
            self.configure_java_logging(jpype, log, log_prefix)
        return jpype

    def resolve_classpath(self, audit_event_namespace: str) -> list[Path]:
        """Resolve the CCRS module jar and declared runtime dependencies."""

        paths: list[Path] = []

        env_classpath = os.environ.get("CCRS_JAVA_CLASSPATH")
        if env_classpath:
            paths.extend(Path(path) for path in env_classpath.split(os.pathsep) if path)
            logger.info("%s Added CCRS_JAVA_CLASSPATH entries for JPype classpath.", LOG_PREFIX)

        paths.extend(self.extra_classpath)
        paths.extend(self._resolve_module_jars())
        paths.extend(self._resolve_dependency_jars(audit_event_namespace))

        seen: set[str] = set()
        unique: list[Path] = []
        for path in paths:
            resolved = path.resolve()
            key = str(resolved).lower()
            if resolved.exists() and key not in seen:
                unique.append(resolved)
                seen.add(key)

        if not unique:
            raise CcrsJavaRuntimeError("No Java classpath entries found for CCRS.")

        log_ccrs_event(
            logger,
            f"{audit_event_namespace}.classpath.resolved",
            {
                "entries": len(unique),
                "modules": ",".join(self.modules),
                "maven_repo": self.maven_repo,
                "gradle_cache": self.gradle_cache,
            },
        )
        return unique

    def class_(self, jpype: Any, class_name: str) -> Any:
        """Load and cache a Java class needed by a CCRS wrapper."""

        if class_name not in self._classes:
            self._classes[class_name] = jpype.JClass(class_name)
        return self._classes[class_name]

    def new_array_list(self, jpype: Any) -> Any:
        return self.class_(jpype, "java.util.ArrayList")()

    def new_hash_map(self, jpype: Any, values: Mapping[str, Any]) -> Any:
        java_map = self.class_(jpype, "java.util.HashMap")()
        for key, value in values.items():
            if value is not None:
                java_map.put(str(key), str(value))
        return java_map

    def configure_java_logging(self, jpype: Any, log: logging.Logger, log_prefix: str) -> None:
        try:
            java_log_path = configure_java_ccrs_logging(jpype, log)
            log.info("%s Configured Java CCRS library logging through JPype; path=%s", log_prefix, java_log_path)
        except Exception:
            log.exception("%s Failed to configure Java CCRS library logging level.", log_prefix)

    def _resolve_module_jars(self) -> list[Path]:
        return [self._find_maven_artifact_jar(module) for module in self.modules]

    def _find_maven_artifact_jar(self, artifact_id: str) -> Path:
        artifact_dir = self.maven_repo.joinpath(*self.group.split("."), artifact_id, self.version)
        if not artifact_dir.exists():
            raise CcrsJavaRuntimeError(f"Missing Maven-local CCRS artifact directory: {artifact_dir}")

        candidates = sorted(
            path
            for path in artifact_dir.glob(f"{artifact_id}-{self.version}*.jar")
            if not _is_non_runtime_jar(path)
        )
        if not candidates:
            raise CcrsJavaRuntimeError(
                f"Missing Maven-local CCRS runtime jar for {artifact_id}:{self.version}"
            )
        logger.info("%s Resolved Maven-local CCRS module jar; module=%s path=%s", LOG_PREFIX, artifact_id, candidates[0])
        return candidates[0]

    def _resolve_dependency_jars(self, audit_event_namespace: str) -> list[Path]:
        env_dependencies = os.environ.get("CCRS_JAVA_DEPENDENCY_CLASSPATH")
        if env_dependencies:
            logger.info("%s Using CCRS_JAVA_DEPENDENCY_CLASSPATH for Java dependencies.", LOG_PREFIX)
            return [Path(path) for path in env_dependencies.split(os.pathsep) if path]

        jars: list[Path] = []
        missing: list[str] = []
        dependency_coordinates = list(self._runtime_dependencies)
        for module in self.modules:
            dependency_coordinates.extend(self._module_runtime_dependencies.get(module, ()))

        seen_coordinates: set[tuple[str, str, str]] = set()
        for group, artifact_id, version in dependency_coordinates:
            coordinate = (group, artifact_id, version)
            if coordinate in seen_coordinates:
                continue
            seen_coordinates.add(coordinate)
            jar = self._find_dependency_jar(group, artifact_id, version)
            if jar is None:
                missing.append(f"{group}:{artifact_id}:{version}")
            else:
                jars.append(jar)

        if missing:
            logger.warning("%s Missing declared dependency jars: %s", LOG_PREFIX, ", ".join(missing))
            log_ccrs_event(
                logger,
                f"{audit_event_namespace}.classpath.missing_dependencies",
                {"count": len(missing), "coordinates": ",".join(missing)},
            )
        return jars

    def _find_dependency_jar(self, group: str, artifact_id: str, version: str) -> Path | None:
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

    def _find_artifact_jar_in_gradle_cache(self, group: str, artifact_id: str, version: str) -> Path | None:
        artifact_dir = self.gradle_cache.joinpath(group, artifact_id, version)
        if not artifact_dir.exists():
            return None
        candidates = sorted(
            path
            for path in artifact_dir.rglob(f"{artifact_id}-{version}*.jar")
            if not _is_non_runtime_jar(path)
        )
        return candidates[0] if candidates else None


def get_default_java_runtime() -> CcrsJavaRuntime:
    """Return the process-local Java runtime used by default CCRS wrappers."""

    global _default_java_runtime
    if _default_java_runtime is None:
        _default_java_runtime = CcrsJavaRuntime.from_maven_local()
    return _default_java_runtime


def require_jpype() -> Any:
    """Import JPype and raise a CCRS-specific error if it is unavailable."""

    try:
        import jpype
    except ImportError as exc:
        raise CcrsJavaRuntimeError(
            "JPype1 is required for CCRS Java integration. Install the project "
            "requirements before running the CCRS adapter."
        ) from exc
    return jpype


def _is_non_runtime_jar(path: Path) -> bool:
    name = path.name
    return name.endswith("-sources.jar") or name.endswith("-javadoc.jar")


_default_java_runtime: CcrsJavaRuntime | None = None
