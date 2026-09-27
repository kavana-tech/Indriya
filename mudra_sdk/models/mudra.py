from bleak.backends.device import BLEDevice
from mudra_sdk.models.enums import (
    FirmwareDataType,
    MudraModel,
    SensorTypes,
    BtCmdId,
    BtCmdStatus,
)
from mudra_sdk.models.cdc_device import CdcDevice
from ..service import BleService, MudraCharacteristicUUID
from ..service.cdc_service import CdcService
from ..service.dfu_service import DfuService
from ..libs import load_library
from ctypes import CDLL
from typing import Callable, List, Optional, Union

import mudra_sdk.models.mudra_device as mudraDeviceModule
from mudra_sdk.models.mudra_pro import MudraPro
from mudra_sdk.models.mudra_ultimate import MudraUltimate

from ..models.callbacks import BleServiceDelegate, CdcServiceDelegate, MudraDelegate
from ..logging_config import get_logger

logger = get_logger(__name__)

class Mudra(BleServiceDelegate, CdcServiceDelegate):
    _instance = None
    _delegate: Optional[MudraDelegate] = None
    _ble_service: Optional[BleService] = None
    _cdc_service: Optional[CdcService] = None
    _dfu_service: Optional[DfuService] = None

    _mudra_devices: dict[str, mudraDeviceModule.MudraDevice] = {}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Mark instance as not yet initialized; used to guard __init__
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # Guard against running initialization logic multiple times on the singleton
        if getattr(self, "_initialized", False):
            return

        self._native_lib: Optional[CDLL] = None
        self._load_native_library()
        self._ble_service = BleService(delegate=self)
        self._cdc_service = CdcService(delegate=self)
        self._dfu_service = DfuService()
        self._initialized = True


    def _load_native_library(self):
        """
        Load the native library for the current platform.
        This will automatically detect the platform and load the correct .dll/.so/.dylib
        """
        try:
            self._native_lib = load_library('MudraSDK', 'MudraSDK')
            logger.info(f"Native library loaded: {self._native_lib}")
        except (FileNotFoundError, OSError) as e:
            # Handle the case where the library is not found or cannot be loaded
            logger.warning(f"Could not load native library: {e}")
            self._native_lib = None

    @property
    def native_lib(self) -> Optional[CDLL]:
        """Get the loaded native library, or None if not loaded."""
        return self._native_lib

    def get_native_library(self) -> Optional[CDLL]:
        return self._native_lib

    async def send_general_command(self, device: mudraDeviceModule.MudraDevice, command: bytes):
        await self._ble_service.send_general_command(device, command)

    async def send_cdc_command(self, device: mudraDeviceModule.MudraDevice, command: str) -> None:
        """Send one ASCII CONFIG-port command for a CDC-transport device.

        The device's reply is also forwarded to ``on_command_reply_received``
        (below), which decodes it into the same higher-level events BLE
        produces (sensor status / command errors) where a mapping exists.
        """
        await self._cdc_service.query(device.as_cdc_device(), command)

    async def send_cdc_ping(self, device: mudraDeviceModule.MudraDevice) -> None:
        await self._cdc_service.ping(device.as_cdc_device())

    async def update_configuration(
        self,
        device: mudraDeviceModule.MudraDevice,
        enable: bool,
        data_type: FirmwareDataType,
    ) -> None:
        if device.transport == "cdc":
            cmd = device._cdc_power_command(data_type)
            if cmd is None:
                return
            await device._cdc_send(device._cdc_token(cmd, enable))
            return
        await self._ble_service.update_configuration(device, enable, data_type)

    async def start_dfu(
        self,
        device: mudraDeviceModule.MudraDevice,
        firmware_path: str,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_stage: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Update `device`'s firmware over its USB-CDC SMP port (see
        ``dfu_service.py``). Returns the version string just staged; the
        device reboots and swaps to it right after — reconnect afterward to
        confirm. Works whether or not `device` is currently connected via
        `CdcService` (the SMP port is a separate physical port from
        CONFIG/DATA), but requires DFU-enabled firmware to be running."""
        cdc_device = device.as_cdc_device()
        if cdc_device is None:
            raise RuntimeError("Firmware update is only supported over USB (CDC) for now")

        with open(firmware_path, "rb") as f:
            image = f.read()

        exclude_ports = [p for p in (cdc_device.config_port, cdc_device.data_port) if p]
        port = await self._dfu_service.find_port(cdc_device.serial_number, exclude_ports)
        if port is None:
            raise RuntimeError(
                "Could not find the device's SMP (firmware-update) port — "
                "is it running DFU-enabled firmware?"
            )
        return await self._dfu_service.update(
            port, image, on_progress=on_progress, on_stage=on_stage
        )

    ### ----------------------- Connection Methods ----------------------- ###

    async def connect(self, device: mudraDeviceModule.MudraDevice):
        if device.transport == "cdc":
            await self._cdc_service.connect(device.as_cdc_device())
            return
        await self._ble_service.connect(device)

    async def disconnect(self, device: mudraDeviceModule.MudraDevice):
        if device.transport == "cdc":
            try:
                await device.stop_streaming()
            except Exception as e:
                logger.error(f"Failed to stop CDC streaming for {device.address}: {e}")
            await self._cdc_service.disconnect(device.as_cdc_device())
            return
        await self._ble_service.disconnect(device)

    async def is_connected(self, device: mudraDeviceModule.MudraDevice) -> bool:
        if device.transport == "cdc":
            return self._cdc_service.is_connected(device.as_cdc_device())
        return self._ble_service.is_connected(device)

    ### ----------------------- Scan Methods ----------------------- ###

    async def scan_ble(self):
        await self._ble_service.scan()

    async def stop_scan_ble(self):
        await self._ble_service.stop_scanning()

    async def scan_cdc(self):
        await self._cdc_service.scan()

    async def stop_scan_cdc(self):
        await self._cdc_service.stop_scanning()

    async def get_connected_devices(self) -> List[mudraDeviceModule.MudraDevice]:
        devices: List[mudraDeviceModule.MudraDevice] = []

        raw_ble_devices = await self._ble_service.get_connected_devices()
        for raw in raw_ble_devices:
            mudra_device = self._create_device(raw)
            devices.append(mudra_device)
            if self._delegate:
                self._delegate.on_device_discovered(mudra_device)

        for cdc_device in self._cdc_service.get_connected_devices():
            mudra_device = self._create_device(cdc_device)
            devices.append(mudra_device)
            if self._delegate:
                self._delegate.on_device_discovered(mudra_device)

        return devices

    # --- Implementation of BleServiceDelegate abstract methods ---
    async def on_ble_characteristic_discovered(self, device: mudraDeviceModule.MudraDevice, characteristic_uuid: MudraCharacteristicUUID):
        if device.address in self._mudra_devices:
            logger.debug(f"on_ble_characteristic_discovered: {device.name}")
            self._mudra_devices[device.address].on_characteristic_discovered(characteristic_uuid)
        else:
            logger.warning(f"on_ble_characteristic_discovered: Device not found: {device.name}")

    def on_charging_state_changed(self, device_address: str, is_charging: bool):
        if device_address in self._mudra_devices:
            self._mudra_devices[device_address].on_charging_state_changed(is_charging)

    def on_data_received(self, device_address: str, data: bytes):
        if device_address in self._mudra_devices:
            self._mudra_devices[device_address].on_data_received(data)

    def on_battery_level_changed(self, device_address: str, level: int):
        if device_address in self._mudra_devices:
            self._mudra_devices[device_address].on_battery_level_changed(level)

    def on_sensor_status_received(self, device_address: str, sensor_type: SensorTypes, status: bytes):
        if device_address in self._mudra_devices:
            self._mudra_devices[device_address].on_sensor_status_received(sensor_type, status)

    def on_storage_record_state_received(self, device_address: str, status: bytes):
        if device_address in self._mudra_devices:
            self._mudra_devices[device_address].on_storage_record_state_received(status)

    def on_storage_record_error_received(self, device_address: str, status: BtCmdStatus):
        if device_address in self._mudra_devices:
            self._mudra_devices[device_address].on_storage_record_error_received(status)

    def on_storage_next_file_num_received(self, device_address: str, data: bytes):
        if device_address in self._mudra_devices:
            self._mudra_devices[device_address].on_storage_next_file_num_received(data)

    def on_command_error_received(
        self, device_address: str, cmd_id: BtCmdId, status: BtCmdStatus
    ):
        if device_address in self._mudra_devices:
            self._mudra_devices[device_address].on_command_error_received(cmd_id, status)

    def on_ping_response_received(self, device_address: str):
        if device_address in self._mudra_devices:
            self._mudra_devices[device_address].on_ping_response_received()

    def on_device_info_received(self, device_address: str, data: bytes) -> None:
        if device_address in self._mudra_devices:
            self._mudra_devices[device_address].on_device_info_received(data)

    def on_firmware_version_received(self, device_address: str, data: bytes) -> None:
        if device_address in self._mudra_devices:
            self._mudra_devices[device_address].on_firmware_version_received(data)

    # --- Implementation of CdcServiceDelegate abstract methods ---
    def on_command_reply_received(self, device_address: str, line: str) -> None:
        """Fallback for a CONFIG-port line `CdcService._dispatch_reply`
        couldn't classify as a sensor-status push or a setter error — a
        plain GET reply or a bare "<TOKEN> OK" ack. Mirrors
        `BleService._command_notification_handler`'s final `case _:`, which
        likewise just logs an unrecognized frame."""
        logger.debug(f"CDC reply from {device_address}: {line}")

    # --- Implementation of MudraDelegate abstract methods ---

    @staticmethod
    def _device_class_for_model(model: MudraModel) -> type:
        """Which MudraDevice subclass — and therefore which fully-independent
        command table (ProFirmwareCommand vs. UltimateFirmwareCommand) — a
        detected device gets."""
        return MudraUltimate if model == MudraModel.ULTIMATE else MudraPro

    def _create_device(self, device: Union[BLEDevice, CdcDevice]) -> mudraDeviceModule.MudraDevice:
        if device.address in self._mudra_devices:
            return self._mudra_devices[device.address]
        if isinstance(device, CdcDevice):
            device_class = self._device_class_for_model(device.model)
            mudra_device = device_class(cdc_device=device)
        else:
            # `.model` is stamped by BleService._on_device_detected via
            # MudraModel.from_ble_name() during scanning — but a device
            # reached via get_connected_devices() (an OS-level "already
            # connected" query, e.g. the example app's "Find Connected"
            # button) never goes through that scan callback, so it never
            # gets stamped. Fall back to the same name-based classification
            # directly rather than silently defaulting to Pro — that
            # default previously made an Ultimate device found this way talk
            # Pro's command bytes (e.g. EMG_STATUS 0x04 instead of 0x08),
            # which firmware then rejects as ERR_INVALID.
            model = (
                getattr(device, "model", None)
                or MudraModel.from_ble_name(getattr(device, "name", None))
                or MudraModel.PRO
            )
            device_class = self._device_class_for_model(model)
            mudra_device = device_class(ble_device=device)
        self._mudra_devices[device.address] = mudra_device
        return mudra_device

    def set_delegate(self, delegate: MudraDelegate):
        self._delegate = delegate

    def on_device_discovered(self, device: Union[BLEDevice, CdcDevice]):
        mudra_device = self._create_device(device)
        if self._delegate:
            self._delegate.on_device_discovered(mudra_device)

    def on_mudra_device_disconnected(self, device: Union[BLEDevice, CdcDevice]):
        mudra_device = self._mudra_devices.get(device.address)
        if mudra_device and self._delegate:
            self._delegate.on_mudra_device_disconnected(mudra_device)
            mudra_device.handle_disconnection()

    def on_mudra_device_disconnecting(self, device: Union[BLEDevice, CdcDevice]):
        mudra_device = self._mudra_devices.get(device.address)
        if mudra_device and self._delegate:
            self._delegate.on_mudra_device_disconnecting(mudra_device)

    async def on_mudra_device_connected(self, device: Union[BLEDevice, CdcDevice]):
        mudra_device = self._mudra_devices.get(device.address)
        if mudra_device is None:
            return
        if self._delegate:
            self._delegate.on_mudra_device_connected(mudra_device)
        if mudra_device.transport == "cdc":
            # CDC has no GATT-discovery step to hang the initial status
            # queries off of, and needs an explicit global START to make the
            # DATA port stream at all (BLE has neither requirement).
            # on_cdc_ready() must complete BEFORE start_streaming(): it's what
            # sets the native parser's EMG resolution/IMU ranges, and if the
            # device is already running when we connect, DATA bytes at the
            # real (possibly non-default) stride can start arriving the
            # instant START is sent.
            try:
                await mudra_device.on_cdc_ready()
            except Exception as e:
                logger.error(f"Failed to query initial CDC status for {device.address}: {e}")
            try:
                await mudra_device.start_streaming()
            except Exception as e:
                logger.error(f"Failed to start CDC streaming for {device.address}: {e}")

    def on_mudra_device_connecting(self, device: Union[BLEDevice, CdcDevice]):
        mudra_device = self._mudra_devices.get(device.address)
        if mudra_device and self._delegate:
            self._delegate.on_mudra_device_connecting(mudra_device)

    def on_mudra_device_connection_failed(self, device: Union[BLEDevice, CdcDevice], error: str):
        mudra_device = self._mudra_devices.get(device.address)
        if mudra_device and self._delegate:
            self._delegate.on_mudra_device_connection_failed(mudra_device, error)

    def on_bluetooth_state_changed(self, state: bool):
        if self._delegate:
            self._delegate.on_bluetooth_state_changed(state)

