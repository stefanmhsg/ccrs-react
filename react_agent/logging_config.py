import logging
from logging import Logger

def setup_logging(level: int = logging.INFO, run_name: str = "run") -> Logger:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        filename=f"{run_name}.log",
        filemode="w",
        
    )
    return logging.getLogger(__name__)
