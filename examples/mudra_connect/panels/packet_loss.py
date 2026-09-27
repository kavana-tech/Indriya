"""Packet-loss test panel.

The counter-loss detection itself is entirely native (see
``ComputationManager::GetPacketLossStats``/``ResetPacketLossStats``, backed
by ``PacketLossStats`` in ``core/Computation/CommonTypes.h``) and runs off
the raw byte stream regardless of whether anything is listening for it —
completely independent of the sensor's normal "ready" data path
(``set_on_*_ready``, used by the Explorer tab). This panel only drives:

  1. Apply the chosen ODR.
  2. Enable test mode — one firmware command that both resets the counter
     AND starts the sensor (``set_*_test_mode(True)``); no ready-callback
     needed to make it stream.

Then ``tick()`` (called once per app refresh) polls the windowed loss %
for whichever sensors are running and updates the label + shared chart
cache — a plain poll, not a push callback, since the native counting
doesn't need one to keep working.
"""

from __future__ import annotations

import asyncio
import tkinter as tk
from tkinter import ttk

from mudra_sdk.models.enums import ProEMGODR, IMUODR, PPGODR
from mudra_sdk.models.mudra_pro import MudraPro

from ..state import AppState
from ..theme import ACCENT, BG_PANEL, ERR, FG_MUTED, FONT_SMALL, FONT_UI_BOLD, OK, WARN
from ..widgets import combo

SENSORS = ("EMG", "IMU_H", "IMU_F", "PPG")

_SENSOR_LABELS = {
    "EMG": "EMG",
    "IMU_H": "IMU hand",
    "IMU_F": "IMU ring",
    "PPG": "PPG",
}

# EMG uses ProEMGODR specifically (not a generic EMGODR) because this whole
# panel is Pro-only (packet-loss test mode doesn't exist on Ultimate — see
# the isinstance(device, MudraPro) guard in start_test/stop_test below).
_ODR_ENUM = {
    "EMG": ProEMGODR,
    "IMU_H": IMUODR,
    "IMU_F": IMUODR,
    "PPG": PPGODR,
}

_ODR_VALUES = {
    "EMG": [e.value_int for e in ProEMGODR],
    "IMU_H": [e.value_int for e in IMUODR],
    "IMU_F": [e.value_int for e in IMUODR],
    "PPG": [e.value_int for e in PPGODR],
}

_ODR_DEFAULT = {
    "EMG": ProEMGODR.emgOdr800.value_int,
    "IMU_H": IMUODR.imuHOdr100.value_int,
    "IMU_F": IMUODR.imuHOdr100.value_int,
    "PPG": PPGODR.ppgOdr100.value_int,
}

# Escalating alert tiers for the current (last ~1s) loss %, checked highest
# first. Two colors (WARN/ERR) each cover two tiers, distinguished by font
# weight — no new theme colors needed.
_ALERT_TIERS = (
    (20.0, "≥ 20%", ERR, FONT_UI_BOLD),
    (15.0, "≥ 15%", ERR, FONT_SMALL),
    (10.0, "≥ 10%", WARN, FONT_UI_BOLD),
    (5.0, "≥ 5%", WARN, FONT_SMALL),
)
_ALERT_IDLE = ("—", FG_MUTED, FONT_SMALL)
_ALERT_OK = ("OK", OK, FONT_SMALL)


def _alert_for(pct: float):
    for threshold, text, color, font in _ALERT_TIERS:
        if pct >= threshold:
            return text, color, font
    return _ALERT_OK


def _test_mode_setter(device, sensor: str):
    """Only exists on MudraPro (packet-loss test mode is a Pro-only firmware
    feature) — callers must check isinstance(device, MudraPro) first, since
    building this dict touches all four attributes regardless of `sensor`."""
    return {
        "EMG": device.set_emg_test_mode,
        "IMU_H": device.set_h_imu_test_mode,
        "IMU_F": device.set_f_imu_test_mode,
        "PPG": device.set_ppg_test_mode,
    }[sensor]


def _odr_setter(device, sensor: str):
    return {
        "EMG": device.set_emg_odr,
        "IMU_H": device.set_h_imu_odr,
        "IMU_F": device.set_f_imu_odr,
        "PPG": device.set_ppg_odr,
    }[sensor]


def _sample_getter(device, sensor: str):
    return {
        "EMG": device.sample_emg_packet_loss,
        "IMU_H": device.sample_h_imu_packet_loss,
        "IMU_F": device.sample_f_imu_packet_loss,
        "PPG": device.sample_ppg_packet_loss,
    }[sensor]


