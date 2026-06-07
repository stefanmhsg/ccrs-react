import logging
import os
from pathlib import Path
from logging import Logger

def setup_logging(level: int = logging.INFO, run_name: str = "run") -> Logger:
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_path = (log_dir / f"{run_name}.log").resolve()
    java_log_path = log_path.with_name(f"{log_path.stem}.java.log")

    os.environ["REACT_AGENT_LOG_FILE"] = str(log_path)
    os.environ["REACT_AGENT_JAVA_LOG_FILE"] = str(java_log_path)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        filename=str(log_path),
        filemode="w",
        # Notebook kernels often configure root logging before launch_agent runs.
        # Without force=True, basicConfig is a no-op and the Python run log is
        # not created even though the Java log path is exported above.
        force=True,
    )
    return logging.getLogger(__name__)
