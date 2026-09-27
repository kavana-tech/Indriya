"""Packet-loss windowing helper.

The actual loss detection — a scale-free continuity check on the raw,
pre-scale channel-0 integer straight off the wire — lives entirely in the
native core now (``PacketLossStats`` in
``core/Computation/CommonTypes.h``, fed from ``Parser.cpp`` and exposed via
``ComputationManager``/``computation_wrapper``'s
``get_packet_loss_stats``/``reset_packet_loss_stats``). Python never sees a
raw sample or a scale factor for this.

This class only turns periodic reads of those two cumulative native counters
(samples seen, samples lost) into a "how much was lost in roughly the last
second" percentage and a live sample rate, purely from elapsed wall-clock
time between reads. It has no notion of which sensor it's for and no notion
of test mode — the same instance works identically for any sensor.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Deque, Tuple

WINDOW_S = 1.0


class PacketLossWindow:
    """Feed it the native cumulative ``(samples_seen, samples_lost)`` counters
    (e.g. once per ready-callback) via ``update()``; it derives the loss
    percentage over the last ``window_s`` seconds and a live ``rate_hz``,
    from nothing but how those counters changed between calls.
    """

    def __init__(self, window_s: float = WINDOW_S):
        self._window_s = window_s
        self._history: Deque[Tuple[float, int, int]] = deque()
        self._start_t0 = time.perf_counter()
        self.rate_hz = 0.0
        self._rate_count = 0
        self._rate_t0 = time.perf_counter()

    def update(self, samples_seen: int, samples_lost: int) -> float:
        """Record the latest native cumulative counters; returns the windowed
        loss percentage over the last window_s seconds."""
        now = time.perf_counter()

        if not self._history:
            # Seed with a synthetic zero baseline at the moment tracking
            # started (construction or last reset()), so loss already
            # present in the very first reading is counted immediately
            # instead of silently becoming the new baseline (which would
            # otherwise always report 0% on the first call).
            self._history.append((self._start_t0, 0, 0))

        _, prev_seen, _ = self._history[-1]
        self._rate_count += max(0, samples_seen - prev_seen)
        self._history.append((now, samples_seen, samples_lost))

        cutoff = now - self._window_s
        while len(self._history) > 1 and self._history[0][0] < cutoff:
            self._history.popleft()

        _, base_seen, base_lost = self._history[0]
        d_seen = samples_seen - base_seen
        d_lost = samples_lost - base_lost
        total = d_seen + d_lost
        windowed_pct = (100.0 * d_lost / total) if total else 0.0

        elapsed = now - self._rate_t0
        if elapsed >= WINDOW_S:
            self.rate_hz = self._rate_count / elapsed
            self._rate_count = 0
            self._rate_t0 = now

        return windowed_pct

    def reset(self) -> None:
        """Call whenever the native counters are reset, so stale cumulative
        values aren't diffed against the fresh (zeroed) ones."""
        self._history.clear()
        self._start_t0 = time.perf_counter()
        self.rate_hz = 0.0
        self._rate_count = 0
        self._rate_t0 = time.perf_counter()