def _stats_getter(device, sensor: str):
    return {
        "EMG": device.get_emg_packet_loss_stats,
        "IMU_H": device.get_h_imu_packet_loss_stats,
        "IMU_F": device.get_f_imu_packet_loss_stats,
        "PPG": device.get_ppg_packet_loss_stats,
    }[sensor]


def _rate_hz_getter(device, sensor: str):
    return {
        "EMG": device.get_emg_packet_loss_rate_hz,
        "IMU_H": device.get_h_imu_packet_loss_rate_hz,
        "IMU_F": device.get_f_imu_packet_loss_rate_hz,
        "PPG": device.get_ppg_packet_loss_rate_hz,
    }[sensor]


def _window_resetter(device, sensor: str):
    return {
        "EMG": device.reset_emg_packet_loss_window,
        "IMU_H": device.reset_h_imu_packet_loss_window,
        "IMU_F": device.reset_f_imu_packet_loss_window,
        "PPG": device.reset_ppg_packet_loss_window,
    }[sensor]


def _format_stats(sensor: str, rate_hz: float, total: int, samples_lost: int, overall_pct: float, windowed_pct: float) -> str:
    return (
        f"{_SENSOR_LABELS[sensor]} — {rate_hz:.1f} Hz | samples: {total}, "
        f"lost: {samples_lost} ({overall_pct:.2f}% overall, "
        f"{windowed_pct:.2f}% last ~1s)"
    )


def tick(state: AppState) -> None:
    """Call once per app refresh tick. Polls the windowed loss % for every
    currently-running sensor test and updates its label, alert badge, and
    the shared chart caches — a plain poll, not a push callback, since the
    native counting doesn't need one to keep working."""
    device = state.connected_device()
    if device is None:
        return
    for sensor in SENSORS:
        if not state.packet_loss_active.get(sensor):
            continue
        windowed_pct = _sample_getter(device, sensor)()
        state.packet_loss_pct_by_sensor[sensor] = windowed_pct

        samples_seen, samples_lost = _stats_getter(device, sensor)()
        total = samples_seen + samples_lost
        overall_pct = (100.0 * samples_lost / total) if total else 0.0

        rate_hz = _rate_hz_getter(device, sensor)()
        label = state.packet_loss_labels.get(sensor)
        if label is not None:
            label.configure(
                text=_format_stats(sensor, rate_hz, total, samples_lost, overall_pct, windowed_pct)
            )

        alert_label = state.packet_loss_alert_labels.get(sensor)
        if alert_label is not None:
            text, color, font = _alert_for(windowed_pct)
            alert_label.configure(text=text, fg=color, font=font)


def _apply_odr(state: AppState, sensor: str) -> None:
    """Apply the ODR combo's value immediately on selection -- same
    apply-on-change pattern as every other ODR combo in the app now, instead
    of only being read implicitly when Start is pressed. Harmless either
    way: Start re-reads and re-applies it regardless, and firmware's
    config-while-running guard rejects this with ERR_BUSY (surfaced via the
    command-error callback) if the test is currently active for this
    sensor -- same as pressing Start mid-test would."""
    combo_widget = state.packet_loss_odr_combos.get(sensor)
    if combo_widget is None:
        return
    odr = _ODR_ENUM[sensor].from_value(int(combo_widget.get()))
    if odr is None:
        return
    state.run_device(f"{sensor}_ODR", lambda d: _odr_setter(d, sensor)(odr))


def start_test(state: AppState, sensor: str) -> None:
    device = state.connected_device()
    if device is None:
        if state.set_status is not None:
            state.set_status("Connect a device before starting the packet-loss test")
        return
    if not isinstance(device, MudraPro):
        if state.set_status is not None:
            state.set_status("Packet-loss test mode is Pro-only (not available on Ultimate)")
        return
    if state.packet_loss_active.get(sensor):
        return

    combo_widget = state.packet_loss_odr_combos.get(sensor)
    odr_value = int(combo_widget.get()) if combo_widget is not None else _ODR_DEFAULT[sensor]
    odr = _ODR_ENUM[sensor].from_value(odr_value)

    if state.packet_loss_chart is not None:
        state.packet_loss_chart.clear(sensor)
    state.packet_loss_active[sensor] = True

    assert state.bridge is not None
    state.bridge.ensure_running()

    async def _run() -> None:
        if odr is not None:
            await _odr_setter(device, sensor)(odr)
        # One command: resets the native counters, replaces channel 0 with
        # the incrementing counter, AND starts the sensor (firmware-side).
        await _test_mode_setter(device, sensor)(True)

    state.bridge.submit(_run())
    if state.set_status is not None:
        state.set_status(f"Packet-loss test started: {_SENSOR_LABELS[sensor]}")
    label = state.packet_loss_labels.get(sensor)
    if label is not None:
        label.configure(text=f"{_SENSOR_LABELS[sensor]} — running...")
    alert_label = state.packet_loss_alert_labels.get(sensor)
    if alert_label is not None:
        text, color, font = _ALERT_OK
        alert_label.configure(text=text, fg=color, font=font)


