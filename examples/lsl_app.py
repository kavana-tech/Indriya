"""Mudra LSL streamer — scan, connect, publish sensors to the Lab Streaming Layer."""

from __future__ import annotations

import sys
from pathlib import Path

_EXAMPLES_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _EXAMPLES_DIR.parent
for _path in (_EXAMPLES_DIR, _REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from mudra_lsl import main

if __name__ == "__main__":
    # Logging is configured inside main() from --log-level.
    raise SystemExit(main())
