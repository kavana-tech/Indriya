"""Mudra LSL streamer — headless: scan, connect, publish a device's sensors to
the Lab Streaming Layer. Launched by ``examples/lsl_app.py``; the library it
drives is :mod:`mudra_sdk.lsl` (guide: ``docs/LSL.md``)."""

from __future__ import annotations

from .cli import main

__all__ = ["main"]
