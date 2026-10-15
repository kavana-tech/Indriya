"""Asyncio loop bridge for Tkinter (daemon thread + run_coroutine_threadsafe)."""

from __future__ import annotations

import asyncio
from threading import Thread
from typing import Callable, Optional


class AsyncBridge:
    """Owns a background asyncio loop used for BLE / Mudra coroutines."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[Thread] = None

    @property
    def loop(self) -> Optional[asyncio.AbstractEventLoop]:
        return self._loop

    def ensure_running(self) -> None:
        if self._loop is not None:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def submit(self, coro) -> None:
        self.ensure_running()
        assert self._loop is not None
        asyncio.run_coroutine_threadsafe(coro, self._loop)

    def run(self, label: str, coro_fn: Callable, on_error: Optional[Callable[[str], None]] = None) -> None:
        """Schedule ``coro_fn()``; report failures via ``on_error``."""

        async def _wrapped():
            try:
                await coro_fn()
            except Exception as exc:  # noqa: BLE001 — surface any BLE/device error to UI
                if on_error is not None:
                    on_error(f"{label} failed: {exc}")

        self.submit(_wrapped())
