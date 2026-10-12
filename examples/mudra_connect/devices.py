"""Device list UI and BLE scan/connect helpers."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from mudra_sdk.models.mudra_device import MudraDevice

from .anim import set_indicator
from .state import AppState
from .theme import (
    ACCENT,
    BG,
    BG_PANEL,
    BORDER,
    FG,
    FG_MUTED,
    FONT_DOT,
    FONT_HEADER,
    FONT_SMALL,
    FONT_UI_BOLD,
    OK,
    SELECT,
    WARN,
    px,
)
from .widgets import ScrollColumn


def build_device_list(parent: tk.Widget, state: AppState) -> tk.Frame:
    """Build scrollable device list; returns outer container."""
    outer = tk.Frame(parent, bg=BG_PANEL)

    header = tk.Label(
        outer,
        text="Devices",
        bg=BG_PANEL,
        fg=FG,
        font=FONT_HEADER,
        anchor="w",
    )
    header.pack(fill=tk.X, padx=px(8), pady=(px(8), px(4)))

    column = ScrollColumn(outer, bg=BG)
    column.outer.pack(fill=tk.BOTH, expand=True, padx=(px(8), 0), pady=(0, px(8)))
    state.devices_container = column.inner
    return outer


def device_list_width() -> int:
    """Starting width of the device pane: enough for a typical name, its
    transport tag and the address at this machine's font size."""
    bold = tkfont.nametofont(FONT_UI_BOLD)
    small = tkfont.nametofont(FONT_SMALL)
    return (
        bold.measure("Mudra Ultimate 00-00")
        + small.measure("  BLE  ")
        + tkfont.nametofont(FONT_DOT).measure("●  ")
        + px(56)  # card padding/border + scrollbar + outer margins
    )


def add_device_row(state: AppState, device: MudraDevice) -> None:
    container = state.devices_container
    if container is None or state.root is None or not state.root.winfo_exists():
        return
    if device.address in state.device_rows:
        return

    # Card: name + transport on line 1, address on line 2, and the action
    # button full-width on line 3 — so it's never pushed out of a narrow
    # column by a long name.
    row = tk.Frame(
        container,
        bg=BG_PANEL,
        highlightthickness=1,
        highlightbackground=BORDER,
        padx=px(6),
        pady=px(5),
    )
    row.pack(fill=tk.X, pady=(0, px(4)))
    row.columnconfigure(1, weight=1)

    status_dot = tk.Label(row, text="●", font=FONT_DOT, bg=BG_PANEL, fg=FG_MUTED)
    status_dot.grid(row=0, column=0, sticky="w", padx=(0, px(4)))

    name_label = tk.Label(
        row,
        text=device.name or device.address,
        font=FONT_UI_BOLD,
        bg=BG_PANEL,
        fg=FG,
        anchor="w",
    )
    name_label.grid(row=0, column=1, sticky="ew")

    transport_label = tk.Label(
        row,
        text=device.transport.upper(),
        font=FONT_SMALL,
        bg=BG_PANEL,
        fg=ACCENT,
        anchor="e",
    )
    transport_label.grid(row=0, column=2, sticky="e", padx=(px(4), 0))

    address_label = tk.Label(
        row,
        text=device.address,
        font=FONT_SMALL,
        bg=BG_PANEL,
        fg=FG_MUTED,
        anchor="w",
    )
    address_label.grid(row=1, column=1, columnspan=2, sticky="ew")

    action_btn = ttk.Button(
        row,
        text="Connect",
        command=lambda d=device: toggle_connection(state, d),
    )
    action_btn.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(px(4), 0))

    info = {
        "device": device,
        "row": row,
        "name_label": name_label,
        "status_dot": status_dot,
        "action_btn": action_btn,
        "bg_widgets": (row, status_dot, name_label, transport_label, address_label),
        "state": "idle",
    }
    state.device_rows[device.address] = info

    def _on_click(_event, d=device) -> None:
        select_device(state, d)

    for widget in info["bg_widgets"]:
        widget.bind("<Button-1>", _on_click)

    _refresh_idle_buttons(state)


def select_device(state: AppState, device: MudraDevice) -> None:
    state.selected_device = device
    for info in state.device_rows.values():
        bg = SELECT if info["device"] is device else BG_PANEL
        for widget in info["bg_widgets"]:
            widget.config(bg=bg)


def _refresh_idle_buttons(state: AppState) -> None:
    busy = any(
        info["state"] in ("connecting", "connected", "disconnecting")
        for info in state.device_rows.values()
    )
    for info in state.device_rows.values():
        if info["state"] == "idle":
            info["action_btn"].config(state="disabled" if busy else "normal")


