"""Logging utilities for the Xiaohongshu automation project."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional


DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"


def configure_logger(
    name: str,
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
    fmt: str = DEFAULT_LOG_FORMAT,
) -> logging.Logger:
    """Create and configure a logger.

    Parameters
    ----------
    name:
        Name of the logger.
    log_file:
        Optional path to a log file. If provided the directory will be created
        and log messages will be written to the file in addition to stderr.
    level:
        Logging level to use. Defaults to :data:`logging.INFO`.
    fmt:
        Log message format.

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """

    logger = logging.getLogger(name)

    if logger.handlers:
        # Logger already configured.
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(fmt)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_file is not None:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


__all__ = ["configure_logger", "DEFAULT_LOG_FORMAT"]
