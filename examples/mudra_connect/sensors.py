"""Sensor stream toggles, status indicators, and combined explorer layout."""

from __future__ import annotations

from typing import Callable

import tkinter as tk
from tkinter import ttk

from mudra_sdk.models.mudra_device import MudraDevice
from mudra_sdk.logging_config import get_logger

from .panels.config import build_sensor_config_ui
from .state import AppState
from .theme import ACCENT, BG_PANEL, CHART_BG, FG_MUTED, FONT_DOT, FONT_SMALL, FONT_UI_BOLD, px
from .widgets import ScrollColumn, fit_pane

logger = get_logger(__name__)


def _make_sensor_callback(state: AppState, sensor_name: str) -> Callable:
    def _on_ready(
        timestamp: int,
        data: list[float],
        frequency: int,
        frequency_std: float,
    ) -> None:
        if state.charts is not None:
            state.charts.enqueue(sensor_name, data)

    return _on_ready


async def _set_sensor_enabled(
    state: AppState, device: MudraDevice, sensor: str, enabled: bool
) -> None:
    callback = _make_sensor_callback(state, sensor) if enabled else None
    if sensor == "EMG":
        await device.set_on_emg_ready(callback)
    elif sensor == "IMU_H":
        await device.set_on_imu_h_ready(callback)
    elif sensor == "IMU_F":
        await device.set_on_imu_f_ready(callback)
    elif sensor == "PPG_H":
        await device.set_on_ppg_h_ready(callback)
    elif sensor == "PPG_F":
        await device.set_on_ppg_f_ready(callback)
    else:
        raise ValueError(f"Unknown sensor: {sensor}")

    if not enabled and state.charts is not None:
        state.charts.clear(sensor)


def toggle_sensor(state: AppState, sensor: str, enabled: bool) -> None:
    device = state.connected_device()
    if device is None:
        if state.set_status is not None:
            state.set_status("Connect a device before toggling sensors")
        return

    assert state.bridge is not None
    state.bridge.ensure_running()

    action = "Enabling" if enabled else "Disabling"
    if state.set_status is not None:
        state.set_status(f"{action} {sensor}...")
    logger.info(f"{action} {sensor} on {device.name or device.address}")

    async def _run() -> None:
        try:
            await _set_sensor_enabled(state, device, sensor, enabled)
            label = "enabled" if enabled else "disabled"
            if state.post_ui is not None and state.set_status is not None:
                state.post_ui(lambda: state.set_status(f"{sensor} {label}"))
            logger.info(f"{sensor} {label}")
        except Exception as exc:  # noqa: BLE001
            if state.post_ui is not None and state.set_status is not None:
                # Bind exc now: it's deleted when the except block ends.
                state.post_ui(lambda e=exc: state.set_status(f"{sensor} toggle failed: {e}"))
            logger.error(f"{sensor} toggle failed: {exc}")

    state.bridge.submit(_run())


def _section_header(parent: tk.Widget, text: str) -> None:
    tk.Label(
        parent,
        text=text,
        bg=BG_PANEL,
        fg=ACCENT,
        font=FONT_UI_BOLD,
        anchor="w",
    ).pack(fill=tk.X, pady=(px(10), px(4)))


def _build_stream_toggles(parent: tk.Widget, state: AppState) -> None:
    from .charts import SPLITTABLE_SENSORS

    _section_header(parent, "Streams")
    # One grid for every sensor so the columns line up; the column hosting
    # this panel is sized from the grid's own requested width (see
    # build_streams_panel), so nothing here is ever clipped.
    grid = tk.Frame(parent, bg=BG_PANEL)
    grid.pack(fill=tk.X)
    grid.columnconfigure(1, weight=1)

    for i, sensor in enumerate(("EMG", "IMU_H", "IMU_F", "PPG_H", "PPG_F")):
        r = i * 2
        dot = tk.Label(grid, text="●", font=FONT_DOT, bg=BG_PANEL, fg=FG_MUTED)
        dot.grid(row=r, column=0, sticky="w", padx=(0, px(4)), pady=(px(4), 0))
        ttk.Label(grid, text=sensor).grid(row=r, column=1, sticky="w", pady=(px(4), 0))
        ttk.Button(
            grid,
            text="Enable",
            width=7,
            style="Small.TButton",
            command=lambda s=sensor: toggle_sensor(state, s, True),
        ).grid(row=r, column=2, sticky="ew", padx=(px(4), px(2)), pady=(px(4), 0))
        ttk.Button(
            grid,
            text="Disable",
            width=7,
            style="Small.TButton",
            command=lambda s=sensor: toggle_sensor(state, s, False),
        ).grid(row=r, column=3, sticky="ew", padx=(0, px(4)), pady=(px(4), 0))

        # Split-into-separate-charts toggle — PPG_H's and PPG_F's two groups
        # already carry one channel each (splitting would be a no-op), so it's omitted
        # there; charts.SPLITTABLE_SENSORS is the source of truth.
        if sensor in SPLITTABLE_SENSORS:
            split_var = tk.BooleanVar(value=False)

            def _on_split(s=sensor, var=split_var) -> None:
                if state.charts is not None:
                    state.charts.set_split(s, var.get())

            ttk.Checkbutton(
                grid, text="Split", variable=split_var, command=_on_split
            ).grid(row=r, column=4, sticky="w", pady=(px(4), 0))
            state.chart_split_vars[sensor] = split_var

        text = tk.Label(
            grid,
            text="—",
            font=FONT_SMALL,
            bg=BG_PANEL,
            fg=FG_MUTED,
            anchor="w",
            justify=tk.LEFT,
        )
        text.grid(row=r + 1, column=1, columnspan=4, sticky="ew")
        state.sensor_status_ui[sensor] = {"dot": dot, "text": text}


def build_streams_panel(parent: tk.Widget, state: AppState) -> None:
    """Streams + Sensor Config (scrollable left) and charts (right), split by a
    draggable sash. The left column starts exactly as wide as its content
    needs at this machine's fonts/DPI — never a fixed pixel width."""
    paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
    paned.pack(fill=tk.BOTH, expand=True)

    left = ScrollColumn(paned, padx=px(8), pady=px(4))
    paned.add(left.outer, weight=0)
    controls = left.inner

    _build_stream_toggles(controls, state)

    # Recording (SD card + PC-side JSON) lives in its own top-level
    # "Recording" tab (see recording_tab.py).
    _section_header(controls, "Sensor Config")
    config_box = tk.Frame(controls, bg=BG_PANEL)
    config_box.pack(fill=tk.X, pady=(0, px(8)))
    build_sensor_config_ui(config_box, state)

    # Scrollable — the chart figure's height grows with panel count (more
    # so once any sensor is split into per-channel charts; see
    # charts.SensorCharts.set_split/_rebuild_panels). The inner frame is
    # stretched to the column's width; matplotlib's own FigureCanvasTk
    # <Configure> binding then rescales the figure to match (see
    # charts.py's _current_fig_width_inches).
    charts_col = ScrollColumn(paned, bg=CHART_BG)
    paned.add(charts_col.outer, weight=1)

    from .charts import SensorCharts

    state.charts = SensorCharts(charts_col.inner, state=state)

    fit_pane(paned, left.natural_width)
