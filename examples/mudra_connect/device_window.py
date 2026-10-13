"""One window per connected device.

Every connected device gets its own ``tk.Toplevel`` holding the full set of
per-device tabs (Explorer, Recording, Ping, Packet Loss, Advanced, Firmware
Update), its FW / Battery / License indicators and its own status bar — all
backed by one :class:`DeviceState`, so each window only ever talks to its own
device. The main window (app.py) keeps scanning, sign-in and the device list.

Lifecycle: ``ConnectAppDelegate.on_mudra_device_connected`` opens the window
and registers the device's status callbacks; it closes again when the device
disconnects (or fails to connect). Closing the window disconnects the device.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from mudra_sdk import __version__ as SDK_VERSION
from mudra_sdk.models.mudra_device import MudraDevice
from mudra_sdk.logging_config import get_logger

from .anim import set_text
from .charts import CHART_REFRESH_MS
from .panels import packet_loss
from .panels.command import build_command_ui
from .panels.dfu import build_dfu_ui
from .panels.packet_loss import build_packet_loss_ui
from .panels.ping import build_ping_ui
from .recording_tab import build_recording_tab
from .sensors import build_streams_panel
from .state import AppState, DeviceState
from .status_ui import build_device_indicators, register_status_callbacks
from .theme import BG, BG_PANEL, px

logger = get_logger(__name__)

# How far each new device window is shifted from the previous one, so two
# windows opened back to back don't sit exactly on top of each other.
_CASCADE_STEP = 32


def _device_title(device: MudraDevice) -> str:
    return f"{device.name or device.address} ({device.transport.upper()})"


def _initial_geometry(window: tk.Toplevel, index: int) -> None:
    screen_w, screen_h = window.winfo_screenwidth(), window.winfo_screenheight()
    width = min(px(1360), screen_w - px(40))
    height = min(px(900), screen_h - px(80))
    offset = px(_CASCADE_STEP) * (index % 6)
    window.geometry(f"{width}x{height}+{px(20) + offset}+{px(20) + offset}")
    window.minsize(min(px(960), width), min(px(620), height))


def _window_alive(state: DeviceState) -> bool:
    try:
        return state.window is not None and bool(state.window.winfo_exists())
    except tk.TclError:
        return False


def open_device_window(app: AppState, device: MudraDevice) -> DeviceState:
    """Open ``device``'s window (or raise it if it's already open) and
    register its status callbacks. Tk thread only."""
    existing = app.device_windows.get(device.address)
    if existing is not None and _window_alive(existing):
        existing.window.deiconify()
        existing.window.lift()
        existing.window.focus_force()
        return existing

    assert app.root is not None
    window = tk.Toplevel(app.root, bg=BG)
    window.title(f"{_device_title(device)} — Signal Explorer — SDK v{SDK_VERSION}")
    _initial_geometry(window, len(app.device_windows))

    state = DeviceState(app=app, device=device, window=window)
    app.device_windows[device.address] = state

    def set_status(text: str) -> None:
        if state.status_label is not None and _window_alive(state):
            set_text(state.status_label, text)

    def post_ui(callback) -> None:
        # Device callbacks arrive on the asyncio thread and may still land
        # just after this window is closed — drop them once it's gone.
        root = app.root
        if root is None or not root.winfo_exists():
            return

        def _run() -> None:
            if _window_alive(state):
                callback()

        root.after(0, _run)

    state.set_status = set_status
    state.post_ui = post_ui

    _build_window(window, state)
    window.protocol("WM_DELETE_WINDOW", lambda: _on_window_close(state))
    _schedule_chart_refresh(state)

    assert app.bridge is not None
    app.bridge.ensure_running()
    app.bridge.submit(register_status_callbacks(device, state))
    return state


def close_device_window(app: AppState, device: MudraDevice) -> None:
    """Tear down ``device``'s window if it's open. Tk thread only."""
    state = app.device_windows.pop(device.address, None)
    if state is None:
        return
    _stop_ping(state)
    if _window_alive(state):
        state.window.destroy()


def _stop_ping(state: DeviceState) -> None:
    """Cancel a running ping loop — it lives on the asyncio thread and would
    otherwise keep pinging a device whose window is gone."""
    task = state.ping_task
    if task is None or state.bridge is None or state.bridge.loop is None:
        return
    state.ping_task = None
    state.bridge.loop.call_soon_threadsafe(task.cancel)


def _on_window_close(state: DeviceState) -> None:
    """Closing a device window disconnects that device."""
    app = state.app
    device = state.device
    close_device_window(app, device)

    info = app.device_rows.get(device.address)
    if info is None or info["state"] != "connected":
        return
    # Imported here: devices.py imports this module.
    from .devices import toggle_connection

    toggle_connection(app, device)


def _build_window(window: tk.Toplevel, state: DeviceState) -> None:
    device = state.device
    container = tk.Frame(window, bg=BG)
    container.pack(fill=tk.BOTH, expand=True, padx=px(8), pady=px(8))

    # Top toolbar: device name (left), FW/Battery/License indicators (right).
    toolbar = ttk.Frame(container, style="Toolbar.TFrame")
    toolbar.pack(side=tk.TOP, fill=tk.X, pady=(0, px(8)))

    build_device_indicators(toolbar, state).pack(side=tk.RIGHT)

    ttk.Label(toolbar, text=device.name or device.address, style="Title.TLabel").pack(
        side=tk.LEFT, padx=(0, px(8))
    )
    ttk.Label(
        toolbar,
        text=f"{device.transport.upper()} · {device.address}",
        style="Status.TLabel",
    ).pack(side=tk.LEFT, padx=(0, px(16)))
    ttk.Button(
        toolbar,
        text="Disconnect",
        command=lambda: _on_window_close(state),
    ).pack(side=tk.LEFT)

    # Bottom status bar — packed before the body so the body, not the status
    # line, is what gives up height on a short window.
    status_bar = ttk.Frame(container, style="Toolbar.TFrame")
    status_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(px(6), 0))
    state.rate_label = ttk.Label(
        status_bar,
        text="EMG 0 · H 0 · F 0 · PPG_H 0 · PPG_F 0 Hz",
        style="Status.TLabel",
    )
    state.rate_label.pack(side=tk.RIGHT, padx=(px(8), 0))
    state.status_label = ttk.Label(
        status_bar,
        text=f"Connected: {device.name or device.address}",
        style="Status.TLabel",
    )
    state.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

    notebook = ttk.Notebook(container)
    notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

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

    advanced_wrap = tk.Frame(advanced_tab, bg=BG_PANEL, padx=px(8), pady=px(8))
    advanced_wrap.pack(fill=tk.BOTH, expand=True)
    build_command_ui(advanced_wrap, state)

    build_dfu_ui(dfu_tab, state)


def _schedule_chart_refresh(state: DeviceState) -> None:
    """Per-window redraw loop. Scheduled on the app root (which outlives
    this window), and stops by itself once the window is gone."""
    if not _window_alive(state):
        return
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
    root = state.app.root
    if root is not None and root.winfo_exists():
        root.after(CHART_REFRESH_MS, lambda: _schedule_chart_refresh(state))
