import asyncio
from calendar import c
import cmd
from enum import Enum
from typing import Any, Callable, Optional, Dict, List, Tuple
from bleak import BleakAdapter, BleakScanner, BleakClient
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTServiceCollection
from mudra_sdk.models.enums import FirmwareCallbacks, FirmwareDataType, MudraBLEServicesUUID, MudraCharacteristicUUID, MudraModel, SensorTypes, BtCmdId, BtCmdStatus, cmdType


from ..models.callbacks import BleServiceDelegate
from ..logging_config import get_logger

logger = get_logger(__name__)

class BleService:
    _instance = None
    _delegate: Optional[BleServiceDelegate] = None

    charging_state_true = 0x7b 
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, delegate: BleServiceDelegate):
        if not hasattr(self, '_initialized'):
            self._discovered_devices: set[Any] = set()
            self._scan_task = None
            self._scanner: Optional[BleakScanner] = None
            self._delegate = delegate
            self._connected_clients: Dict[str, BleakClient] = {}  # address -> client
            self._initialized = True

    ### ----------------------- Connection Methods ----------------------- ###
    
    async def connect(self, device: BLEDevice):
        logger.info(f"Connecting to device: {device.name}")
        address = device.address

        # Check if already connected
        if address in self._connected_clients:
            logger.warning(f"Device {address} is already connected")
            return
        
        try:
            # Notify connecting
            if self._delegate:
                self._delegate.on_mudra_device_connecting(device)
            
            # Create client with disconnect callback.
            client = BleakClient(device, disconnected_callback=lambda client: self._on_disconnect_callback(device))
            
            # Attempt connection
            logger.debug(f"Calling BleakClient.connect() for {address}")
            await client.connect()
            
            # Store the connected client
            self._connected_clients[address] = client
            device.client = client 
            
            # Discover services
            logger.debug(f"Discovering services for {device.name}")
            services = client.services
            
            # Notify connected
            if self._delegate:
                await self._delegate.on_mudra_device_connected(device)
            
            if not await self.init_ble_services(device, services):
                logger.error(f"Failed to initialize BLE services for {device.name} ({address})")
                await self.disconnect(device)
                if self._delegate:
                    self._delegate.on_mudra_device_connection_failed(device, "Failed to initialize BLE services")
                return 
            
            # Optionally store services in the device object
            device.services = services

            logger.info(f"Successfully connected to {device.name} ({address})")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to connect to {address}: {error_msg}")
            
            # Notify connection failed
            if self._delegate:
                self._delegate.on_mudra_device_connection_failed(device, error_msg)
            
            # Clean up if connection attempt failed
            if address in self._connected_clients:
                del self._connected_clients[address]

    async def init_ble_services(self, device: BLEDevice, services: BleakGATTServiceCollection):
        client = device.client  # Get the BleakClient from the device

        for service in services:
            service_enum = MudraBLEServicesUUID.from_value(service.uuid)
            if service_enum:
                logger.debug(f"  -> Recognized as: {service_enum.name}")

            for char in service.characteristics:
                char_enum = MudraCharacteristicUUID.from_value(char.uuid)
                logger.debug(f"    Properties: {char.properties}")

                # Check if characteristic supports notify or indicate
                can_notify = "notify" in char.properties
                can_indicate = "indicate" in char.properties

                if char_enum:
                    if self._delegate:
                        await self._delegate.on_ble_characteristic_discovered(device, char_enum)

                try:
                    match char_enum:
                        case MudraCharacteristicUUID.COMMAND_CHARACTERISTIC:
                            if can_notify or can_indicate:
                                logger.debug(f"Subscribing to notifications for COMMAND characteristic: {char.uuid}")
                                await client.start_notify(char.uuid, lambda sender, data: self._command_notification_handler(device, sender, data))

                        case MudraCharacteristicUUID.MESSAGE_CHARACTERISTIC:
                            if can_notify or can_indicate:
                                logger.debug(f"Subscribing to notifications for MESSAGE characteristic: {char.uuid}")
                                await client.start_notify(char.uuid, lambda sender, data: self._message_notification_handler(device, sender, data))

                        case MudraCharacteristicUUID.DATA_CHARACTERISTIC:
                            if can_notify or can_indicate:
                                logger.debug(f"Subscribing to notifications for DATA characteristic: {char.uuid}")
                                await client.start_notify(char.uuid, lambda sender, data: self._data_notification_handler(device, sender, data))

                        case MudraCharacteristicUUID.BATTERY_CHARACTERISTIC:
                            if can_notify or can_indicate:
                                logger.debug(f"Subscribing to notifications for BATTERY characteristic: {char.uuid}")
                                await client.start_notify(char.uuid, lambda sender, data: self._battery_notification_handler(device, sender, data))
                            logger.debug(f"Reading BATTERY characteristic: {char.uuid}")
                            try:
                                value = await client.read_gatt_char(char.uuid)
                                self._battery_notification_handler(device, char.uuid, value)
                            except Exception as e:
                                logger.error(f"Failed to read BATTERY characteristic {char.uuid}: {e}")

                        case MudraCharacteristicUUID.BATTERY_POWER_STATE_CHARACTERISTIC:
                            if can_notify or can_indicate:
                                logger.debug(f"Subscribing to notifications for BATTERY POWER STATE characteristic: {char.uuid}")
                                await client.start_notify(char.uuid, lambda sender, data: self._charging_notification_handler(device, sender, data))
                            logger.debug(f"Reading BATTERY POWER STATE characteristic: {char.uuid}")
                            try:
                                value = await client.read_gatt_char(char.uuid)
                                self._charging_notification_handler(device, char.uuid, value)
                            except Exception as e:
                                logger.error(f"Failed to read BATTERY POWER STATE characteristic {char.uuid}: {e}")
                        case _:
                            if char_enum:
                                logger.debug(f"No notification handler for: {char_enum.name}")
                            else:
                                logger.debug(f"Unrecognized characteristic: {char.uuid}")

                except Exception as e:
                    logger.error(f"Failed to subscribe/read {char.uuid}: {e}")
                    return False
        return True

    # Notification handler examples
    def _command_notification_handler(self, device: BLEDevice, sender: int, data: bytearray):
        """Handle COMMAND characteristic notifications."""
        firmware_callback = FirmwareCallbacks.from_data(data)
        match firmware_callback:
            case FirmwareCallbacks.EMG_STATUS:
                self._delegate.on_sensor_status_received(device.address, SensorTypes.EMG, bytes(data))
            case FirmwareCallbacks.H_IMU_STATUS:
                self._delegate.on_sensor_status_received(device.address, SensorTypes.H_IMU, bytes(data))
            case FirmwareCallbacks.F_IMU_STATUS:
                self._delegate.on_sensor_status_received(device.address, SensorTypes.F_IMU, bytes(data))
            case FirmwareCallbacks.PPG_STATUS:
                self._delegate.on_sensor_status_received(device.address, SensorTypes.PPG, bytes(data))
            case FirmwareCallbacks.STORAGE_RECORD_STATE:
                self._delegate.on_storage_record_state_received(device.address, bytes(data))
            case FirmwareCallbacks.STORAGE_RECORD_ERROR:
                # [0xF0, 0x90, RECORD_ERROR, status] — async abort (e.g. SD write fail)
                status = BtCmdStatus.from_value(data[3]) if len(data) >= 4 else None
                if status is not None:
                    self._delegate.on_command_error_received(
                        device.address, BtCmdId.STORAGE, status
                    )
                    self._delegate.on_storage_record_error_received(device.address, status)
                else:
                    logger.warning(
                        f"STORAGE_RECORD_ERROR: unknown status from {device.address}: "
                        f"{bytes(data).hex(' ')}"
                    )
            case FirmwareCallbacks.STORAGE_NEXT_FILE_NUM:
                # [0xF0, 0x90, NEXT_FILE_NUM, file_num]
                self._delegate.on_storage_next_file_num_received(device.address, bytes(data))
            case FirmwareCallbacks.PING_RESPONSE:
                self._delegate.on_ping_response_received(device.address)
            case FirmwareCallbacks.DEVICE_INFO:
                self._delegate.on_device_info_received(device.address, bytes(data))
            case FirmwareCallbacks.SYSTEM_VERSION:
                self._delegate.on_firmware_version_received(device.address, bytes(data))
            case _:
                # Status-only reply: [0xF0, cmd_id, status]
                # Covers SET/POWER acks for EMG/IMU/PPG/… and RECORD_SET errors.
                if (
                    len(data) == 3
                    and data[0] == cmdType.BT_CMD_RESPONSE_HEADER.value_int
                ):
                    cmd_id = BtCmdId.from_value(data[1])
                    status = BtCmdStatus.from_value(data[2])
                    if cmd_id is not None and status is not None and status != BtCmdStatus.OK:
                        self._delegate.on_command_error_received(
                            device.address, cmd_id, status
                        )
                        if cmd_id == BtCmdId.STORAGE:
                            self._delegate.on_storage_record_error_received(
                                device.address, status
                            )
                        return
                    if cmd_id is not None and status == BtCmdStatus.OK:
                        # Successful status-only ack — not an error; ignore quietly.
                        return
                logger.warning(f"Unknown firmware callback received from {device.address}: {bytes(data).hex(' ')}")

    def _message_notification_handler(self, device: BLEDevice, sender: int, data: bytearray):
        """Handle MESSAGE characteristic notifications."""
        logger.debug(f"MESSAGE notification from {sender} (device {device.address}): {data.hex()}")

    def _data_notification_handler(self, device: BLEDevice, sender: int, data: bytearray):
        """Handle DATA characteristic notifications (unified sensor stream)."""
        if self._delegate:
            self._delegate.on_data_received(device.address, bytes(data))

    def _battery_notification_handler(self, device: BLEDevice, sender: int, data: bytearray):
        """Handle BATTERY characteristic notifications."""
        battery_level = int(data[0]) if len(data) > 0 else 0
        if self._delegate:
            self._delegate.on_battery_level_changed(device.address, battery_level)

    def _charging_notification_handler(self, device: BLEDevice, sender: int, data: bytearray):
        """Handle BATTERY POWER STATE characteristic notifications."""
        is_charging = data[0] == self.charging_state_true
        if self._delegate:
            self._delegate.on_charging_state_changed(device.address, is_charging)

    
    async def disconnect(self, device: BLEDevice):
        address = device.address
        
        # Check if device is connected
        if address not in self._connected_clients:
            logger.warning(f"Device {address} is not connected")
            return

        try:
            # Notify disconnecting
            if self._delegate:
                self._delegate.on_mudra_device_disconnecting(device)
            
            client = self._connected_clients[address]

            # If it's already disconnected (e.g. due to unexpected disconnect),
            # skip calling disconnect() to avoid spurious errors.
            if getattr(client, "is_connected", False):
                # Disconnect
                await client.disconnect()
            
            # Remove from connected clients
            del self._connected_clients[address]
            device.client = None  # Clear client reference if stored
            
            # Notify disconnected
            if self._delegate:
                self._delegate.on_mudra_device_disconnected(device)
            
            logger.info(f"Successfully disconnected from {device.name} ({address})")
            
        except Exception as e:
            if address in self._connected_clients:
                del self._connected_clients[address]
            device.client = None

    def _on_disconnect_callback(self, device: BLEDevice):
        """Internal callback triggered when device disconnects unexpectedly."""
        address = device.address
        
        logger.warning(f"Device {address} disconnected unexpectedly")
        
        # Clean up
        if address in self._connected_clients:
            del self._connected_clients[address]
            device.client = None
        
        # Notify delegate
        if self._delegate:
            self._delegate.on_mudra_device_disconnected(device)

    def is_connected(self, device: BLEDevice) -> bool:
        """Check if a device is currently connected."""
        address = device.address
        if address not in self._connected_clients:
            return False
        
        client = self._connected_clients[address]
        return client.is_connected

    async def disconnect_all(self):
        """Disconnect all connected devices."""
        devices_to_disconnect = list(self._connected_clients.keys())
        
        for address in devices_to_disconnect:
            client = self._connected_clients[address]
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting {address}: {e}")
            finally:
                if address in self._connected_clients:
                    del self._connected_clients[address]


    async def update_configuration(self, device: BLEDevice, enable: bool, data_type: FirmwareDataType):
        # `device` here is actually the MudraDevice/MudraPro/MudraUltimate
        # instance (see Mudra.update_configuration, which forwards `self`
        # through unchanged) — `_cdc_power_command` resolves the ENABLE_*
        # command from *this device's own* command table (self.CMD), so the
        # right one of ProFirmwareCommand/UltimateFirmwareCommand is used.
        # ENABLE_* power templates are byte-identical across both anyway.
        firmware_command = device._cdc_power_command(data_type)

        if firmware_command is None:
            return

        cmd = bytearray(firmware_command.id)
        # Power templates end with STOP(0) / START(1) action byte.
        if len(cmd) >= 3:
            cmd[2] = 0x01 if enable else 0x00
        await self.send_general_command(device, bytes(cmd))

    async def send_general_command(self, device: BLEDevice, command: bytes):
        try:
            client = device.client
            if client:
                logger.debug(f"Sending general command: {command.hex()}")
                await client.write_gatt_char(MudraCharacteristicUUID.COMMAND_CHARACTERISTIC.value, command)
            else:
                logger.warning(f"Device {device.address} is not connected")
        except Exception as e:
            logger.error(f"Error sending generic command to {device.address}: {e}")


    ### ----------------------- Scan Methods ----------------------- ###
    @property
    def _is_scanning(self) -> bool:
        """Check if currently scanning for devices."""
        return self._scan_task is not None and not self._scan_task.done()

    async def scan(self):
        """Start scanning for BLE devices."""
        if self._is_scanning:
            return
        logger.info("Starting scan")
        self._discovered_devices.clear()
        self._scan_task = asyncio.create_task(self._scan_loop())

    async def stop_scanning(self):
        """Stop scanning for BLE devices."""
        if not self._is_scanning:
            return
        logger.info("Stopping scan")
        
        # Cancel the scan task
        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
        
        # Stop the scanner if it exists
        if self._scanner:
            try:
                await self._scanner.stop()
            except Exception:
                pass
            finally:
                self._scanner = None
        
        self._scan_task = None

    async def _scan_loop(self):
        """Internal method that performs the actual scanning."""
        try:
            self._scanner = BleakScanner(detection_callback=self._on_device_detected)
            
            await self._scanner.start()
            logger.info("Scan started successfully")
            
            # Keep scanning until cancelled
            while True:
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info("Scan cancelled")
            if self._scanner:
                try:
                    await self._scanner.stop()
                except Exception:
                    pass
            raise
        except Exception as e:
            logger.error(f"Error during scan: {e}")
            raise
        finally:
            self._scanner = None
            self._scan_task = None

    def _on_device_detected(self, device: BLEDevice, advertisement_data):
        """Internal callback when a BLE device is detected."""
        if self._delegate:
            try:
                model = MudraModel.from_ble_name(device.name)
                if model is not None:
                    # Use address as identifier, since address is unique per BLE device
                    if device.address not in self._discovered_devices:
                        self._discovered_devices.add(device.address)
                        # Stashed on the bleak object itself (same pattern as
                        # `device.client` in connect() above) so downstream
                        # code (Mudra._create_device) knows which subclass to
                        # build without re-deriving it from the name.
                        self._delegate.on_device_discovered(device)
            except Exception as e:
                logger.error(f"Error processing device {device.address}: {e}")

    async def get_connected_devices(self, service_uuids: Optional[List[str]] = None) -> List[BLEDevice]:
        uuids = service_uuids or [MudraBLEServicesUUID.COMMAND_SERVICE.value]
        try:
            adapter = await BleakAdapter.get()
            return await adapter.get_connected_devices(service_uuids=uuids)
        except Exception as e:
            logger.warning(f"get_connected_devices: adapter unavailable ({e}); returning empty list")
            return []