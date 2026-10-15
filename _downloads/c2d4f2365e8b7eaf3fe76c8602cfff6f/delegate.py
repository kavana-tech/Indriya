"""MudraDelegate implementation for the connect app.

Connection events update the device's card in the main window and open/close
that device's own window (device_window.py) — one per connected device.
"""

from __future__ import annotations

from mudra_sdk.models.callbacks import MudraDelegate
from mudra_sdk.models.mudra_device import MudraDevice
from mudra_sdk.logging_config import get_logger

from .device_window import close_device_window, open_device_window
from .devices import post_device_state, update_devices_list
from .state import AppState

logger = get_logger(__name__)


class ConnectAppDelegate(MudraDelegate):
    def __init__(self, state: AppState) -> None:
        self._state = state

    def _post_status(self, text: str) -> None:
        assert self._state.post_ui is not None
        self._state.post_ui(
            lambda: self._state.set_status(text) if self._state.set_status else None
        )

    def on_device_discovered(self, device: MudraDevice) -> None:
        logger.info(f"Discovered: {device.name} ({device.address})")
        update_devices_list(self._state, device)
        assert self._state.post_ui is not None
        self._state.post_ui(
            lambda: self._state.set_status(f"Found {len(self._state.device_rows)} device(s)")
        )

    def on_mudra_device_disconnected(self, device: MudraDevice) -> None:
        logger.info(f"Disconnected: {device.name}")
        post_device_state(self._state, device, "idle")
        assert self._state.post_ui is not None
        self._state.post_ui(lambda: close_device_window(self._state, device))
        self._post_status(f"Disconnected: {device.name or device.address}")

    def on_mudra_device_disconnecting(self, device: MudraDevice) -> None:
        logger.info(f"Disconnecting: {device.name}")
        post_device_state(self._state, device, "disconnecting")

    def on_mudra_device_connected(self, device: MudraDevice) -> None:
        logger.info(f"Connected: {device.name}")
        post_device_state(self._state, device, "connected")
        self._post_status(f"Connected: {device.name or device.address}")
        # Opening the window also registers the device's status callbacks
        # (status_ui.register_status_callbacks) against that window's state.
        assert self._state.post_ui is not None
        self._state.post_ui(lambda: open_device_window(self._state, device))

    def on_mudra_device_connecting(self, device: MudraDevice) -> None:
        logger.info(f"Connecting: {device.name}")
        post_device_state(self._state, device, "connecting")

    def on_mudra_device_connection_failed(self, device: MudraDevice, error: str) -> None:
        logger.error(f"Connection failed: {device.name}, error={error}")
        post_device_state(self._state, device, "idle")
        # The link may have opened (and the window with it) before setup failed.
        assert self._state.post_ui is not None
        self._state.post_ui(lambda: close_device_window(self._state, device))
        self._post_status(f"Connection failed ({device.name or device.address}): {error}")

    def on_bluetooth_state_changed(self, state: bool) -> None:
        logger.info(f"Bluetooth {'On' if state else 'Off'}")
        self._post_status(f"Bluetooth {'On' if state else 'Off'}")
