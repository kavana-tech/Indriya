"""Matplotlib ping round-trip-delay chart for the connect app."""

from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Deque, List

import tkinter as tk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

PING_HISTORY = 200  # ~20 s of history at a 100 ms ping interval


class PingChart:
    """One chart: raw round-trip PING delay (ms) plus a flat line at the window average."""

    def __init__(self, parent: tk.Widget):
        self._lock = Lock()
        self._pending: List[float] = []
        self._samples: Deque[float] = deque(maxlen=PING_HISTORY)
        self._dirty = False

        self.figure = Figure(figsize=(8.5, 3.6), dpi=90, facecolor="#101010")
        self.figure.subplots_adjust(left=0.08, right=0.98, top=0.90, bottom=0.12)
        self._ax = self.figure.add_subplot(111)
        self._ax.set_facecolor("#000000")
        self._ax.set_title("Ping delay (ms)", fontsize=9, color="#dddddd", pad=3)
        self._ax.grid(True, color="#222222", linewidth=0.6)
        self._ax.tick_params(labelsize=7, colors="#888888")
        for spine in self._ax.spines.values():
            spine.set_color("#333333")

        (self._line_raw,) = self._ax.plot([], [], lw=0.9, color="#56b4e9", label="delay")
        (self._line_avg,) = self._ax.plot(
            [], [], lw=1.3, color="#f0e442", linestyle="--", label="average"
        )
        legend = self._ax.legend(loc="upper right", fontsize=7, framealpha=0.35)
        legend.get_frame().set_facecolor("#111111")
        for t in legend.get_texts():
            t.set_color("#cccccc")

        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        widget = self.canvas.get_tk_widget()
        widget.configure(bg="#101010", highlightthickness=0)
        widget.pack(fill=tk.BOTH, expand=True)
        self.canvas.draw()

    def enqueue(self, delay_ms: float) -> None:
        """Thread-safe: call directly from the SDK's ping-response callback."""
        with self._lock:
            self._pending.append(delay_ms)

    def clear(self) -> None:
        with self._lock:
            self._pending.clear()
            self._samples.clear()
            self._dirty = True

    def drain_and_redraw(self) -> None:
        """Call from the Tk-thread chart-refresh tick."""
        with self._lock:
            pending = self._pending
            self._pending = []
            if pending:
                self._samples.extend(pending)
                self._dirty = True
            samples = list(self._samples)

        if not self._dirty:
            return
        self._dirty = False

        if not samples:
            return

        xs = list(range(len(samples)))
        average = sum(samples) / len(samples)
        last_x = len(samples) - 1

        self._line_raw.set_data(xs, samples)
        self._line_avg.set_data([0, max(last_x, 0)], [average, average])

        lo, hi = min(samples), max(samples)
        if hi <= lo:
            hi = lo + 1.0
        pad = 0.1 * (hi - lo)
        self._ax.set_xlim(0, max(1, last_x))
        self._ax.set_ylim(max(0.0, lo - pad), hi + pad)

        self.canvas.draw()
