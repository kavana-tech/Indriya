"""Firmware update (DFU) panel — upload a signed image over the device's
USB-CDC SMP port (see mudra_sdk/service/dfu_service.py).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk

from ..state import AppState
from ..theme import ACCENT, BG_PANEL, ERR, FG_MUTED, FONT_SMALL, FONT_UI_BOLD, OK, muted_label

_STAGE_TEXT = {
    "connect": "Connecting to SMP port...",
    "upload": "Uploading image...",
    "mark": "Marking image for boot...",
    "reset": "Resetting device...",
    "done": "Update staged — device is rebooting",
}


def _pick_firmware(state: AppState) -> None:
    path = filedialog.askopenfilename(
        title="Select firmware image (.bin)",
        filetypes=[("Firmware image", "*.bin"), ("All files", "*.*")],
    )
    if path:
        state.dfu_file_var.set(path)


def _set_status(state: AppState, text: str, color: str = FG_MUTED) -> None:
    if state.dfu_status_label is None or state.post_ui is None:
        return
    state.post_ui(lambda: state.dfu_status_label.configure(text=text, fg=color))


def _set_progress(state: AppState, offset: int, total: int) -> None:
    if state.dfu_progress is None or state.post_ui is None:
        return
    pct = (offset / total * 100.0) if total else 0.0
    state.post_ui(lambda: state.dfu_progress.configure(value=pct))


def _start_update(state: AppState) -> None:
    device = state.connected_device()
    if device is None:
        if state.set_status is not None:
            state.set_status("Connect a device before starting a firmware update")
        return

    path = (state.dfu_file_var.get() or "").strip()
    if not path:
        _set_status(state, "Select a firmware .bin file first", ERR)
        return

    if state.dfu_busy:
        return
    state.dfu_busy = True
    _set_progress(state, 0, 1)
    _set_status(state, "Looking for the device's SMP port...")

    def on_stage(stage: str) -> None:
        _set_status(state, _STAGE_TEXT.get(stage, stage))

    def on_progress(offset: int, total: int) -> None:
        _set_progress(state, offset, total)

    async def _run() -> None:
        try:
            version = await device.start_dfu(path, on_progress=on_progress, on_stage=on_stage)
            _set_progress(state, 1, 1)
            _set_status(state, f"Staged firmware v{version} — device is rebooting", OK)
        except Exception as exc:  # noqa: BLE001
            _set_status(state, f"Firmware update failed: {exc}", ERR)
        finally:
            state.dfu_busy = False

    assert state.bridge is not None
    state.bridge.submit(_run())


def build_dfu_ui(parent: tk.Widget, state: AppState) -> None:
    header = tk.Frame(parent, bg=BG_PANEL)
    header.pack(fill=tk.X, padx=8, pady=(8, 4))
    tk.Label(
        header,
        text="Firmware Update (DFU)",
        bg=BG_PANEL,
        fg=ACCENT,
        font=FONT_UI_BOLD,
        anchor="w",
    ).pack(side=tk.LEFT)

    muted_label(
        parent,
        text=(
            "Uploads a signed firmware image (app_flpr.signed.bin) over the "
            "device's USB-CDC SMP port via MCUmgr — USB (CDC) only, requires "
            "DFU-enabled firmware already running on the device."
        ),
    ).pack(anchor="w", padx=8)

    file_row = tk.Frame(parent, bg=BG_PANEL)
    file_row.pack(fill=tk.X, padx=8, pady=(8, 0))
    ttk.Label(file_row, text="Firmware", width=9, anchor="w").pack(side=tk.LEFT)
    state.dfu_file_var = tk.StringVar(value="")
    ttk.Entry(file_row, textvariable=state.dfu_file_var).pack(
        side=tk.LEFT, fill=tk.X, expand=True
    )
    ttk.Button(file_row, text="Browse...", command=lambda: _pick_firmware(state)).pack(
        side=tk.LEFT, padx=(6, 0)
    )

    btn_row = tk.Frame(parent, bg=BG_PANEL)
    btn_row.pack(fill=tk.X, padx=8, pady=(8, 0))
    ttk.Button(
        btn_row,
        text="Start Update",
        style="Accent.TButton",
        command=lambda: _start_update(state),
    ).pack(side=tk.LEFT)

    state.dfu_progress = ttk.Progressbar(parent, mode="determinate", maximum=100)
    state.dfu_progress.pack(fill=tk.X, padx=8, pady=(10, 4))

    state.dfu_status_label = tk.Label(
        parent,
        text="Idle",
        bg=BG_PANEL,
        fg=FG_MUTED,
        font=FONT_SMALL,
        anchor="w",
    )
    state.dfu_status_label.pack(fill=tk.X, padx=8)
