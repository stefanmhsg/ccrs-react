from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

from react_agent.ccrs.audit import log_ccrs_event


JAVA_LOG_FILE_ENV = "REACT_AGENT_JAVA_LOG_FILE"
PYTHON_LOG_FILE_ENV = "REACT_AGENT_LOG_FILE"

_lock = threading.Lock()
_configured_handler: Any | None = None
_configured_path: Path | None = None


def configure_java_ccrs_logging(
    jpype: Any,
    logger: logging.Logger,
    *,
    level_name: str = "FINE",
) -> Path | None:
    """Route Java CCRS JUL records to a React-run companion log file."""

    global _configured_handler, _configured_path

    java_log_path = _java_log_path()
    if java_log_path is None:
        log_ccrs_event(
            logger,
            "react.ccrs.java_logging.skipped",
            {"reason": "missing_react_log_file"},
        )
        return None

    java_log_path.parent.mkdir(parents=True, exist_ok=True)

    with _lock:
        if _configured_path == java_log_path and _configured_handler is not None:
            return java_log_path

        java_logger = jpype.JClass("java.util.logging.Logger")
        java_level = jpype.JClass("java.util.logging.Level")
        java_file_handler = jpype.JClass("java.util.logging.FileHandler")
        java_simple_formatter = jpype.JClass("java.util.logging.SimpleFormatter")
        java_system = jpype.JClass("java.lang.System")

        level = java_level.parse(level_name)
        ccrs_logger = java_logger.getLogger("ccrs")

        _remove_previous_handler(ccrs_logger)

        java_system.setProperty(
            "java.util.logging.SimpleFormatter.format",
            "%1$tF %1$tT,%1$tL [JAVA-CCRS] %3$s: %5$s%6$s%n",
        )
        handler = java_file_handler(str(java_log_path), True)
        handler.setLevel(level)
        handler.setFormatter(java_simple_formatter())

        ccrs_logger.addHandler(handler)
        ccrs_logger.setLevel(level)
        ccrs_logger.setUseParentHandlers(False)

        _configured_handler = handler
        _configured_path = java_log_path

    log_ccrs_event(
        logger,
        "react.ccrs.java_logging.configured",
        {"path": java_log_path, "level": level_name},
    )
    return java_log_path


def _java_log_path() -> Path | None:
    explicit = os.environ.get(JAVA_LOG_FILE_ENV)
    if explicit:
        return Path(explicit).resolve()

    python_log = os.environ.get(PYTHON_LOG_FILE_ENV)
    if not python_log:
        return None

    path = Path(python_log).resolve()
    return path.with_name(f"{path.stem}.java.log")


def _remove_previous_handler(ccrs_logger: Any) -> None:
    global _configured_handler, _configured_path

    if _configured_handler is None:
        return

    try:
        ccrs_logger.removeHandler(_configured_handler)
        _configured_handler.close()
    finally:
        _configured_handler = None
        _configured_path = None
