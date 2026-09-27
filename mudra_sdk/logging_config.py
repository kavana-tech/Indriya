"""Central logging setup for the SDK and example apps.

Mirrors the severity levels used by the native C++ core
(``mudra_sdk/core/Computation/Logging.h``: Debug/Info/Warning/Error) so
Python-side output goes through the same kind of leveled logger instead of
bare ``print()``.

Library modules should just do::

    from mudra_sdk.logging_config import get_logger
    logger = get_logger(__name__)

An application entry point (e.g. ``connect_app.py``)
should call :func:`configure_logging` once at startup to see the output on
the console.
"""

from __future__ import annotations

import logging
import sys

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def configure_logging(level: int = logging.INFO) -> None:
    """Install a console handler on the root logger, if one isn't already there.

    Safe to call more than once — later calls just adjust the level.
    """
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
