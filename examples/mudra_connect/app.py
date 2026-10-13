"""Main window assembly for the Mudra Pro connect app.

The main window holds scanning, account sign-in and the device list. Any
number of listed devices can be connected at once; each connected device
opens its own window with the per-device tabs (device_window.py).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .anim import set_text
from .async_bridge import AsyncBridge
from .delegate import ConnectAppDelegate
from .devices import (
    build_device_list,
    device_list_width,
    find_connected_devices,
    toggle_scan_ble,
    toggle_scan_cdc,
)
from .panels.auth import build_auth_bar
from .state import AppState
from .theme import BG, apply_theme, enable_windows_dpi_awareness, px


def _initial_geometry(root: tk.Tk) -> None:
    """Wide enough for the toolbar and sign-in bar at this screen's scale,
    tall enough for a handful of device cards — never larger than the screen
    itself (winfo_screen* spans every monitor on some X setups, so it's only
    an upper bound)."""
    root.update_idletasks()
    screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
    width = min(max(root.winfo_reqwidth(), device_list_width() * 2), screen_w - px(40))
    height = min(px(640), screen_h - px(80))
    root.geometry(f"{width}x{height}")
    root.minsize(min(px(480), width), min(px(360), height))


def main() -> None:
    enable_windows_dpi_awareness()
    root = tk.Tk()
    root.title("Mudra Pro — Signal Explorer")
    apply_theme(root)

    state = AppState(root=root, bridge=AsyncBridge())

    def set_status(text: str) -> None:
        if state.status_label is not None and root.winfo_exists():
            set_text(state.status_label, text)

    def post_ui(callback) -> None:
        if root.winfo_exists():
            root.after(0, callback)

    state.set_status = set_status
    state.post_ui = post_ui

    state.mudra.set_delegate(ConnectAppDelegate(state))

    main_container = tk.Frame(root, bg=BG)
    main_container.pack(fill=tk.BOTH, expand=True, padx=px(8), pady=px(8))

    # Top toolbar: scan controls.
    toolbar = ttk.Frame(main_container, style="Toolbar.TFrame")
    toolbar.pack(side=tk.TOP, fill=tk.X, pady=(0, px(8)))

    ttk.Label(toolbar, text="Mudra Pro", style="Title.TLabel").pack(side=tk.LEFT, padx=(0, px(16)))
    state.ble_scan_btn = ttk.Button(
        toolbar,
        text="BLE Scan",
        style="Accent.TButton",
        command=lambda: toggle_scan_ble(state),
    )
    state.ble_scan_btn.pack(side=tk.LEFT, padx=(0, px(4)))
    state.cdc_scan_btn = ttk.Button(
        toolbar,
        text="CDC Scan",
        style="Accent.TButton",
        command=lambda: toggle_scan_cdc(state),
    )
    state.cdc_scan_btn.pack(side=tk.LEFT, padx=(0, px(4)))
    ttk.Button(
        toolbar,
        text="Find Connected",
        command=lambda: find_connected_devices(state),
    ).pack(side=tk.LEFT, padx=(px(4), 0))

    # Account sign-in bar — email/password + Login/Logout (panels/auth.py).
    # Optional: connecting never requires signing in. While signed in, the
    # SDK provisions every device it connects (license + user ID) itself.
    auth_bar = build_auth_bar(main_container, state)
    auth_bar.pack(side=tk.TOP, fill=tk.X, pady=(0, px(8)))

    # Bottom status bar — packed before the body so the body, not the status
    # line, is what gives up height on a short window.
    status_bar = ttk.Frame(main_container, style="Toolbar.TFrame")
    status_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(px(6), 0))
    state.status_label = ttk.Label(
        status_bar,
        text="Ready. Click BLE Scan or CDC Scan, then Connect one or more devices.",
        style="Status.TLabel",
    )
    state.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # Body: the device list. Each connected device opens its own window.
    build_device_list(main_container, state).pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    _initial_geometry(root)
    state.bridge.ensure_running()
    root.mainloop()
