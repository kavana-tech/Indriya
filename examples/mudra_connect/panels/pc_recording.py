"""PC-side JSON recording panel — exercises MudraDevice.start_recording /
stop_recording / get_json_recording (DataRecorder), as opposed to the
firmware's onboard SD card recording (panels/recording.py)."""

from __future__ import annotations

import json
from tkinter import filedialog
from typing import List

import tkinter as tk
from tkinter import ttk

from mudra_sdk.models.enums import RecordingDataType

from ..state import AppState
from ..theme import BG_PANEL, FG_MUTED, FONT_SMALL, muted_label

# Which RecordingDataType members each sensor checkbox turns on. Hand and
# Finger IMU are recorded independently (data.acc/gyro vs data.acc_f/gyro_f).
_SENSOR_RECORDING_TYPES = {
    "EMG": [RecordingDataType.emg1, RecordingDataType.emg2, RecordingDataType.emg3, RecordingDataType.emgTS],
    "IMU_H": [
        RecordingDataType.acc1, RecordingDataType.acc2, RecordingDataType.acc3, RecordingDataType.accTS,
        RecordingDataType.gyro1, RecordingDataType.gyro2, RecordingDataType.gyro3, RecordingDataType.gyroTS,
    ],
    "IMU_F": [
        RecordingDataType.accF1, RecordingDataType.accF2, RecordingDataType.accF3, RecordingDataType.accFTS,
        RecordingDataType.gyroF1, RecordingDataType.gyroF2, RecordingDataType.gyroF3, RecordingDataType.gyroFTS,
    ],
    "PPG": [
        RecordingDataType.ppg1, RecordingDataType.ppg2, RecordingDataType.ppg3, RecordingDataType.ppg4,
        RecordingDataType.ppgTS,
    ],
}


def _set_status(state: AppState, text: str) -> None:
    if state.pc_record_status_label is not None:
        state.pc_record_status_label.config(text=text)
    if state.set_status is not None:
        state.set_status(text)


def _start_recording(state: AppState) -> None:
    selected = [sensor for sensor, var in state.pc_record_vars.items() if var.get()]
    if not selected:
        _set_status(state, "Select at least one sensor to record")
        return

    recording_types: List[RecordingDataType] = []
    for sensor in selected:
        recording_types.extend(_SENSOR_RECORDING_TYPES[sensor])

    _set_status(state, f"Starting PC recording ({', '.join(selected)})...")

    state.run_device(
        "START_RECORDING",
        lambda d: d.start_recording(recording_types),
    )


def _stop_recording(state: AppState) -> None:
    _set_status(state, "Stopping PC recording...")
    state.run_device("STOP_RECORDING", lambda d: d.stop_recording())


def _save_json(state: AppState) -> None:
    device = state.connected_device()
    if device is None:
        _set_status(state, "Connect a device before saving")
        return

    json_str = device.get_json_recording()
    if not json_str:
        _set_status(state, "No recording JSON available yet — start/stop a recording first")
        return

    path = filedialog.asksaveasfilename(
        title="Save recording JSON",
        defaultextension=".json",
        filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        initialfile="mudra_recording.json",
    )
    if not path:
        return

    with open(path, "w", encoding="utf-8") as f:
        f.write(json_str)

    groups = "?"
    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            groups = ", ".join(sorted(data.keys())) or "(empty)"
    except (ValueError, AttributeError):
        pass

    _set_status(state, f"Saved {len(json_str)} bytes to {path} — data: {groups}")


def build_pc_recording_ui(parent: tk.Widget, state: AppState) -> None:
    """PC-side JSON recording — Start/Stop capture EMG/IMU/PPG samples into
    an in-memory DataRecorder session; Save JSON writes GetJsonRecording()'s
    output to a local file."""
    muted_label(
        parent,
        text="Records live sample data into JSON (data.emg/acc/gyro/acc_f/gyro_f/ppg).",
        wraplength=420,
        justify=tk.LEFT,
    ).pack(anchor="w")

    flags = tk.Frame(parent, bg=BG_PANEL)
    flags.pack(fill=tk.X, pady=(6, 0))
    for key, label in (
        ("EMG", "EMG"),
        ("IMU_H", "H_IMU"),
        ("IMU_F", "F_IMU"),
        ("PPG", "PPG"),
    ):
        var = tk.BooleanVar(value=False)
        state.pc_record_vars[key] = var
        ttk.Checkbutton(flags, text=label, variable=var).pack(side=tk.LEFT, padx=(0, 8))

    btn_row = tk.Frame(parent, bg=BG_PANEL)
    btn_row.pack(fill=tk.X, pady=(8, 0))
    ttk.Button(
        btn_row, text="Start Recording", width=14, command=lambda: _start_recording(state)
    ).pack(side=tk.LEFT, padx=(0, 4))
    ttk.Button(
        btn_row, text="Stop Recording", width=14, command=lambda: _stop_recording(state)
    ).pack(side=tk.LEFT, padx=(0, 4))
    ttk.Button(
        btn_row, text="Save JSON...", width=12, command=lambda: _save_json(state)
    ).pack(side=tk.LEFT)

    state.pc_record_status_label = tk.Label(
        parent,
        text="—",
        font=FONT_SMALL,
        bg=BG_PANEL,
        fg=FG_MUTED,
        anchor="w",
        wraplength=420,
        justify=tk.LEFT,
    )
    state.pc_record_status_label.pack(fill=tk.X, pady=(6, 0))
