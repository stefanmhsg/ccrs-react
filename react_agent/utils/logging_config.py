import logging
import os
from logging import Logger

def setup_logging(level: int = logging.INFO, run_name: str = "run") -> Logger:
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        filename=os.path.join(log_dir, f"{run_name}.log"),
        filemode="w",
        
    )
    return logging.getLogger(__name__)