def set_device_state(state: AppState, device: MudraDevice, device_state: str) -> None:
    info = state.device_rows.get(device.address)
    if info is None or state.root is None or not state.root.winfo_exists():
        return

    info["state"] = device_state
    btn = info["action_btn"]
    dot = info["status_dot"]

    if device_state == "idle":
        btn.config(text="Connect", state="normal")
        set_indicator(dot, FG_MUTED)
        if state.charts is not None:
            state.charts.clear()
    elif device_state == "connecting":
        btn.config(text="Connecting…", state="disabled")
        set_indicator(dot, WARN)
    elif device_state == "connected":
        btn.config(text="Disconnect", state="normal")
        set_indicator(dot, OK)
    elif device_state == "disconnecting":
        btn.config(text="Disconnecting…", state="disabled")
        set_indicator(dot, WARN)

    _refresh_idle_buttons(state)


def post_device_state(state: AppState, device: MudraDevice, device_state: str) -> None:
    assert state.post_ui is not None
    state.post_ui(lambda d=device, s=device_state: set_device_state(state, d, s))


def toggle_connection(state: AppState, device: MudraDevice) -> None:
    info = state.device_rows.get(device.address)
    device_state = info["state"] if info else "idle"
    select_device(state, device)
    assert state.bridge is not None
    state.bridge.ensure_running()

    if device_state == "idle":
        if state.set_status is not None:
            state.set_status(f"Connecting to {device.name or device.address}...")

        def _on_connect_error(msg: str) -> None:
            # Without this, bridge.submit()'s bare future would drop any
            # connect() exception silently and the row would hang on
            # "connecting" forever.
            post_device_state(state, device, "idle")
            if state.set_status is not None:
                assert state.post_ui is not None
                state.post_ui(lambda: state.set_status(msg))

        state.bridge.run(
            f"Connect to {device.name or device.address}",
            device.connect,
            on_error=_on_connect_error,
        )
    elif device_state == "connected":
        if state.set_status is not None:
            state.set_status(f"Disconnecting from {device.name or device.address}...")

        def _on_disconnect_error(msg: str) -> None:
            if state.set_status is not None:
                assert state.post_ui is not None
                state.post_ui(lambda: state.set_status(msg))

        state.bridge.run(
            f"Disconnect from {device.name or device.address}",
            device.disconnect,
            on_error=_on_disconnect_error,
        )


def update_devices_list(state: AppState, device: MudraDevice) -> None:
    key = device.address
    if key in state.device_rows:
        return
    state.devices_list.append(device)
    assert state.post_ui is not None
    state.post_ui(lambda d=device: add_device_row(state, d))


def _toggle_scan(state: AppState, transport: str) -> None:
    """Start/stop scanning on one transport ("ble" or "cdc"), toggling its
    own toolbar button independently of the other transport's scan."""
    assert state.bridge is not None
    state.bridge.ensure_running()
    label = "BLE" if transport == "ble" else "CDC"
    now_scanning = not (state.ble_scanning if transport == "ble" else state.cdc_scanning)

    if transport == "ble":
        state.ble_scanning = now_scanning
        btn = state.ble_scan_btn
    else:
        state.cdc_scanning = now_scanning
        btn = state.cdc_scan_btn
    if btn is not None:
        btn.config(text=f"Stop {label} Scan" if now_scanning else f"{label} Scan")

    if now_scanning:
        if state.set_status is not None:
            state.set_status(f"Scanning for {label} devices...")
        coro = state.mudra.scan_ble() if transport == "ble" else state.mudra.scan_cdc()
        state.bridge.submit(coro)
    else:
        if state.set_status is not None:
            state.set_status(f"Stopping {label} scan...")
        coro = state.mudra.stop_scan_ble() if transport == "ble" else state.mudra.stop_scan_cdc()
        state.bridge.submit(coro)
        assert state.post_ui is not None
        state.post_ui(lambda: state.set_status(f"{label} scan stopped"))


def toggle_scan_ble(state: AppState) -> None:
    _toggle_scan(state, "ble")


def toggle_scan_cdc(state: AppState) -> None:
    _toggle_scan(state, "cdc")


def find_connected_devices(state: AppState) -> None:
    assert state.bridge is not None
    state.bridge.ensure_running()
    if state.set_status is not None:
        state.set_status("Checking for already-connected devices...")

    async def _run() -> None:
        devices = await state.mudra.get_connected_devices()
        if state.post_ui is not None and state.set_status is not None:
            if devices:
                state.post_ui(
                    lambda: state.set_status(
                        f"Found {len(devices)} already-connected device(s)"
                    )
                )
            else:
                state.post_ui(
                    lambda: state.set_status("No already-connected devices found")
                )

    state.bridge.submit(_run())
