"""MudraDelegate implementation for the connect app."""

from __future__ import annotations

from mudra_sdk.models.callbacks import MudraDelegate
from mudra_sdk.models.mudra_device import MudraDevice
from mudra_sdk.logging_config import get_logger

from .devices import post_device_state, update_devices_list
from .state import AppState
from .status_ui import register_status_callbacks, reset_sensor_indicators

logger = get_logger(__name__)


class ConnectAppDelegate(MudraDelegate):
    def __init__(self, state: AppState) -> None:
        self._state = state

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
        self._state.post_ui(lambda: reset_sensor_indicators(self._state))
        self._state.post_ui(
            lambda: self._state.set_status(f"Disconnected: {device.name or device.address}")
            if self._state.set_status
            else None
        )

    def on_mudra_device_disconnecting(self, device: MudraDevice) -> None:
        logger.info(f"Disconnecting: {device.name}")
        post_device_state(self._state, device, "disconnecting")

    def on_mudra_device_connected(self, device: MudraDevice) -> None:
        logger.info(f"Connected: {device.name}")
        post_device_state(self._state, device, "connected")
        assert self._state.post_ui is not None
        self._state.post_ui(
            lambda: self._state.set_status(f"Connected: {device.name or device.address}")
            if self._state.set_status
            else None
        )
        assert self._state.bridge is not None
        self._state.bridge.ensure_running()
        self._state.bridge.submit(register_status_callbacks(device, self._state))

    def on_mudra_device_connecting(self, device: MudraDevice) -> None:
        logger.info(f"Connecting: {device.name}")
        post_device_state(self._state, device, "connecting")

    def on_mudra_device_connection_failed(self, device: MudraDevice, error: str) -> None:
        logger.error(f"Connection failed: {device.name}, error={error}")
        post_device_state(self._state, device, "idle")
        assert self._state.post_ui is not None
        self._state.post_ui(
            lambda: self._state.set_status(f"Connection failed: {error}")
            if self._state.set_status
            else None
        )

    def on_bluetooth_state_changed(self, state: bool) -> None:
        logger.info(f"Bluetooth {'On' if state else 'Off'}")
        assert self._state.post_ui is not None
        self._state.post_ui(
            lambda: self._state.set_status(f"Bluetooth {'On' if state else 'Off'}")
            if self._state.set_status
            else None
        )