def stop_test(state: AppState, sensor: str) -> None:
    device = state.connected_device()
    state.packet_loss_active[sensor] = False

    if device is not None:
        _window_resetter(device, sensor)()
    state.packet_loss_pct_by_sensor[sensor] = 0.0
    if state.packet_loss_chart is not None:
        state.packet_loss_chart.clear(sensor)
    label = state.packet_loss_labels.get(sensor)
    if label is not None:
        label.configure(text=f"{_SENSOR_LABELS[sensor]} — not running")
    alert_label = state.packet_loss_alert_labels.get(sensor)
    if alert_label is not None:
        text, color, font = _ALERT_IDLE
        alert_label.configure(text=text, fg=color, font=font)

    async def _run() -> None:
        if device is not None and isinstance(device, MudraPro):
            # One command: stops the sensor AND clears test mode.
            await _test_mode_setter(device, sensor)(False)

    assert state.bridge is not None
    state.bridge.submit(_run())
    if state.set_status is not None:
        state.set_status(f"Packet-loss test stopped: {_SENSOR_LABELS[sensor]}")


def build_packet_loss_ui(parent: tk.Widget, state: AppState) -> None:
    tk.Label(
        parent,
        text="Packet-Loss Test",
        bg=BG_PANEL,
        fg=ACCENT,
        font=FONT_UI_BOLD,
        anchor="w",
    ).pack(fill=tk.X, padx=8, pady=(8, 4))

    tk.Label(
        parent,
        text=(
            "Replaces each sensor's channel 0 with a firmware-side incrementing "
            "counter. Any gap in the counter as it arrives here means samples "
            "were dropped in transit (not a firmware bug). The dashed line on "
            "the chart marks each sensor's current (last ~1s) loss level; "
            "the badge next to its ODR flags the same value against "
            "escalating tiers: OK under 5%, then 5/10/15/20%."
        ),
        bg=BG_PANEL,
        fg=FG_MUTED,
        font=FONT_SMALL,
        anchor="w",
        justify=tk.LEFT,
        wraplength=520,
    ).pack(fill=tk.X, padx=8, pady=(0, 8))

    for sensor in SENSORS:
        state.packet_loss_active.setdefault(sensor, False)

        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill=tk.X, padx=8, pady=4)

        header = tk.Frame(row, bg=BG_PANEL)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text=_SENSOR_LABELS[sensor],
            width=10,
            bg=BG_PANEL,
            fg="#dddddd",
            font=FONT_SMALL,
            anchor="w",
        ).pack(side=tk.LEFT)

        ttk.Label(header, text="ODR Hz", width=7, anchor="w").pack(side=tk.LEFT, padx=(4, 2))
        odr_combo = combo(header, _ODR_VALUES[sensor], _ODR_DEFAULT[sensor], width=6)
        odr_combo.pack(side=tk.LEFT, padx=(0, 8))
        odr_combo.bind(
            "<<ComboboxSelected>>", lambda _evt, s=sensor: _apply_odr(state, s)
        )
        state.packet_loss_odr_combos[sensor] = odr_combo

        alert_label = tk.Label(
            header,
            text=_ALERT_IDLE[0],
            width=6,
            bg=BG_PANEL,
            fg=_ALERT_IDLE[1],
            font=_ALERT_IDLE[2],
            anchor="center",
        )
        alert_label.pack(side=tk.LEFT, padx=(0, 8))
        state.packet_loss_alert_labels[sensor] = alert_label

        ttk.Button(
            header,
            text="Stop",
            width=8,
            command=lambda s=sensor: stop_test(state, s),
        ).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(
            header,
            text="Start",
            width=8,
            command=lambda s=sensor: start_test(state, s),
        ).pack(side=tk.RIGHT)

        label = tk.Label(
            row,
            text=f"{_SENSOR_LABELS[sensor]} — not running",
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=FONT_SMALL,
            anchor="w",
        )
        label.pack(fill=tk.X, padx=(10, 0))
        state.packet_loss_labels[sensor] = label

    chart_wrap = tk.Frame(parent, bg="#101010")
    chart_wrap.pack(fill=tk.BOTH, expand=True, padx=4, pady=(8, 4))

    from ..packet_loss_chart import PacketLossChart

    state.packet_loss_chart = PacketLossChart(chart_wrap, list(SENSORS))
