"""Lost-packet percentage chart — one line per sensor, for the packet-loss panel."""

from __future__ import annotations

from collections import deque
from typing import Deque, Dict, List, Optional

import tkinter as tk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

HISTORY = 200  # ticks of history, driven by the app's chart-refresh tick

SENSOR_COLORS = {
    "EMG": "#f0e442",
    "IMU_H": "#e74c3c",
    "IMU_F": "#3498db",
    "PPG": "#00bcd4",
}

SENSOR_LABELS = {
    "EMG": "EMG",
    "IMU_H": "IMU hand",
    "IMU_F": "IMU ring",
    "PPG": "PPG",
}


class PacketLossChart:
    """Lost-packet percentage (0-100) per sensor, sampled once per redraw tick.

    Driven by a fixed-cadence clock tick (app.py polls the detectors' current
    value every CHART_REFRESH_MS, not event-driven from real samples like the
    other charts). ``sample_tick`` marks the chart dirty whenever a sensor is
    actively running (so the line keeps scrolling even at a steady 0% loss —
    new zero samples are still new data) or a value actually *changed*; a
    sensor that isn't running at all never marks dirty, so a fully idle chart
    (nothing running, everything flat at 0%) still costs effectively nothing
    instead of a ~50ms full redraw 20x/second. ``redraw`` blits (no
    full-figure draw) to keep the per-tick cost low while a test is running.
    """

    def __init__(self, parent: tk.Widget, sensors: List[str]):
        self._sensors = sensors
        self._history: Dict[str, Deque[float]] = {
            s: deque([0.0] * HISTORY, maxlen=HISTORY) for s in sensors
        }
        self._dirty = False
        self._blit_ready = False

        self.figure = Figure(figsize=(8.5, 3.2), dpi=90, facecolor="#101010")
        self.figure.subplots_adjust(left=0.08, right=0.98, top=0.90, bottom=0.12)
        self._ax = self.figure.add_subplot(111)
        self._ax.set_facecolor("#000000")
        self._ax.set_title(
            "Packets lost (%, last ~1s, native raw-counter check)", fontsize=9, color="#dddddd", pad=3
        )
        self._ax.grid(True, color="#222222", linewidth=0.6)
        self._ax.tick_params(labelsize=7, colors="#888888")
        for spine in self._ax.spines.values():
            spine.set_color("#333333")
        self._ax.set_xlim(0, HISTORY - 1)
        # Fixed [0, 100] — always a percentage, never rescaled — which is what
        # makes blitting safe here (axes/limits never change after this).
        self._ax.set_ylim(0, 100)

        xs = list(range(HISTORY))
        self._lines = {}
        self._avg_lines = {}
        self._avg_values: Dict[str, float] = {s: 0.0 for s in sensors}
        for sensor in sensors:
            (line,) = self._ax.plot(
                xs,
                [0.0] * HISTORY,
                lw=1.1,
                color=SENSOR_COLORS[sensor],
                label=SENSOR_LABELS[sensor],
                animated=True,
            )
            self._lines[sensor] = line
            # Flat dashed reference line at the current (last ~1s) value —
            # same color as the sensor's data line so it reads as "where
            # that sensor is right now" without needing its own legend entry.
            (avg_line,) = self._ax.plot(
                [0, HISTORY - 1],
                [0.0, 0.0],
                lw=1.0,
                linestyle="--",
                color=SENSOR_COLORS[sensor],
                alpha=0.5,
                animated=True,
            )
            self._avg_lines[sensor] = avg_line
        legend = self._ax.legend(loc="upper left", fontsize=7, framealpha=0.35)
        legend.get_frame().set_facecolor("#111111")
        for text in legend.get_texts():
            text.set_color("#cccccc")

        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        widget = self.canvas.get_tk_widget()
        widget.configure(bg="#101010", highlightthickness=0)
        widget.pack(fill=tk.BOTH, expand=True)
        self.canvas.draw()
        self._bg = self.canvas.copy_from_bbox(self._ax.bbox)
        self._blit_ready = True
        widget.bind("<Configure>", self._on_resize)

    def _on_resize(self, _event=None) -> None:
        self._blit_ready = False
        self.canvas.draw()
        self._bg = self.canvas.copy_from_bbox(self._ax.bbox)
        self._blit_ready = True

    def sample_tick(
        self,
        loss_pct_by_sensor: Dict[str, float],
        active_sensors: Optional[Dict[str, bool]] = None,
        avg_pct_by_sensor: Optional[Dict[str, float]] = None,
    ) -> None:
        """Call once per redraw tick with each sensor's current loss percentage
        (0-100), which sensors are actively running, and (usually the same)
        current value again for the flat reference line. A running sensor
        stays dirty even at a constant value, so the line keeps scrolling;
        a sensor that isn't running only redraws on an actual value change
        (there isn't one, since nothing feeds it) — an idle chart is
        essentially free."""
        active_sensors = active_sensors or {}
        avg_pct_by_sensor = avg_pct_by_sensor or {}
        for sensor in self._sensors:
            value = loss_pct_by_sensor.get(sensor, 0.0)
            history = self._history[sensor]
            if active_sensors.get(sensor) or not history or history[-1] != value:
                self._dirty = True
            history.append(value)

            avg = avg_pct_by_sensor.get(sensor, 0.0)
            if self._avg_values.get(sensor) != avg:
                self._avg_values[sensor] = avg
                self._avg_lines[sensor].set_ydata([avg, avg])
                self._dirty = True

    def redraw(self) -> None:
        if not self._dirty:
            return
        self._dirty = False

        for sensor in self._sensors:
            self._lines[sensor].set_ydata(list(self._history[sensor]))

        if not self._blit_ready:
            self.canvas.draw()
            self._bg = self.canvas.copy_from_bbox(self._ax.bbox)
            self._blit_ready = True
            return

        self.canvas.restore_region(self._bg)
        for sensor in self._sensors:
            self._ax.draw_artist(self._avg_lines[sensor])
            self._ax.draw_artist(self._lines[sensor])
        self.canvas.blit(self._ax.bbox)
        self.canvas.flush_events()

    def clear(self, sensor: str) -> None:
        self._history[sensor] = deque([0.0] * HISTORY, maxlen=HISTORY)
        self._avg_values[sensor] = 0.0
        self._avg_lines[sensor].set_ydata([0.0, 0.0])
        self._dirty = True
