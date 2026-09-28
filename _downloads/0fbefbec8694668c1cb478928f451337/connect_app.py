"""Mudra Pro connect app — scan, connect, stream, configure, record."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_EXAMPLES_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _EXAMPLES_DIR.parent
for _path in (_EXAMPLES_DIR, _REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from mudra_sdk.logging_config import configure_logging
from mudra_connect import main

if __name__ == "__main__":
    configure_logging(logging.INFO)
    main()
