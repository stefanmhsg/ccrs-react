import logging
from logging import Logger

def setup_logging(level: int = logging.INFO) -> Logger:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        filename="run.log",
        filemode="w",
    )
    return logging.getLogger(__name__)
