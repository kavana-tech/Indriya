"""Shared UI / device state for the connect app (no module-level globals)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

import tkinter as tk
from tkinter import ttk

from mudra_sdk import Mudra, MudraDevice
from mudra_sdk.logging_config import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from .async_bridge import AsyncBridge
    from .charts import SensorCharts
    from .packet_loss_chart import PacketLossChart
    from .ping_chart import PingChart


@dataclass
class AppState:
    mudra: Mudra = field(default_factory=Mudra)
    bridge: Optional["AsyncBridge"] = None
    root: Optional[tk.Tk] = None
    charts: Optional["SensorCharts"] = None
    ping_chart: Optional["PingChart"] = None
    ping_status_label: Optional[tk.Label] = None
    # Ping timer/timing state lives here (app layer) — the SDK only sends/notifies.
    ping_task: Optional[asyncio.Task] = None
    ping_sent_at_iso: Optional[str] = None
    ping_interval_s: float = 0.1
    ping_interval_var: Optional[tk.StringVar] = None

    # Packet-loss test: sensor name -> status label / running flag / ODR combo.
    # The actual counting is native (ComputationManager::GetPacketLossStats)
    # and runs independent of any ready-callback; MudraDevice's
    # PacketLossWindow turns a poll of it into a windowed percentage.
    # panels/packet_loss.py's tick() polls active sensors each app refresh
    # and writes the result here for the chart to read.
    packet_loss_labels: Dict[str, tk.Label] = field(default_factory=dict)
    packet_loss_active: Dict[str, bool] = field(default_factory=dict)
    packet_loss_odr_combos: Dict[str, ttk.Combobox] = field(default_factory=dict)
    packet_loss_chart: Optional["PacketLossChart"] = None
    packet_loss_pct_by_sensor: Dict[str, float] = field(default_factory=dict)
    # Threshold-alert badge next to each sensor's ODR combo.
    packet_loss_alert_labels: Dict[str, tk.Label] = field(default_factory=dict)

    devices_list: List[MudraDevice] = field(default_factory=list)
    device_rows: Dict[str, dict] = field(default_factory=dict)
    devices_container: Optional[tk.Frame] = None
    selected_device: Optional[MudraDevice] = None

    # BLE/CDC scan toggle buttons (toolbar) — each independently starts/stops
    # scanning on its own transport via Mudra.scan_ble()/scan_cdc().
    ble_scanning: bool = False
    cdc_scanning: bool = False
    ble_scan_btn: Optional[ttk.Button] = None
    cdc_scan_btn: Optional[ttk.Button] = None

    # Sensors tab indicators: sensor -> {dot, text}
    sensor_status_ui: Dict[str, dict] = field(default_factory=dict)
    # Config status summary labels (Explorer + Ping may each register one)
    config_status_labels: Dict[str, List[tk.Label]] = field(default_factory=dict)

    # EMG ODR comboboxes — config.py's build_sensor_config_ui() is called
    # from TWO places (sensors.py's Explorer tab and panels/ping.py's Ping
    # tab), each building its own
    # independent widget instance; same pattern as config_status_labels
    # above. Their valid-values list is per-device-model (ProEMGODR vs
    # UltimateEMGODR — different AFEs, different discrete rates), so every
    # combo in this list is re-populated in
    # status_ui.register_status_callbacks() on every connect rather than
    # being a fixed module-level list.
    emg_odr_combos: List[ttk.Combobox] = field(default_factory=list)

    # Per-sensor "Split into separate charts" checkboxes (sensors.py) — sensor
    # name (EMG/IMU_H/IMU_F) -> its BooleanVar. Kept here mainly so the
    # BooleanVar isn't garbage-collected out from under its Checkbutton;
    # charts.SensorCharts itself is the actual source of truth for split
    # state (SensorCharts._split).
    chart_split_vars: Dict[str, tk.BooleanVar] = field(default_factory=dict)

    # Firmware update (DFU) panel widgets / state (panels/dfu.py)
    dfu_file_var: Optional[tk.StringVar] = None
    dfu_status_label: Optional[tk.Label] = None
    dfu_progress: Optional[ttk.Progressbar] = None
    dfu_busy: bool = False

    # Recording widgets / vars (SD card — panels/recording.py)
    record_status_label: Optional[tk.Label] = None
    record_vars: Dict[str, tk.BooleanVar] = field(default_factory=dict)
    record_file_var: Optional[tk.StringVar] = None
    record_duration_var: Optional[tk.StringVar] = None
    record_send_utc_var: Optional[tk.BooleanVar] = None
    record_desc_var: Optional[tk.StringVar] = None

    # PC-side JSON recording widgets / vars (panels/pc_recording.py)
    pc_record_status_label: Optional[tk.Label] = None
    pc_record_vars: Dict[str, tk.BooleanVar] = field(default_factory=dict)

    # Status / rate labels (toolbar)
    status_label: Optional[tk.Label] = None
    rate_label: Optional[tk.Label] = None

    # Account sign-in bar (panels/auth.py)
    auth_email_var: Optional[tk.StringVar] = None
    auth_password_var: Optional[tk.StringVar] = None
    auth_status_label: Optional[tk.Label] = None
    # Device license tier indicator (updated via set_on_license_device_info_received)
    license_tier_dot: Optional[tk.Label] = None
    license_tier_label: Optional[tk.Label] = None

    # Device firmware version indicator (updated via
    # set_on_firmware_version_received — BT_SYS_VERSION, 0x00 0x01)
    firmware_version_dot: Optional[tk.Label] = None
    firmware_version_label: Optional[tk.Label] = None

    # Battery / charging indicator (updated via set_on_battery_level_changed
    # and set_on_charging_state_changed — see status_ui.py). The two
    # callbacks fire independently, so the last-known values are cached here
    # and merged into a single indicator on every update.
    battery_dot: Optional[tk.Label] = None
    battery_label: Optional[tk.Label] = None
    battery_level: Optional[int] = None
    battery_is_charging: Optional[bool] = None

    # Optional hooks set by App after UI build
    set_status: Optional[Callable[[str], None]] = None
    post_ui: Optional[Callable[[Callable], None]] = None

    def connected_device(self) -> Optional[MudraDevice]:
        if self.selected_device is not None:
            info = self.device_rows.get(self.selected_device.address)
            if info and info["state"] == "connected":
                return self.selected_device
        for info in self.device_rows.values():
            if info["state"] == "connected":
                return info["device"]
        return None

    def run_device(self, label: str, coro_fn: Callable) -> None:
        device = self.connected_device()
        if device is None:
            if self.set_status is not None:
                self.set_status("Connect a device before sending a command")
            return
        assert self.bridge is not None
        self.bridge.ensure_running()
        if self.set_status is not None:
            self.set_status(f"Sending {label}...")
        logger.info(f"Sending {label} to {device.name or device.address}")

        async def _run() -> None:
            try:
                await coro_fn(device)
                if self.post_ui is not None and self.set_status is not None:
                    self.post_ui(lambda: self.set_status(f"Sent {label}"))
            except Exception as exc:  # noqa: BLE001
                if self.post_ui is not None and self.set_status is not None:
                    self.post_ui(lambda: self.set_status(f"{label} failed: {exc}"))
                logger.error(f"{label} failed: {exc}")

        self.bridge.submit(_run())
