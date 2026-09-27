"""SD card recording panel."""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from ..state import AppState
from ..theme import BG_PANEL, FG_MUTED, FONT_SMALL, muted_label


def build_sd_recording_ui(parent: tk.Widget, state: AppState) -> None:
    """SD card recording — Set sensors/file/desc, Get State, next file #."""
    muted_label(
        parent,
        text="Logs to /SD:/REC_<file>.bin — optional desc is first text line",
        wraplength=420,
        justify=tk.LEFT,
    ).pack(anchor="w")
    muted_label(
        parent,
        text="Requires PRO tier license — Set fails with ERR_LICENSE on FREE/PLUS",
        wraplength=420,
        justify=tk.LEFT,
    ).pack(anchor="w")

    flags = tk.Frame(parent, bg=BG_PANEL)
    flags.pack(fill=tk.X, pady=(6, 0))
    for key, label in (
        ("emg", "EMG"),
        ("ppg", "PPG"),
        ("imu_h", "H_IMU"),
        ("imu_f", "F_IMU"),
    ):
        var = tk.BooleanVar(value=False)
        state.record_vars[key] = var
        ttk.Checkbutton(flags, text=label, variable=var).pack(side=tk.LEFT, padx=(0, 8))

    ttk.Separator(flags, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(4, 8))
    test_var = tk.BooleanVar(value=False)
    state.record_vars["is_test"] = test_var
    ttk.Checkbutton(flags, text="Test mode", variable=test_var).pack(side=tk.LEFT, padx=(0, 8))

    state.record_send_utc_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(flags, text="Send UTC timestamp", variable=state.record_send_utc_var).pack(side=tk.LEFT)
    muted_label(
        parent,
        text="Test mode: each recorded sensor's channel 0 becomes an incrementing counter (packet-loss analysis offline, no BLE needed)",
        wraplength=420,
        justify=tk.LEFT,
    ).pack(anchor="w", pady=(2, 0))
    muted_label(
        parent,
        text="Send UTC timestamp: sends this PC's current time (epoch seconds) at Set -- the device has no RTC of its own -- so the recording's meta line can show a real-world start time",
        wraplength=420,
        justify=tk.LEFT,
    ).pack(anchor="w", pady=(2, 0))

    muted_label(
        parent,
        text=(
            "Set requires a signed-in account (see the sign-in bar above) -- "
            "sign in before connecting, or reconnect after signing in. No "
            "separate step needed otherwise: connecting sends what the "
            "device needs automatically. Fails with ERR_STATE if skipped."
        ),
        wraplength=420,
        justify=tk.LEFT,
    ).pack(anchor="w", pady=(2, 0))

    file_row = tk.Frame(parent, bg=BG_PANEL)
    file_row.pack(fill=tk.X, pady=(6, 0))
    ttk.Label(file_row, text="File #", width=7, anchor="w").pack(side=tk.LEFT)
    state.record_file_var = tk.StringVar(value="0")
    ttk.Entry(file_row, textvariable=state.record_file_var, width=6).pack(side=tk.LEFT)
    ttk.Button(
        file_row,
        text="Next #",
        width=8,
        command=lambda: state.run_device(
            "STORAGE_NEXT_FILE_NUM?", lambda d: d.get_storage_next_file_num()
        ),
    ).pack(side=tk.LEFT, padx=(6, 0))

    duration_row = tk.Frame(parent, bg=BG_PANEL)
    duration_row.pack(fill=tk.X, pady=(6, 0))
    ttk.Label(duration_row, text="Duration", width=7, anchor="w").pack(side=tk.LEFT)
    state.record_duration_var = tk.StringVar(value="0")
    ttk.Entry(duration_row, textvariable=state.record_duration_var, width=6).pack(side=tk.LEFT)
    ttk.Label(duration_row, text="min (0 = record until Stop All)").pack(side=tk.LEFT, padx=(6, 0))

    desc_row = tk.Frame(parent, bg=BG_PANEL)
    desc_row.pack(fill=tk.X, pady=(6, 0))
    ttk.Label(desc_row, text="Desc", width=7, anchor="w").pack(side=tk.LEFT)
    state.record_desc_var = tk.StringVar(value="")
    ttk.Entry(desc_row, textvariable=state.record_desc_var).pack(
        side=tk.LEFT, fill=tk.X, expand=True
    )

    def _file_num() -> int:
        try:
            return max(0, min(255, int(state.record_file_var.get())))
        except (TypeError, ValueError):
            return 0

    def _duration_min() -> int:
        assert state.record_duration_var is not None
        try:
            return max(0, min(0xFFFF, int(state.record_duration_var.get())))
        except (TypeError, ValueError):
            return 0

    def _description() -> str:
        return (state.record_desc_var.get() or "").strip()

    def _set_record() -> None:
        async def _do(d) -> None:
            await d.set_storage_record(
                state.record_vars["emg"].get(),
                state.record_vars["ppg"].get(),
                state.record_vars["imu_h"].get(),
                state.record_vars["imu_f"].get(),
                file_num=_file_num(),
                duration_min=_duration_min(),
                utc_ts=int(time.time()) if state.record_send_utc_var.get() else 0,
                description=_description(),
                is_test=state.record_vars["is_test"].get(),
            )

        state.run_device("STORAGE_RECORD_SET", _do)

    def _stop_record() -> None:
        for var in state.record_vars.values():
            var.set(False)
        state.run_device(
            "STORAGE_RECORD_STOP",
            lambda d: d.set_storage_record(False, False, False, False, file_num=_file_num()),
        )

    btn_row = tk.Frame(parent, bg=BG_PANEL)
    btn_row.pack(fill=tk.X, pady=(8, 0))
    ttk.Button(btn_row, text="Set", width=8, command=_set_record).pack(side=tk.LEFT, padx=(0, 4))
    ttk.Button(btn_row, text="Stop All", width=10, command=_stop_record).pack(
        side=tk.LEFT, padx=(0, 4)
    )
    ttk.Button(
        btn_row,
        text="Get State",
        width=10,
        command=lambda: state.run_device(
            "STORAGE_RECORD_STATE?", lambda d: d.get_storage_record_state()
        ),
    ).pack(side=tk.LEFT)

    state.record_status_label = tk.Label(
        parent,
        text="—",
        font=FONT_SMALL,
        bg=BG_PANEL,
        fg=FG_MUTED,
        anchor="w",
    )
    state.record_status_label.pack(fill=tk.X, pady=(6, 0))
