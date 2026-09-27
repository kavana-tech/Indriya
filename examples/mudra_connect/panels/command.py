"""Raw hex command panel."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from mudra_sdk.models.enums import ProFirmwareCommand, UltimateFirmwareCommand
from mudra_sdk.logging_config import get_logger

from ..state import AppState
from ..theme import BG_PANEL, muted_label

logger = get_logger(__name__)

_command_entry: ttk.Entry | None = None


def parse_hex_command(raw: str) -> bytes:
    """Parse hex input like '01 02 ff' or '0102ff' into bytes."""
    cleaned = raw.strip().replace(",", " ").replace("0x", " ").replace("0X", " ")
    if not cleaned:
        raise ValueError("Command is empty")

    parts = cleaned.split()
    if len(parts) == 1 and all(c in "0123456789abcdefABCDEF" for c in parts[0]):
        hex_str = parts[0]
        if len(hex_str) % 2 != 0:
            raise ValueError("Hex string must have an even number of digits")
        return bytes.fromhex(hex_str)

    return bytes(int(part, 16) for part in parts)


def send_command(state: AppState) -> None:
    if _command_entry is None:
        return

    device = state.connected_device()
    if device is None:
        if state.set_status is not None:
            state.set_status("Connect a device before sending a command")
        return

    raw = _command_entry.get()

    if device.transport == "cdc":
        # CDC's CONFIG port speaks ASCII, not binary hex frames — send the
        # entry text as a literal command line (e.g. "EMG_ODR?", "H_IMU?").
        text = raw.strip()
        if not text:
            if state.set_status is not None:
                state.set_status("Command is empty")
            return
        assert state.bridge is not None
        state.bridge.ensure_running()
        if state.set_status is not None:
            state.set_status(f"Sending: {text}")
        logger.info(f"Sending CDC command to {device.name or device.address}: {text}")
        state.bridge.submit(state.mudra.send_cdc_command(device, text))
        return

    try:
        command = parse_hex_command(raw)
    except ValueError as exc:
        if state.set_status is not None:
            state.set_status(f"Invalid command: {exc}")
        return

    assert state.bridge is not None
    state.bridge.ensure_running()
    if state.set_status is not None:
        state.set_status(f"Sending: {command.hex(' ')}")
    logger.info(f"Sending command to {device.name or device.address}: {command.hex(' ')}")
    state.bridge.submit(state.mudra.send_general_command(device, command))


def print_all_commands(state: AppState) -> None:
    """Dump every command's byte template for both hardware models —
    ProFirmwareCommand and UltimateFirmwareCommand are fully independent
    enums (not a shared table with a model switch), so this prints two
    separate sections rather than one side-by-side comparison."""
    total = 0
    for label, enum_cls in (("PRO", ProFirmwareCommand), ("ULTIMATE", UltimateFirmwareCommand)):
        logger.debug(f"=== {label} firmware commands ===")
        for cmd in enum_cls:
            logger.debug(f"{cmd.op_code:3d}  {cmd.description:<22}  {cmd.id.hex(' ')}")
        logger.debug(f"=== {len(enum_cls)} {label} commands ===")
        total += len(enum_cls)
    if state.set_status is not None:
        state.set_status(f"Printed {total} firmware commands to console")


def build_command_ui(parent: tk.Widget, state: AppState) -> None:
    global _command_entry

    muted_label(
        parent,
        text="Hex bytes (e.g. 01 02 FF or 0102FF)",
    ).pack(anchor="w")

    command_row = tk.Frame(parent, bg=BG_PANEL)
    command_row.pack(fill=tk.X, pady=(4, 0))
    _command_entry = ttk.Entry(command_row)
    _command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
    _command_entry.bind("<Return>", lambda _event: send_command(state))
    ttk.Button(command_row, text="Send", width=10, command=lambda: send_command(state)).pack(
        side=tk.RIGHT
    )

    ttk.Button(
        parent,
        text="Print All Commands",
        command=lambda: print_all_commands(state),
    ).pack(fill=tk.X, pady=(6, 0))
