"""Device list UI and BLE scan/connect helpers."""

from __future__ import annotations

import platform

import tkinter as tk
from tkinter import ttk

from mudra_sdk.models.mudra_device import MudraDevice

from .anim import set_indicator
from .state import AppState
from .theme import BG, BG_PANEL, BORDER, FG, FG_MUTED, OK, SELECT, WARN


def build_device_list(parent: tk.Widget, state: AppState) -> tk.Frame:
    """Build scrollable device list; returns outer container."""
    outer = tk.Frame(parent, bg=BG_PANEL)
    outer.pack(fill=tk.BOTH, expand=True)

    header = tk.Label(
        outer,
        text="Devices",
        bg=BG_PANEL,
        fg=FG,
        font=("Segoe UI", 10, "bold"),
        anchor="w",
    )
    header.pack(fill=tk.X, padx=8, pady=(8, 4))

    canvas = tk.Canvas(outer, highlightthickness=0, bg=BG, height=200)
    scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=(0, 8))
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=(0, 8))

    container = tk.Frame(canvas, bg=BG)
    window_id = canvas.create_window((0, 0), window=container, anchor="nw")
    state.devices_container = container

    def _on_configure(_event=None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))
        if canvas.winfo_width() > 1:
            canvas.itemconfig(window_id, width=canvas.winfo_width())

    container.bind("<Configure>", _on_configure)
    canvas.bind(
        "<Configure>",
        lambda e: canvas.itemconfig(window_id, width=e.width) if e.width > 1 else None,
    )

    def _on_wheel(event) -> None:
        delta = (
            int(-1 * event.delta)
            if platform.system() == "Darwin"
            else int(-1 * (event.delta / 120))
        )
        canvas.yview_scroll(delta, "units")

    canvas.bind("<MouseWheel>", _on_wheel)
    container.bind("<MouseWheel>", _on_wheel)
    return outer


def add_device_row(state: AppState, device: MudraDevice) -> None:
    container = state.devices_container
    if container is None or state.root is None or not state.root.winfo_exists():
        return
    if device.address in state.device_rows:
        return

    row = tk.Frame(container, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER)
    row.pack(fill=tk.X, pady=1)

    status_dot = tk.Label(row, text="●", font=("Segoe UI", 10), bg=BG_PANEL, fg=FG_MUTED, width=2)
    status_dot.pack(side=tk.LEFT, padx=(2, 0))

    display_name = device.name or device.address
    name_label = tk.Label(
        row,
        text=f"{display_name} [{device.transport.upper()}]\n{device.address}",
        font=("Segoe UI", 9),
        bg=BG_PANEL,
        fg=FG,
        anchor="w",
        justify=tk.LEFT,
    )
    name_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 4))

    action_btn = ttk.Button(
        row,
        text="Connect",
        width=11,
        command=lambda d=device: toggle_connection(state, d),
    )
    action_btn.pack(side=tk.RIGHT, padx=(0, 2), pady=2)

    info = {
        "device": device,
        "row": row,
        "name_label": name_label,
        "status_dot": status_dot,
        "action_btn": action_btn,
        "state": "idle",
    }
    state.device_rows[device.address] = info

    def _on_click(_event, d=device) -> None:
        select_device(state, d)

    for widget in (row, name_label, status_dot):
        widget.bind("<Button-1>", _on_click)

    _refresh_idle_buttons(state)


def select_device(state: AppState, device: MudraDevice) -> None:
    state.selected_device = device
    for info in state.device_rows.values():
        is_selected = info["device"] is device
        bg = SELECT if is_selected else BG_PANEL
        info["row"].config(bg=bg)
        info["name_label"].config(bg=bg)
        info["status_dot"].config(bg=bg)


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
        btn.config(text="...", state="disabled")
        set_indicator(dot, WARN)
    elif device_state == "connected":
        btn.config(text="Disconnect", state="normal")
        set_indicator(dot, OK)
    elif device_state == "disconnecting":
        btn.config(text="...", state="disabled")
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
