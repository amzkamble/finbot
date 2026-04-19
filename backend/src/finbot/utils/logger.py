"""Structured logging configuration for the FinBot application."""

from __future__ import annotations

import logging
import sys
from typing import Any


def get_logger(name: str, level: str | None = None) -> logging.Logger:
    """
    Return a configured logger for the given module name.

    Usage::

        from finbot.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Pipeline started", extra={"collection": "finance"})
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    if level:
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    elif logger.level == logging.NOTSET:
        logger.setLevel(logging.INFO)

    return logger
