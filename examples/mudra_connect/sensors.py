"""Sensor stream toggles, status indicators, and combined explorer layout."""

from __future__ import annotations

from typing import Callable

import tkinter as tk
from tkinter import ttk

from mudra_sdk.models.mudra_device import MudraDevice
from mudra_sdk.logging_config import get_logger

from .panels.config import build_sensor_config_ui
from .state import AppState
from .theme import ACCENT, BG_PANEL, FG_MUTED, FONT_SMALL, FONT_UI_BOLD

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
    elif sensor == "PPG":
        await device.set_on_ppg_ready(callback)
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
                state.post_ui(lambda: state.set_status(f"{sensor} toggle failed: {exc}"))
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
    ).pack(fill=tk.X, pady=(10, 4))


def _build_stream_toggles(parent: tk.Widget, state: AppState) -> None:
    from .charts import SPLITTABLE_SENSORS

    _section_header(parent, "Streams")
    for sensor in ("EMG", "IMU_H", "IMU_F", "PPG"):
        block = tk.Frame(parent, bg=BG_PANEL)
        block.pack(fill=tk.X, pady=3)

        row = tk.Frame(block, bg=BG_PANEL)
        row.pack(fill=tk.X)
        dot = tk.Label(
            row,
            text="●",
            font=("Segoe UI", 11),
            bg=BG_PANEL,
            fg=FG_MUTED,
            width=2,
        )
        dot.pack(side=tk.LEFT)
        ttk.Label(row, text=sensor, width=7).pack(side=tk.LEFT)
        ttk.Button(
            row,
            text="Enable",
            width=8,
            command=lambda s=sensor: toggle_sensor(state, s, True),
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(
            row,
            text="Disable",
            width=8,
            command=lambda s=sensor: toggle_sensor(state, s, False),
        ).pack(side=tk.LEFT)

        # Split-into-separate-charts toggle — PPG's two groups already carry
        # one channel each (splitting would be a no-op), so it's omitted
        # there; charts.SPLITTABLE_SENSORS is the source of truth.
        if sensor in SPLITTABLE_SENSORS:
            split_var = tk.BooleanVar(value=False)

            def _on_split(s=sensor, var=split_var) -> None:
                if state.charts is not None:
                    state.charts.set_split(s, var.get())

            ttk.Checkbutton(
                row, text="Split", variable=split_var, command=_on_split
            ).pack(side=tk.LEFT, padx=(6, 0))
            state.chart_split_vars[sensor] = split_var

        text = tk.Label(
            block,
            text="—",
            font=FONT_SMALL,
            bg=BG_PANEL,
            fg=FG_MUTED,
            anchor="w",
        )
        text.pack(fill=tk.X, padx=(22, 0))
        state.sensor_status_ui[sensor] = {"dot": dot, "text": text}


def build_streams_panel(parent: tk.Widget, state: AppState) -> None:
    """Streams + Recording + Config (scrollable left) and charts (right)."""
    outer = tk.Frame(parent, bg=BG_PANEL)
    outer.pack(fill=tk.BOTH, expand=True)

    left_wrap = tk.Frame(outer, bg=BG_PANEL, width=360)
    left_wrap.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 4), pady=4)
    left_wrap.pack_propagate(False)

    canvas = tk.Canvas(left_wrap, highlightthickness=0, bg=BG_PANEL)
    scroll = ttk.Scrollbar(left_wrap, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    controls = tk.Frame(canvas, bg=BG_PANEL, padx=6, pady=4)
    win_id = canvas.create_window((0, 0), window=controls, anchor="nw")

    def _sync(_event=None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))
        if canvas.winfo_width() > 1:
            canvas.itemconfig(win_id, width=canvas.winfo_width())

    controls.bind("<Configure>", _sync)
    canvas.bind(
        "<Configure>",
        lambda e: canvas.itemconfig(win_id, width=e.width) if e.width > 1 else None,
    )

    def _wheel(event) -> None:
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind("<MouseWheel>", _wheel)
    controls.bind("<MouseWheel>", _wheel)

    _build_stream_toggles(controls, state)

    # Recording (SD card + PC-side JSON) lives in its own top-level
    # "Recording" tab now (see recording_tab.py) — it was competing with
    # Streams/Sensor Config for this narrow scrollable column and pushing
    # Sensor Config far down.
    _section_header(controls, "Sensor Config")
    config_box = tk.Frame(controls, bg=BG_PANEL)
    config_box.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
    build_sensor_config_ui(config_box, state)

    charts_wrap = tk.Frame(outer, bg="#101010")
    charts_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Scrollable — the chart figure's height grows with panel count (more
    # so once any sensor is split into per-channel charts; see
    # charts.SensorCharts.set_split/_rebuild_panels), and previously had no
    # way to reach panels that didn't fit the window (PPG, being last, was
    # the first to go off-screen). Same canvas+scrollbar+<Configure> pattern
    # already used for the left `controls` column above.
    chart_canvas = tk.Canvas(charts_wrap, highlightthickness=0, bg="#101010")
    chart_scroll = ttk.Scrollbar(charts_wrap, orient=tk.VERTICAL, command=chart_canvas.yview)
    chart_canvas.configure(yscrollcommand=chart_scroll.set)
    chart_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    chart_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    from .charts import SensorCharts

    charts_frame = tk.Frame(chart_canvas, bg="#101010")
    charts_win_id = chart_canvas.create_window((0, 0), window=charts_frame, anchor="nw")

    # Stretch charts_frame's WIDTH to chart_canvas's width (only the vertical
    # scrollregion was synced before — the figure just sat at its fixed
    # _FIGURE_WIDTH_INCHES regardless of how wide the window actually was).
    # Once the Tk widget itself is actually resized, matplotlib's own
    # FigureCanvasTk <Configure> binding takes it from there and rescales the
    # figure to match (see charts.py's _current_fig_width_inches). Same
    # dual-binding pattern as the left `controls` column above.
    def _sync_charts(_event=None) -> None:
        chart_canvas.configure(scrollregion=chart_canvas.bbox("all"))
        if chart_canvas.winfo_width() > 1:
            chart_canvas.itemconfig(charts_win_id, width=chart_canvas.winfo_width())

    charts_frame.bind("<Configure>", _sync_charts)
    chart_canvas.bind(
        "<Configure>",
        lambda e: chart_canvas.itemconfig(charts_win_id, width=e.width) if e.width > 1 else None,
    )

    def _wheel_charts(event) -> None:
        chart_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    chart_canvas.bind("<MouseWheel>", _wheel_charts)
    charts_frame.bind("<MouseWheel>", _wheel_charts)

    state.charts = SensorCharts(charts_frame, state=state)
