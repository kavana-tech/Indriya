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
from ..theme import ACCENT, BG_PANEL, FG_MUTED, FONT_SMALL, FONT_UI_BOLD

logger = get_logger(__name__)

DEFAULT_PING_INTERVAL_S = 0.1
_PING_SENSORS = ("EMG", "IMU_H", "IMU_F", "PPG")


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
    header.pack(fill=tk.X, padx=8, pady=(8, 4))

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

    sensors = tk.Frame(parent, bg=BG_PANEL)
    sensors.pack(fill=tk.X, padx=8, pady=(0, 4))
    tk.Label(
        sensors,
        text="Sensors",
        bg=BG_PANEL,
        fg=FG_MUTED,
        font=FONT_SMALL,
        anchor="w",
    ).pack(side=tk.LEFT, padx=(0, 8))
    for sensor in _PING_SENSORS:
        block = tk.Frame(sensors, bg=BG_PANEL)
        block.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(block, text=sensor, width=6).pack(side=tk.LEFT)
        ttk.Button(
            block,
            text="On",
            width=4,
            command=lambda s=sensor: toggle_sensor(state, s, True),
        ).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(
            block,
            text="Off",
            width=4,
            command=lambda s=sensor: toggle_sensor(state, s, False),
        ).pack(side=tk.LEFT)

    state.ping_status_label = tk.Label(
        parent,
        text="Not running",
        bg=BG_PANEL,
        fg=FG_MUTED,
        font=FONT_SMALL,
        anchor="w",
    )
    state.ping_status_label.pack(fill=tk.X, padx=8)

    body = tk.Frame(parent, bg=BG_PANEL)
    body.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    config_wrap = tk.Frame(body, bg=BG_PANEL, width=360)
    config_wrap.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 4))
    config_wrap.pack_propagate(False)
    tk.Label(
        config_wrap,
        text="Sensor Config",
        bg=BG_PANEL,
        fg=ACCENT,
        font=FONT_UI_BOLD,
        anchor="w",
    ).pack(fill=tk.X, pady=(0, 4))
    config_box = tk.Frame(config_wrap, bg=BG_PANEL)
    config_box.pack(fill=tk.BOTH, expand=True)
    build_sensor_config_ui(config_box, state)

    chart_wrap = tk.Frame(body, bg="#101010")
    chart_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    from ..ping_chart import PingChart

    state.ping_chart = PingChart(chart_wrap)
