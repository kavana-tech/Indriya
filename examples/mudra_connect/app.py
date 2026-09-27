"""Main window assembly for the Mudra Pro connect app."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .anim import set_text
from .async_bridge import AsyncBridge
from .charts import CHART_REFRESH_MS
from .delegate import ConnectAppDelegate
from .devices import build_device_list, find_connected_devices, toggle_scan_ble, toggle_scan_cdc
from .panels import packet_loss
from .panels.auth import build_auth_bar
from .panels.command import build_command_ui
from .panels.dfu import build_dfu_ui
from .panels.packet_loss import build_packet_loss_ui
from .panels.ping import build_ping_ui
from .recording_tab import build_recording_tab
from .sensors import build_streams_panel
from .state import AppState
from .theme import BG, BG_PANEL, apply_theme, panel

def main() -> None:
    root = tk.Tk()
    root.title("Mudra Pro — Signal Explorer")
    root.geometry("1280x900")
    root.minsize(1000, 720)
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
    main_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    # Top toolbar
    toolbar = ttk.Frame(main_container, style="Toolbar.TFrame")
    toolbar.pack(fill=tk.X, pady=(0, 8))

    ttk.Label(toolbar, text="Mudra Pro", style="Title.TLabel").pack(side=tk.LEFT, padx=(0, 16))
    state.ble_scan_btn = ttk.Button(
        toolbar,
        text="BLE Scan",
        style="Accent.TButton",
        command=lambda: toggle_scan_ble(state),
    )
    state.ble_scan_btn.pack(side=tk.LEFT, padx=(0, 4))
    state.cdc_scan_btn = ttk.Button(
        toolbar,
        text="CDC Scan",
        style="Accent.TButton",
        command=lambda: toggle_scan_cdc(state),
    )
    state.cdc_scan_btn.pack(side=tk.LEFT, padx=(0, 4))
    ttk.Button(
        toolbar,
        text="Find Connected",
        command=lambda: find_connected_devices(state),
    ).pack(side=tk.LEFT, padx=(4, 0))

    state.status_label = ttk.Label(
        toolbar,
        text="Ready. Click BLE Scan or CDC Scan.",
        style="Status.TLabel",
    )
    state.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(16, 8))

    state.rate_label = ttk.Label(
        toolbar,
        text="EMG 0 · H 0 · F 0 · PPG 0 Hz",
        style="Status.TLabel",
    )
    state.rate_label.pack(side=tk.RIGHT)

    # Account sign-in bar — email/password + Login/Logout (panels/auth.py).
    # Optional: connecting never requires signing in. A signed-in session
    # only lets a connected device get licensed to a higher tier (see
    # ConnectAppDelegate._provision_license).
    auth_bar = build_auth_bar(main_container, state)
    auth_bar.pack(fill=tk.X, pady=(0, 8))

    # Body: device list + notebook tabs
    body = tk.Frame(main_container, bg=BG)
    body.pack(fill=tk.BOTH, expand=True)

    left = tk.Frame(body, bg=BG, width=260)
    left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
    left.pack_propagate(False)
    build_device_list(left, state)

    right = panel(body)
    right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    notebook = ttk.Notebook(right)
    notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    explorer_tab = tk.Frame(notebook, bg=BG_PANEL)
    recording_tab = tk.Frame(notebook, bg=BG_PANEL)
    ping_tab = tk.Frame(notebook, bg=BG_PANEL)
    packet_loss_tab = tk.Frame(notebook, bg=BG_PANEL)
    advanced_tab = tk.Frame(notebook, bg=BG_PANEL)
    dfu_tab = tk.Frame(notebook, bg=BG_PANEL)
    notebook.add(explorer_tab, text="Explorer")
    notebook.add(recording_tab, text="Recording")
    notebook.add(ping_tab, text="Ping")
    notebook.add(packet_loss_tab, text="Packet Loss")
    notebook.add(advanced_tab, text="Advanced")
    notebook.add(dfu_tab, text="Firmware Update")

    build_streams_panel(explorer_tab, state)
    build_recording_tab(recording_tab, state)
    build_ping_ui(ping_tab, state)
    build_packet_loss_ui(packet_loss_tab, state)

    advanced_wrap = tk.Frame(advanced_tab, bg=BG_PANEL, padx=8, pady=8)
    advanced_wrap.pack(fill=tk.BOTH, expand=True)
    build_command_ui(advanced_wrap, state)

    build_dfu_ui(dfu_tab, state)

    def schedule_chart_refresh() -> None:
        if state.charts is not None:
            state.charts.drain_and_redraw()
        if state.ping_chart is not None:
            state.ping_chart.drain_and_redraw()
        packet_loss.tick(state)
        if state.packet_loss_chart is not None:
            current = dict(state.packet_loss_pct_by_sensor)
            # The chart's dashed reference line sits at this same current
            # last-~1s value as the scrolling line — a flat "where am I
            # right now" level, not a mean accumulated over the test.
            state.packet_loss_chart.sample_tick(current, dict(state.packet_loss_active), current)
            state.packet_loss_chart.redraw()
        if root.winfo_exists():
            root.after(CHART_REFRESH_MS, schedule_chart_refresh)

    state.bridge.ensure_running()
    schedule_chart_refresh()
    root.mainloop()
