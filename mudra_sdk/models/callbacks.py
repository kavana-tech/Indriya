from abc import ABC, abstractmethod



from bleak.backends.device import BLEDevice

from mudra_sdk.models.enums import SensorTypes, BtCmdId, BtCmdStatus



from ..service.ble_service import MudraCharacteristicUUID

from mudra_sdk.models.cdc_device import CdcDevice

import mudra_sdk.models.mudra_device as mudraDeviceModule



from typing import Callable



OnBleDeviceDiscovered = Callable[[mudraDeviceModule.MudraDevice], None]  

OnBleDeviceConnected = Callable[[mudraDeviceModule.MudraDevice], None]

OnBleDeviceDisconnected = Callable[[mudraDeviceModule.MudraDevice], None]

OnBleDeviceDisconnecting = Callable[[mudraDeviceModule.MudraDevice], None]

OnBleDeviceConnecting = Callable[[mudraDeviceModule.MudraDevice], None]

OnBleDeviceConnectionFailed = Callable[[mudraDeviceModule.MudraDevice, str], None]

OnBluetoothStateChanged = Callable[[bool], None]



class MudraDelegate(ABC):

    @abstractmethod

    def on_device_discovered(self, device: mudraDeviceModule.MudraDevice):

        pass



    @abstractmethod

    def on_mudra_device_disconnected(self, device: mudraDeviceModule.MudraDevice):

        pass



    @abstractmethod

    def on_mudra_device_disconnecting(self, device: mudraDeviceModule.MudraDevice):

        pass



    @abstractmethod

    def on_mudra_device_connected(self, device: mudraDeviceModule.MudraDevice):

        pass



    @abstractmethod

    def on_mudra_device_connecting(self, device: mudraDeviceModule.MudraDevice):

        pass



    @abstractmethod

    def on_mudra_device_connection_failed(self, device: mudraDeviceModule.MudraDevice, error: str):

        pass



    @abstractmethod

    def on_bluetooth_state_changed(self, state: bool):

        pass







# --- Implementation of BleServiceDelegate abstract methods ---

class BleServiceDelegate(ABC):

    @abstractmethod

    def on_device_discovered(self, device: BLEDevice):

        pass



    @abstractmethod

    def on_mudra_device_disconnected(self, device: BLEDevice):

        pass



    @abstractmethod

    def on_mudra_device_disconnecting(self, device: BLEDevice):

        pass



    @abstractmethod

    async def on_mudra_device_connected(self, device: BLEDevice):

        pass



    @abstractmethod

    def on_mudra_device_connecting(self, device: BLEDevice):

        pass



    @abstractmethod

    def on_mudra_device_connection_failed(self, device: BLEDevice, error: str):

        pass



    @abstractmethod

    def on_bluetooth_state_changed(self, state: bool):

        pass



    @abstractmethod

    async def on_ble_characteristic_discovered(self, device: BLEDevice, characteristic_uuid: MudraCharacteristicUUID):

        pass



    @abstractmethod

    def on_charging_state_changed(self, device_address: str, is_charging: bool):

        pass



    @abstractmethod

    def on_data_received(self, device_address: str, data: bytes):

        pass



    @abstractmethod

    def on_battery_level_changed(self, device_address: str, level: int):

        pass



    @abstractmethod

    def on_sensor_status_received(self, device_address: str, sensor_type: SensorTypes, status: bytes):
        pass

    @abstractmethod
    def on_storage_record_state_received(self, device_address: str, status: bytes):
        pass

    @abstractmethod
    def on_storage_record_error_received(self, device_address: str, status: BtCmdStatus):
        pass

    @abstractmethod
    def on_storage_next_file_num_received(self, device_address: str, data: bytes):
        pass

    @abstractmethod
    def on_command_error_received(
        self, device_address: str, cmd_id: BtCmdId, status: BtCmdStatus
    ):
        pass

    @abstractmethod
    def on_ping_response_received(self, device_address: str):
        pass

    @abstractmethod
    def on_device_info_received(self, device_address: str, data: bytes):
        pass

    @abstractmethod
    def on_firmware_version_received(self, device_address: str, data: bytes):
        pass


# --- Implementation of CdcServiceDelegate abstract methods ---
# Mirrors BleServiceDelegate's lifecycle/data method names so a future
# transport-aware caller (e.g. Mudra) can implement both with matching shapes,
# but is kept as its own ABC — CDC has no BLE characteristics/battery GATT
# notifications, and command replies are ASCII lines rather than binary
# status frames.
class CdcServiceDelegate(ABC):

    @abstractmethod
    def on_device_discovered(self, device: CdcDevice):
        pass

    @abstractmethod
    def on_mudra_device_connecting(self, device: CdcDevice):
        pass

    @abstractmethod
    async def on_mudra_device_connected(self, device: CdcDevice):
        pass

    @abstractmethod
    def on_mudra_device_connection_failed(self, device: CdcDevice, error: str):
        pass

    @abstractmethod
    def on_mudra_device_disconnecting(self, device: CdcDevice):
        pass

    @abstractmethod
    def on_mudra_device_disconnected(self, device: CdcDevice):
        pass

    @abstractmethod
    def on_data_received(self, device_address: str, data: bytes):
        pass

    @abstractmethod
    def on_sensor_status_received(self, device_address: str, sensor_type: SensorTypes, status: bytes):
        pass

    @abstractmethod
    def on_command_error_received(
        self, device_address: str, cmd_id: BtCmdId, status: BtCmdStatus
    ):
        pass

    @abstractmethod
    def on_command_reply_received(self, device_address: str, line: str):
        pass

    @abstractmethod
    def on_ping_response_received(self, device_address: str):
        pass

    @abstractmethod
    def on_firmware_version_received(self, device_address: str, data: bytes):
        pass

