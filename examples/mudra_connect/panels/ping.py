"""Ping / latency-check panel: enable a periodic PING and chart its round-trip delay.

The repeat timer and the send/receive timestamps live here at the app layer —
the SDK (``MudraDevice.ping()`` / ``on_ping_response``) only sends a single PING
and delivers a bare pong notification with no timing of its own.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import tkinter as tk
from tkinter import ttk

from mudra_sdk.logging_config import get_logger

from .config import build_sensor_config_ui
from ..sensors import toggle_sensor
from ..state import AppState
from ..theme import ACCENT, BG_PANEL, CHART_BG, FG_MUTED, FONT_SMALL, FONT_UI_BOLD, px
from ..widgets import ScrollColumn, fit_pane

logger = get_logger(__name__)

DEFAULT_PING_INTERVAL_S = 0.1
_PING_SENSORS = ("EMG", "IMU_H", "IMU_F", "PPG_H", "PPG_F")


def _make_ping_callback(state: AppState):
    def _on_ping_response() -> None:
        if state.ping_sent_at_iso is None:
            return
        sent_at = datetime.fromisoformat(state.ping_sent_at_iso)
        delay_ms = (datetime.now(timezone.utc) - sent_at).total_seconds() * 1000.0
        if state.ping_chart is not None:
            state.ping_chart.enqueue(delay_ms)
        if state.ping_status_label is not None and state.post_ui is not None:
            state.post_ui(
                lambda: state.ping_status_label.configure(
                    text=f"Last delay: {delay_ms:.1f} ms"
                )
            )

    return _on_ping_response


def _read_ping_interval(state: AppState) -> float:
    raw = state.ping_interval_var.get() if state.ping_interval_var is not None else None
    try:
        value = float(raw) if raw is not None else state.ping_interval_s
    except (TypeError, ValueError):
        value = state.ping_interval_s
    if value <= 0:
        value = DEFAULT_PING_INTERVAL_S
    state.ping_interval_s = value
    return value


async def _ping_loop(state: AppState, device) -> None:
    try:
        while True:
            state.ping_sent_at_iso = datetime.now(timezone.utc).isoformat()
            await device.ping()
            await asyncio.sleep(_read_ping_interval(state))
    except asyncio.CancelledError:
        pass


def start_ping_check(state: AppState) -> None:
    device = state.connected_device()
    if device is None:
        if state.set_status is not None:
            state.set_status("Connect a device before starting the ping check")
        return
    if state.ping_task is not None:
        return

    interval = _read_ping_interval(state)

    assert state.bridge is not None
    state.bridge.ensure_running()
    if state.ping_chart is not None:
        state.ping_chart.clear()

    async def _run() -> None:
        await device.set_on_ping_response(_make_ping_callback(state))
        state.ping_task = asyncio.create_task(_ping_loop(state, device))

    state.bridge.submit(_run())
    if state.set_status is not None:
        state.set_status(f"Ping check started ({interval:.3g} s interval)")
    logger.info(f"Ping check started on {device.name or device.address} ({interval:.3g} s)")


def stop_ping_check(state: AppState) -> None:
    device = state.connected_device()

    async def _run() -> None:
        if state.ping_task is not None:
            state.ping_task.cancel()
            state.ping_task = None
        if device is not None:
            await device.set_on_ping_response(None)
        state.ping_sent_at_iso = None

    assert state.bridge is not None
    state.bridge.submit(_run())
    if state.set_status is not None:
        state.set_status("Ping check stopped")
    if state.ping_status_label is not None:
        state.ping_status_label.configure(text="Not running")
    logger.info("Ping check stopped")


def build_ping_ui(parent: tk.Widget, state: AppState) -> None:
    header = tk.Frame(parent, bg=BG_PANEL)
    header.pack(fill=tk.X, padx=px(8), pady=(px(8), px(4)))

    tk.Label(
        header,
        text="Ping / Latency Check",
        bg=BG_PANEL,
        fg=ACCENT,
        font=FONT_UI_BOLD,
        anchor="w",
    ).pack(side=tk.LEFT)

    ttk.Button(
        header,
        text="Stop",
        command=lambda: stop_ping_check(state),
    ).pack(side=tk.RIGHT)
    ttk.Button(
        header,
        text="Start",
        style="Accent.TButton",
        command=lambda: start_ping_check(state),
    ).pack(side=tk.RIGHT, padx=(0, 4))

    interval_row = tk.Frame(header, bg=BG_PANEL)
    interval_row.pack(side=tk.RIGHT, padx=(0, 12))
    ttk.Label(interval_row, text="Interval s").pack(side=tk.LEFT, padx=(0, 4))
    state.ping_interval_var = tk.StringVar(value=str(DEFAULT_PING_INTERVAL_S))
    state.ping_interval_s = DEFAULT_PING_INTERVAL_S
    ttk.Entry(interval_row, textvariable=state.ping_interval_var, width=6).pack(
        side=tk.LEFT
    )

    # Sensor On/Off pairs on a grid (name over its two buttons) rather than
    # one long packed row, which ran off the right edge on larger fonts.
    sensors = tk.Frame(parent, bg=BG_PANEL)
    sensors.pack(fill=tk.X, padx=px(8), pady=(0, px(4)))
    tk.Label(
        sensors,
        text="Sensors",
        bg=BG_PANEL,
        fg=FG_MUTED,
        font=FONT_SMALL,
        anchor="w",
    ).grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, px(8)))
    for i, sensor in enumerate(_PING_SENSORS):
        col = 1 + i * 2
        ttk.Label(sensors, text=sensor).grid(
            row=0, column=col, columnspan=2, sticky="w", padx=(0, px(12))
        )
        ttk.Button(
            sensors,
            text="On",
            width=4,
            style="Small.TButton",
            command=lambda s=sensor: toggle_sensor(state, s, True),
        ).grid(row=1, column=col, sticky="w", padx=(0, px(2)))
        ttk.Button(
            sensors,
            text="Off",
            width=4,
            style="Small.TButton",
            command=lambda s=sensor: toggle_sensor(state, s, False),
        ).grid(row=1, column=col + 1, sticky="w", padx=(0, px(12)))

    state.ping_status_label = tk.Label(
        parent,
        text="Not running",
        bg=BG_PANEL,
        fg=FG_MUTED,
        font=FONT_SMALL,
        anchor="w",
    )
    state.ping_status_label.pack(fill=tk.X, padx=px(8))

    body = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
    body.pack(fill=tk.BOTH, expand=True, padx=px(4), pady=px(4))

    config_col = ScrollColumn(body, padx=px(4))
    body.add(config_col.outer, weight=0)
    tk.Label(
        config_col.inner,
        text="Sensor Config",
        bg=BG_PANEL,
        fg=ACCENT,
        font=FONT_UI_BOLD,
        anchor="w",
    ).pack(fill=tk.X, pady=(0, px(4)))
    config_box = tk.Frame(config_col.inner, bg=BG_PANEL)
    config_box.pack(fill=tk.X)
    build_sensor_config_ui(config_box, state)

    chart_wrap = tk.Frame(body, bg=CHART_BG)
    body.add(chart_wrap, weight=1)
    fit_pane(body, config_col.natural_width)

    from ..ping_chart import PingChart

    state.ping_chart = PingChart(chart_wrap)
