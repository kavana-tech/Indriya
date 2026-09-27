import asyncio
import struct
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple
from bleak.backends.device import BLEDevice

from mudra_sdk.models.data_recorder import DataRecorder
from mudra_sdk.models.license_manager import LicenseManager
from mudra_sdk.models.packet_loss_detector import PacketLossWindow
from mudra_sdk.models.cdc_device import CdcDevice
from mudra_sdk.models.enums import (
    BtCmdId,
    BtCmdStatus,
    ProEMGODR,
    EmgRes,
    EventType,
    ProFirmwareCommand,
    FirmwareDataType,
    IMUODR,
    PPGODR,
    IMUAccRange,
    IMUGyrRange,
    LicenseTier,
    MudraModel,
    PPGChannelCount,
    RecordingDataType,
    SensorTypes,
)
import mudra_sdk.models.mudra as mudraModule
import mudra_sdk.models.computation_wrapper as computationWrapperModule
import mudra_sdk.models.firmware_protocol as fp
from mudra_sdk.service.ble_service import MudraBLEServicesUUID, MudraCharacteristicUUID
from ..logging_config import get_logger

logger = get_logger(__name__)

# ---- CDC (USB serial) ASCII command tokens ---------------------------------
#
# Token strings themselves now come from the native ProCdcCommands/
# UltimateCdcCommands lookup (mudra_sdk/core/Computation/*CdcCommands.h, via
# ComputationWrapper's get_pro_cdc_command_token/get_ultimate_cdc_command_token)
# — see the `_cdc_token`/`_cdc_send` helpers below. That's the single source
# of truth for CDC vs. BLE-oriented naming differences (combined status
# queries, packet-loss test-mode's missing underscore, shortened
# battery/LED/BT tokens, etc.), verified there against firmware's
# src/device_layer/usb_cdc/cdc_commands.c — nothing CDC-token-specific is
# hardcoded in Python anymore. `_cdc_power_command()` below resolves the
# per-model ENABLE_* command for a data type (was a module-level dict before
# commands were split per-model — now needs `self.CMD`, so it's a method).

# Response framing: [0xF0, cmd_id, feature, payload...]
_STATUS_HDR_LEN = 3
_EMG_STATUS_PAYLOAD_LEN = 4   # enabled, odr u16 LE, resolution_bits
_IMU_STATUS_PAYLOAD_LEN = 6  # enabled, odr u16 LE, accel_g, gyro u16 LE
_PPG_STATUS_PAYLOAD_LEN = 4  # enabled, odr u16 LE, channel_count
_RECORD_STATUS_PAYLOAD_LEN = 6  # active, emg, ppg, imu_hand, imu_ring, file_num

# BT_STORAGE_RECORD_SET request is [cmd, feature, 4 sensor flags, is_test,
# file_num, duration_min(u16 LE), utc_ts(u32 LE), description...] — leave
# room under BT_CMD_MAX_LEN (96).
_STORAGE_RECORD_SET_FIXED_LEN = 14
_STORAGE_RECORD_DESC_MAX_LEN = 96 - _STORAGE_RECORD_SET_FIXED_LEN
_STORAGE_RECORD_DURATION_MAX_MIN = 0xFFFF
_STORAGE_RECORD_UTC_TS_MAX = 0xFFFFFFFF

# BT_SYS_DEVICE_INFO is the one BLE reply with NO feature byte on the wire —
# firmware sends [0xF0, cmd_id, payload...] (2-byte header, not 3) — so it
# can't use _STATUS_HDR_LEN/_status_payload() like every other status reply.
_DEVICE_INFO_HDR_LEN = 2
_DEVICE_INFO_FIXED_LEN = 14  # tier u8, valid u8, now/floor/expires_at u32 LE each
_DEVICE_INFO_STRUCT_FMT = "<BBIII"  # tier, valid, now, floor, expires_at (14 bytes; serial follows raw)
# The serial field's width isn't fixed across products/firmware: mudra_pro
# sends a 13-byte serial (27-byte payload), mudra_ultimate widened it to 15
# (29-byte payload) without bumping any header/version field -- see
# mudra_ultimate's bt_command_manager.c BT_SYS_DEVICE_INFO comment ("Pro_SDK
# must change in lockstep"). Rather than hardcode one width and break the
# other product, derive it from the frame length actually received.
_DEVICE_INFO_SERIAL_LEN_MIN = 13
_DEVICE_INFO_SERIAL_LEN_MAX = 15

# BT_SYS_VERSION is likewise a bare [0xF0, cmd_id] header (no feature byte) —
# see FirmwareCallbacks.SYSTEM_VERSION in enums.py.
_FIRMWARE_VERSION_HDR_LEN = 2
_FIRMWARE_VERSION_PAYLOAD_LEN = 4  # major, minor, patch, tweak — one byte each


@dataclass
class EmgStatus:
    """Firmware ``emg_status_t`` — EMG unified status reply payload.

    ``odr_sps`` is a ProEMGODR member on MudraPro, a UltimateEMGODR member
    on MudraUltimate (different AFEs, different valid rate sets — see
    MudraDevice.EMG_ODR_ENUM)."""

    enabled: bool
    odr_sps: "ProEMGODR"
    resolution_bits: EmgRes


@dataclass
class PpgStatus:
    """Firmware ``ppg_status_t`` — PPG unified status reply payload."""

    enabled: bool
    odr_hz: PPGODR
    channel_count: PPGChannelCount


@dataclass
class ImuStatus:
    """Firmware ``imu_status_t`` — H_IMU / F_IMU unified status reply payload."""

    enabled: bool
    odr_hz: IMUODR
    accel_range_g: IMUAccRange
    gyro_range_dps: IMUGyrRange


@dataclass
class RecordStatus:
    """Firmware ``peripherals_record_status_t`` — SD card recording state."""

    active: bool
    emg: bool
    ppg: bool
    imu_hand: bool
    imu_ring: bool
    file_num: int


@dataclass
class LicenseDeviceInfo:
    tier: LicenseTier
    valid: bool
    now: int
    floor: int
    expires_at: int
    serial: str


@dataclass
class FirmwareVersion:
    """Firmware ``BT_SYS_VERSION`` reply — ``[maj, min, patch, tweak]``, one
    raw byte each (see ``bt_command_manager.c``'s ``handle_system()``,
    case ``BT_SYS_VERSION``, and the firmware's ``VERSION`` file)."""

    major: int
    minor: int
    patch: int
    tweak: int

    @property
    def version_string(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}.{self.tweak}"


OnEmgStatusReceivedCallback = Callable[[EmgStatus], None]
OnImuStatusReceivedCallback = Callable[[ImuStatus], None]
OnPpgStatusReceivedCallback = Callable[[PpgStatus], None]
OnRecordStatusReceivedCallback = Callable[[RecordStatus], None]
OnRecordErrorReceivedCallback = Callable[[BtCmdStatus], None]
OnNextFileNumReceivedCallback = Callable[[int], None]
OnCommandErrorReceivedCallback = Callable[[BtCmdId, BtCmdStatus], None]
OnPingResponseCallback = Callable[[], None]
OnLicenseDeviceInfoReceivedCallback = Callable[[LicenseDeviceInfo], None]
OnFirmwareVersionReceivedCallback = Callable[[FirmwareVersion], None]


class MudraDevice(BLEDevice):
    """Shared base for MudraPro / MudraUltimate. Most of the protocol and all
    transport/status-parsing plumbing is identical across both hardware
    models — see MudraPro/MudraUltimate at the end of this file for the
    handful of commands that differ. MODEL/EMG_CHANNEL_COUNT default to Pro's
    values so a bare MudraDevice() (shouldn't normally be constructed
    directly — Mudra._create_device() picks the right subclass) still behaves
    like the pre-Ultimate SDK."""

    MODEL: "MudraModel" = MudraModel.PRO
    EMG_CHANNEL_COUNT: int = 3
    # The command table this device speaks — a fully independent enum per
    # product (ProFirmwareCommand / UltimateFirmwareCommand in enums.py),
    # not a shared enum with a device-branch parameter. Shared methods below
    # reference commands via `self.CMD.xxx` so one method body works for
    # both subclasses, each resolving to its own product's byte template.
    CMD = ProFirmwareCommand
    # EMG ODR value set — also per-product, but for a different reason than
    # CMD: the command byte (EMG_ODR = 0x01) is identical on both, but each
    # product's EMG AFE supports different discrete rates (ADS1293 on Pro:
    # 200-6400 SPS; ADS1298 on Ultimate: 500-4000 SPS) — see ProEMGODR /
    # UltimateEMGODR in enums.py. set_emg_odr() takes whichever enum matches
    # self.EMG_ODR_ENUM; _on_emg_status_received() decodes STATUS replies
    # through it too.
    EMG_ODR_ENUM = ProEMGODR

    def __init__(self, ble_device: Optional[BLEDevice] = None, cdc_device: Optional[CdcDevice] = None):
        if (ble_device is None) == (cdc_device is None):
            raise ValueError("MudraDevice requires exactly one of ble_device or cdc_device")

        self.model: MudraModel = self.MODEL

        if cdc_device is not None:
            super().__init__(cdc_device.address, cdc_device.name, None)
            self.transport = "cdc"
            self._cdc_device = cdc_device
        else:
            super().__init__(ble_device.address, ble_device.name, ble_device.details)
            self.transport = "ble"
            self._cdc_device = None

        # Initialize characteristic status
        self._characteristic_status = {
            MudraCharacteristicUUID.COMMAND_CHARACTERISTIC: False,
            MudraCharacteristicUUID.MESSAGE_CHARACTERISTIC: False,
            MudraCharacteristicUUID.DATA_CHARACTERISTIC: False,
            MudraCharacteristicUUID.BATTERY_CHARACTERISTIC: False,
            MudraCharacteristicUUID.BATTERY_POWER_STATE_CHARACTERISTIC: False,
        }

        # Initialize service status
        self._service_status = {
            MudraBLEServicesUUID.COMMAND_SERVICE: False,
            MudraBLEServicesUUID.BATTERY_SERVICE: False,
            MudraBLEServicesUUID.INFORMATION_SERVICE: False,
        }

        self._state_enabled = {
            FirmwareDataType.emg: False,
            FirmwareDataType.imuH: False,
            FirmwareDataType.imuF: False,
            FirmwareDataType.ppg: False,
        }

        ### ----------------------- Data Recorder ----------------------- ###
        self._data_recorder = DataRecorder()

        ### ----------------------- License Manager ----------------------- ###
        self._license_manager = LicenseManager(self)

        ### ----------------------- Battery poll (CDC only) -------------------- ###
        # BLE gets battery/charging pushed for free via GATT Battery Service
        # notifications (BATTERY_CHARACTERISTIC/BATTERY_POWER_STATE_CHARACTERISTIC,
        # see on_battery_level_changed/on_charging_state_changed below); CDC has
        # no equivalent push, only pollable BAT_SOC?/BAT_CHG? — see on_cdc_ready.
        self._battery_poll_task: Optional[asyncio.Task] = None

        ### ----------------------- Parameters Callbacks ----------------------- ###
        self._on_charging_state_changed: Optional[computationWrapperModule.OnChargingStateChangedCallback] = None
        self._on_battery_level_changed: Optional[computationWrapperModule.OnBatteryLevelChangedCallback] = None
        self._on_emg_ready: Optional[computationWrapperModule.OnEmgReadyCallback] = None
        self._on_emg_ready_ref = None
        self._on_imu_h_ready: Optional[computationWrapperModule.OnImuReadyCallback] = None
        self._on_imu_f_ready: Optional[computationWrapperModule.OnImuReadyCallback] = None
        self._on_ppg_ready: Optional[computationWrapperModule.OnPpgReadyCallback] = None
        self._on_ppg_ready_ref = None
        self._on_emg_status: Optional[OnEmgStatusReceivedCallback] = None
        self._on_h_imu_status: Optional[OnImuStatusReceivedCallback] = None
        self._on_f_imu_status: Optional[OnImuStatusReceivedCallback] = None
        self._on_ppg_status: Optional[OnPpgStatusReceivedCallback] = None
        self._on_record_status: Optional[OnRecordStatusReceivedCallback] = None
        self._on_record_error: Optional[OnRecordErrorReceivedCallback] = None
        self._on_next_file_num: Optional[OnNextFileNumReceivedCallback] = None
        self._on_command_error: Optional[OnCommandErrorReceivedCallback] = None
        self._on_ping_response: Optional[OnPingResponseCallback] = None
        self._on_license_device_info: Optional[OnLicenseDeviceInfoReceivedCallback] = None
        self._on_firmware_version: Optional[OnFirmwareVersionReceivedCallback] = None

        ### ----------------------- Packet-loss windows (one per sensor) ------ ###
        # Cumulative counting itself (raw, scale-free) lives in the native
        # core (see ComputationManager::GetPacketLossStats) and runs
        # automatically off the incoming byte stream, independent of whether
        # a ready-callback is registered — that's what keeps this entirely
        # separate from the normal set_on_*_ready path. These PacketLossWindow
        # instances just turn a periodic poll of the native counters (via
        # sample_*_packet_loss(), called by the caller on its own schedule)
        # into a windowed percentage + live rate.
        self._emg_packet_loss = PacketLossWindow()
        self._h_imu_packet_loss = PacketLossWindow()
        self._f_imu_packet_loss = PacketLossWindow()
        self._ppg_packet_loss = PacketLossWindow()

        ### ----------------------- Computation Wrapper ----------------------- ###
        self._computation_wrapper = computationWrapperModule.ComputationWrapper()
        # EMG channel count is fixed by hardware model (3 on Pro, 8 on
        # Ultimate) — unlike PPG's channel count, it's never negotiated via a
        # STATUS reply, so it's pushed once here rather than from
        # _on_emg_status_received.
        self._computation_wrapper.set_parser_emg_channel_count(self.EMG_CHANNEL_COUNT)

        ### ----------------------- Sensor status (last STATUS reply) --------- ###
        self._emg_status: Optional[EmgStatus] = None
        self._h_imu_status: Optional[ImuStatus] = None
        self._f_imu_status: Optional[ImuStatus] = None
        self._ppg_status: Optional[PpgStatus] = None
        self._record_status: Optional[RecordStatus] = None
        self._next_file_num: Optional[int] = None
        self._license_device_info: Optional[LicenseDeviceInfo] = None
        self._firmware_version: Optional[FirmwareVersion] = None


    async def connect(self):
        await mudraModule.Mudra().connect(self)

    async def _provision_license(self) -> None:
        """Best-effort license provisioning right after connect (see
        :mod:`mudra_sdk.auth`): if signed in, fetches a token from the
        server and sends it to this device; if signed out, does nothing.
        Never raises — a licensing hiccup must not fail a connection that
        already succeeded."""
        try:
            from .. import auth
            await auth.provision_device(self)
        except Exception as exc:  # noqa: BLE001 — provisioning is best-effort
            logger.error(f"provisioning failed: {exc}")

    async def _provision_user_id(self) -> None:
        """Best-effort user_id provisioning right after connect (see
        :mod:`mudra_sdk.auth`): if signed in, sends the account's uref to
        this device as its user_id; if signed out, does nothing. Never
        raises — same reasoning as :meth:`_provision_license`."""
        try:
            from .. import auth
            await auth.provision_user_id(self)
        except Exception as exc:  # noqa: BLE001 — provisioning is best-effort
            logger.error(f"user_id provisioning failed: {exc}")

    async def disconnect(self):
        await mudraModule.Mudra().disconnect(self)

    def handle_disconnection(self):
        self._license_manager.stop()
        if self._battery_poll_task is not None:
            self._battery_poll_task.cancel()
            self._battery_poll_task = None
        for key in self._characteristic_status:
            self._characteristic_status[key] = False
        for key in self._service_status:
            self._service_status[key] = False
        for key in self._state_enabled:
            self._state_enabled[key] = False
        self._computation_wrapper.set_on_emg_ready(None)
        self._on_emg_ready = None
        self._computation_wrapper.set_on_imu_h_ready(None)
        self._on_imu_h_ready = None
        self._computation_wrapper.set_on_imu_f_ready(None)
        self._on_imu_f_ready = None
        self._computation_wrapper.set_on_ppg_ready(None)
        self._on_ppg_ready = None
        self._on_emg_status = None
        self._on_h_imu_status = None
        self._on_f_imu_status = None
        self._on_ppg_status = None
        self._on_record_status = None
        self._on_record_error = None
        self._on_next_file_num = None
        self._on_command_error = None
        self._on_ping_response = None
        self._on_license_device_info = None
        self._on_firmware_version = None
        for data_type in (
            FirmwareDataType.emg,
            FirmwareDataType.imuH,
            FirmwareDataType.imuF,
            FirmwareDataType.ppg,
        ):
            self._computation_wrapper.reset_packet_loss_stats(data_type.value)
        self._emg_packet_loss.reset()
        self._h_imu_packet_loss.reset()
        self._f_imu_packet_loss.reset()
        self._ppg_packet_loss.reset()
        self._emg_status = None
        self._h_imu_status = None
        self._f_imu_status = None
        self._ppg_status = None
        self._record_status = None
        self._next_file_num = None
        self._license_device_info = None
        self._firmware_version = None

    ### ----------------------- Ready Methods ----------------------- ###

    def on_charging_state_changed(self, is_charging: bool):
        logger.info(f"Charging state changed: {is_charging}")
        self._is_charging = is_charging
        if self._on_charging_state_changed:
            self._on_charging_state_changed(is_charging)

    def on_data_received(self, data: bytes):
        self._computation_wrapper.handle_data(data, len(data))

    def on_battery_level_changed(self, level: int):
        self._battery_level = level
        if self._on_battery_level_changed:
            self._on_battery_level_changed(level)

    def on_sensor_status_received(self, sensor_type: SensorTypes, status: bytes):
        logger.debug(f"Sensor status received: {sensor_type}, {status.hex(' ')}")
        if sensor_type == SensorTypes.EMG:
            self._on_emg_status_received(status)
        elif sensor_type == SensorTypes.H_IMU:
            self._on_h_imu_status_received(status)
        elif sensor_type == SensorTypes.F_IMU:
            self._on_f_imu_status_received(status)
        elif sensor_type == SensorTypes.PPG:
            self._on_ppg_status_received(status)

    def on_storage_record_state_received(self, status: bytes):
        logger.debug(f"Storage record state received: {status.hex(' ')}")
        self._on_record_status_received(status)

    def on_storage_record_error_received(self, status: BtCmdStatus):
        logger.error(f"Storage record error: {status.description} (0x{status.value_int:02X})")
        if self._on_record_error:
            self._on_record_error(status)

    def on_storage_next_file_num_received(self, data: bytes):
        # [0xF0, 0x90, NEXT_FILE_NUM, file_num]
        if len(data) < 4:
            logger.warning(f"Next file num: bad frame len={len(data)} data={data.hex(' ')}")
            return
        file_num = data[3]
        self._next_file_num = file_num
        logger.info(f"Next available SD file_num: {file_num}")
        if self._on_next_file_num:
            self._on_next_file_num(file_num)

    def on_command_error_received(self, cmd_id: BtCmdId, status: BtCmdStatus):
        logger.error(
            f"Command error: {cmd_id.description} -> {status.description} "
            f"(0x{status.value_int:02X})"
        )
        if self._on_command_error:
            self._on_command_error(cmd_id, status)

    def on_ping_response_received(self) -> None:
        if self._on_ping_response:
            self._on_ping_response()

    def on_device_info_received(self, status: bytes) -> None:
        self._on_license_device_info_received(status)

    def on_firmware_version_received(self, status: bytes) -> None:
        self._parse_firmware_version(status)

    def _status_payload(self, data: bytes, expected_len: int) -> Optional[bytes]:
        """Return payload after ``[0xF0, cmd_id, feature]`` if length matches STATUS size."""
        if len(data) < _STATUS_HDR_LEN + expected_len:
            return None
        return data[_STATUS_HDR_LEN : _STATUS_HDR_LEN + expected_len]

    def _on_emg_status_received(self, status: bytes) -> None:
        payload = self._status_payload(status, _EMG_STATUS_PAYLOAD_LEN)
        if payload is None:
            logger.warning(f"EMG status: bad frame len={len(status)} data={status.hex(' ')}")
            return
        enabled, odr_sps, resolution_bits = struct.unpack("<BHB", payload)
        if enabled not in (0, 1):
            logger.warning(f"EMG status: bad enabled={enabled} payload={payload.hex(' ')}")
            return
        odr = self.EMG_ODR_ENUM.from_value(odr_sps)
        res = EmgRes.from_value(resolution_bits)
        if odr is None or res is None:
            logger.warning(
                f"EMG status: unknown enum values "
                f"odr={odr_sps} res={resolution_bits} payload={payload.hex(' ')}"
            )
            return
        self._emg_status = EmgStatus(
            enabled=bool(enabled),
            odr_sps=odr,
            resolution_bits=res,
        )
        self._computation_wrapper.set_parser_emg_resolution(res.bits)
        logger.debug(
            f"EMG status: enabled={self._emg_status.enabled} "
            f"odr={self._emg_status.odr_sps.value_int} "
            f"res={self._emg_status.resolution_bits.bits} bits"
        )
        if self._on_emg_status:
            self._on_emg_status(self._emg_status)

    def _on_h_imu_status_received(self, status: bytes) -> None:
        parsed = self._parse_imu_status(status)
        if parsed is None:
            return
        self._h_imu_status = parsed
        self._computation_wrapper.set_parser_imu_h_ranges(
            parsed.accel_range_g.value_int, parsed.gyro_range_dps.value_int
        )
        logger.debug(
            f"H_IMU status: enabled={parsed.enabled} "
            f"odr={parsed.odr_hz.value_int} Hz "
            f"acc={parsed.accel_range_g.value_int} g "
            f"gyr={parsed.gyro_range_dps.value_int} dps"
        )
        if self._on_h_imu_status:
            self._on_h_imu_status(parsed)

    def _on_f_imu_status_received(self, status: bytes) -> None:
        parsed = self._parse_imu_status(status)
        if parsed is None:
            return
        self._f_imu_status = parsed
        self._computation_wrapper.set_parser_imu_f_ranges(
            parsed.accel_range_g.value_int, parsed.gyro_range_dps.value_int
        )
        logger.debug(
            f"F_IMU status: enabled={parsed.enabled} "
            f"odr={parsed.odr_hz.value_int} Hz "
            f"acc={parsed.accel_range_g.value_int} g "
            f"gyr={parsed.gyro_range_dps.value_int} dps"
        )
        if self._on_f_imu_status:
            self._on_f_imu_status(parsed)

    def _parse_imu_status(self, status: bytes) -> Optional[ImuStatus]:
        payload = self._status_payload(status, _IMU_STATUS_PAYLOAD_LEN)
        if payload is None:
            logger.warning(f"IMU status: bad frame len={len(status)} data={status.hex(' ')}")
            return None
        enabled, odr_hz, accel_range_g, gyro_range_dps = struct.unpack("<BHBH", payload)
        if enabled not in (0, 1):
            logger.warning(f"IMU status: bad enabled={enabled} payload={payload.hex(' ')}")
            return None
        odr = IMUODR.from_value(odr_hz)
        acc = IMUAccRange.from_value(accel_range_g)
        gyr = IMUGyrRange.from_value(gyro_range_dps)
        if odr is None or acc is None or gyr is None:
            logger.warning(
                f"IMU status: unknown enum values "
                f"odr={odr_hz} acc={accel_range_g} gyr={gyro_range_dps} "
                f"payload={payload.hex(' ')}"
            )
            return None
        return ImuStatus(
            enabled=bool(enabled),
            odr_hz=odr,
            accel_range_g=acc,
            gyro_range_dps=gyr,
        )

    def _on_ppg_status_received(self, status: bytes) -> None:
        payload = self._status_payload(status, _PPG_STATUS_PAYLOAD_LEN)
        if payload is None:
            logger.warning(f"PPG status: bad frame len={len(status)} data={status.hex(' ')}")
            return
        enabled, odr_hz, channel_count = struct.unpack("<BHB", payload)
        if enabled not in (0, 1):
            logger.warning(f"PPG status: bad enabled={enabled} payload={payload.hex(' ')}")
            return
        odr = PPGODR.from_value(odr_hz)
        channels = PPGChannelCount.from_value(channel_count)
        if odr is None or channels is None:
            logger.warning(
                f"PPG status: unknown enum values "
                f"odr={odr_hz} channels={channel_count} payload={payload.hex(' ')}"
            )
            return
        self._ppg_status = PpgStatus(
            enabled=bool(enabled),
            odr_hz=odr,
            channel_count=channels,
        )
        # Stride is channel_count × 3 B (ODR is not used for DATA decode).
        self._computation_wrapper.set_parser_ppg_channel_count(channels.value_int)
        logger.debug(
            f"PPG status: enabled={self._ppg_status.enabled} "
            f"odr={self._ppg_status.odr_hz.value_int} Hz "
            f"channels={self._ppg_status.channel_count.value_int}"
        )
        if self._on_ppg_status:
            self._on_ppg_status(self._ppg_status)

    def _on_record_status_received(self, status: bytes) -> None:
        payload = self._status_payload(status, _RECORD_STATUS_PAYLOAD_LEN)
        if payload is None:
            logger.warning(f"Record status: bad frame len={len(status)} data={status.hex(' ')}")
            return
        active, emg, ppg, imu_hand, imu_ring, file_num = struct.unpack("6B", payload)
        for label, flag in (
            ("active", active),
            ("emg", emg),
            ("ppg", ppg),
            ("imu_hand", imu_hand),
            ("imu_ring", imu_ring),
        ):
            if flag not in (0, 1):
                logger.warning(f"Record status: bad {label}={flag} payload={payload.hex(' ')}")
                return
        self._record_status = RecordStatus(
            active=bool(active),
            emg=bool(emg),
            ppg=bool(ppg),
            imu_hand=bool(imu_hand),
            imu_ring=bool(imu_ring),
            file_num=file_num,
        )
        logger.debug(
            f"Record status: active={self._record_status.active} "
            f"emg={self._record_status.emg} ppg={self._record_status.ppg} "
            f"imu_h={self._record_status.imu_hand} imu_f={self._record_status.imu_ring} "
            f"file={self._record_status.file_num}"
        )
        if self._on_record_status:
            self._on_record_status(self._record_status)

    def _on_license_device_info_received(self, status: bytes) -> None:
        # Bare [0xF0, cmd_id] header (2 bytes) — BT_SYS_DEVICE_INFO never
        # echoes a feature byte, unlike every _status_payload() case above.
        serial_len = len(status) - _DEVICE_INFO_HDR_LEN - _DEVICE_INFO_FIXED_LEN
        if not (_DEVICE_INFO_SERIAL_LEN_MIN <= serial_len <= _DEVICE_INFO_SERIAL_LEN_MAX):
            logger.warning(f"Device info: bad frame len={len(status)} data={status.hex(' ')}")
            return
        payload = status[_DEVICE_INFO_HDR_LEN:]
        tier_raw, valid, now, floor, expires_at = struct.unpack(_DEVICE_INFO_STRUCT_FMT, payload[:14])
        serial_raw = payload[14 : 14 + serial_len]
        serial = serial_raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")
        tier = LicenseTier.from_value(tier_raw)
        if tier is None:
            logger.warning(f"Device info: unknown tier={tier_raw} payload={payload.hex(' ')}")
            return
        self._license_device_info = LicenseDeviceInfo(
            tier=tier,
            valid=bool(valid),
            now=now,
            floor=floor,
            expires_at=expires_at,
            serial=serial,
        )
        logger.debug(
            f"Device info: tier={tier.name} valid={self._license_device_info.valid} "
            f"now={now} floor={floor} expires_at={expires_at} serial={serial!r}"
        )
        self._license_manager.on_device_info(self._license_device_info)
        if self._on_license_device_info:
            self._on_license_device_info(self._license_device_info)

    def _parse_firmware_version(self, status: bytes) -> None:
        # Bare [0xF0, cmd_id] header (2 bytes) — BT_SYS_VERSION never echoes
        # a feature byte, same as BT_SYS_DEVICE_INFO above.
        expected_len = _FIRMWARE_VERSION_HDR_LEN + _FIRMWARE_VERSION_PAYLOAD_LEN
        if len(status) != expected_len:
            logger.warning(f"Firmware version: bad frame len={len(status)} data={status.hex(' ')}")
            return
        major, minor, patch, tweak = status[_FIRMWARE_VERSION_HDR_LEN:]
        self._firmware_version = FirmwareVersion(major=major, minor=minor, patch=patch, tweak=tweak)
        logger.info(f"Firmware version: {self._firmware_version.version_string}")
        if self._on_firmware_version:
            self._on_firmware_version(self._firmware_version)

    ### ----------------------- Getter Methods ----------------------- ###
    def get_is_charging(self) -> bool:
        return self._is_charging

    def get_battery_level(self) -> Optional[int]:
        return self._battery_level

    def get_emg_status_info(self) -> Optional[EmgStatus]:
        return self._emg_status

    def get_h_imu_status_info(self) -> Optional[ImuStatus]:
        return self._h_imu_status

    def get_f_imu_status_info(self) -> Optional[ImuStatus]:
        return self._f_imu_status

    def get_ppg_status_info(self) -> Optional[PpgStatus]:
        return self._ppg_status

    def get_record_status_info(self) -> Optional[RecordStatus]:
        return self._record_status

    def get_next_file_num_info(self) -> Optional[int]:
        return self._next_file_num

    def get_license_device_info(self) -> Optional[LicenseDeviceInfo]:
        """Last ``BT_SYS_DEVICE_INFO`` reply, on either transport (see :class:`LicenseDeviceInfo`)."""
        return self._license_device_info

    def get_firmware_version_info(self) -> Optional[FirmwareVersion]:
        """Last ``BT_SYS_VERSION`` reply — see :class:`FirmwareVersion`."""
        return self._firmware_version

    def get_emg_packet_loss_stats(self) -> Tuple[int, int]:
        """Lifetime ``(samples_seen, samples_lost)`` from the native counter — resets with ``set_emg_test_mode``."""
        return self._computation_wrapper.get_packet_loss_stats(FirmwareDataType.emg.value)

    def get_h_imu_packet_loss_stats(self) -> Tuple[int, int]:
        return self._computation_wrapper.get_packet_loss_stats(FirmwareDataType.imuH.value)

    def get_f_imu_packet_loss_stats(self) -> Tuple[int, int]:
        return self._computation_wrapper.get_packet_loss_stats(FirmwareDataType.imuF.value)

    def get_ppg_packet_loss_stats(self) -> Tuple[int, int]:
        return self._computation_wrapper.get_packet_loss_stats(FirmwareDataType.ppg.value)

    def get_emg_packet_loss_rate_hz(self) -> float:
        return self._emg_packet_loss.rate_hz

    def get_h_imu_packet_loss_rate_hz(self) -> float:
        return self._h_imu_packet_loss.rate_hz

    def get_f_imu_packet_loss_rate_hz(self) -> float:
        return self._f_imu_packet_loss.rate_hz

    def get_ppg_packet_loss_rate_hz(self) -> float:
        return self._ppg_packet_loss.rate_hz

    def reset_emg_packet_loss_window(self) -> None:
        """Zero the windowed ('last ~1s') reading without touching the native lifetime counters."""
        self._emg_packet_loss.reset()

    def reset_h_imu_packet_loss_window(self) -> None:
        self._h_imu_packet_loss.reset()

    def reset_f_imu_packet_loss_window(self) -> None:
        self._f_imu_packet_loss.reset()

    def reset_ppg_packet_loss_window(self) -> None:
        self._ppg_packet_loss.reset()

    def sample_emg_packet_loss(self) -> float:
        """Read the native counters right now and return the windowed loss %
        over roughly the last second. Independent of set_on_emg_ready —
        call this periodically (e.g. once per UI tick) while EMG's
        packet-loss test mode is running."""
        seen, lost = self._computation_wrapper.get_packet_loss_stats(FirmwareDataType.emg.value)
        return self._emg_packet_loss.update(seen, lost)

    def sample_h_imu_packet_loss(self) -> float:
        seen, lost = self._computation_wrapper.get_packet_loss_stats(FirmwareDataType.imuH.value)
        return self._h_imu_packet_loss.update(seen, lost)

    def sample_f_imu_packet_loss(self) -> float:
        seen, lost = self._computation_wrapper.get_packet_loss_stats(FirmwareDataType.imuF.value)
        return self._f_imu_packet_loss.update(seen, lost)

    def sample_ppg_packet_loss(self) -> float:
        seen, lost = self._computation_wrapper.get_packet_loss_stats(FirmwareDataType.ppg.value)
        return self._ppg_packet_loss.update(seen, lost)

    ### ----------------------- Setter Methods ----------------------- ###

    async def set_on_charging_state_changed(self, callback: computationWrapperModule.OnChargingStateChangedCallback) -> None:
        self._on_charging_state_changed = callback

    async def set_on_battery_level_changed(self, callback: computationWrapperModule.OnBatteryLevelChangedCallback) -> None:
        self._on_battery_level_changed = callback

    async def set_on_emg_ready(self, callback: Optional[computationWrapperModule.OnEmgReadyCallback]) -> None:
        """Normal live-EMG-data path only — entirely separate from the
        packet-loss test path (see sample_emg_packet_loss). The native
        continuity check runs off the raw byte stream regardless of whether
        any ready-callback is registered here, so this never needs to wrap
        or forward through packet-loss logic."""
        self._on_emg_ready = callback
        self._computation_wrapper.set_on_emg_ready(callback)
        await self._update_state_enabled()

    async def set_on_imu_h_ready(self, callback: Optional[computationWrapperModule.OnImuReadyCallback]) -> None:
        self._on_imu_h_ready = callback
        self._computation_wrapper.set_on_imu_h_ready(callback)
        await self._update_state_enabled()

    async def set_on_imu_f_ready(self, callback: Optional[computationWrapperModule.OnImuReadyCallback]) -> None:
        self._on_imu_f_ready = callback
        self._computation_wrapper.set_on_imu_f_ready(callback)
        await self._update_state_enabled()

    async def set_on_ppg_ready(self, callback: Optional[computationWrapperModule.OnPpgReadyCallback]) -> None:
        self._on_ppg_ready = callback
        self._computation_wrapper.set_on_ppg_ready(callback)
        await self._update_state_enabled()

    async def set_on_emg_status_received(
        self, callback: Optional[OnEmgStatusReceivedCallback]
    ) -> None:
        self._on_emg_status = callback

    async def set_on_h_imu_status_received(
        self, callback: Optional[OnImuStatusReceivedCallback]
    ) -> None:
        self._on_h_imu_status = callback

    async def set_on_f_imu_status_received(
        self, callback: Optional[OnImuStatusReceivedCallback]
    ) -> None:
        self._on_f_imu_status = callback

    async def set_on_ppg_status_received(
        self, callback: Optional[OnPpgStatusReceivedCallback]
    ) -> None:
        self._on_ppg_status = callback

    async def set_on_storage_record_state_received(
        self, callback: Optional[OnRecordStatusReceivedCallback]
    ) -> None:
        self._on_record_status = callback

    async def set_on_storage_record_error_received(
        self, callback: Optional[OnRecordErrorReceivedCallback]
    ) -> None:
        self._on_record_error = callback

    async def set_on_storage_next_file_num_received(
        self, callback: Optional[OnNextFileNumReceivedCallback]
    ) -> None:
        self._on_next_file_num = callback

    async def set_on_command_error_received(
        self, callback: Optional[OnCommandErrorReceivedCallback]
    ) -> None:
        """Non-OK status-only CONFIG replies: ``[0xF0, cmd_id, status]``.

        Fired for failed enable/disable, ODR/config SETs, RECORD_SET, etc.,
        and also for async ``STORAGE_RECORD_ERROR`` pushes.
        """
        self._on_command_error = callback

    async def set_on_ping_response(
        self, callback: Optional[OnPingResponseCallback]
    ) -> None:
        self._on_ping_response = callback

    async def set_on_license_device_info_received(
        self, callback: Optional[OnLicenseDeviceInfoReceivedCallback]
    ) -> None:
        self._on_license_device_info = callback

    async def set_on_firmware_version_received(
        self, callback: Optional[OnFirmwareVersionReceivedCallback]
    ) -> None:
        self._on_firmware_version = callback

    ### ----------------------- Delegate Methods ----------------------- ###

    def on_characteristic_discovered(self, characteristic_uuid: MudraCharacteristicUUID):
        logger.debug(f"Characteristic discovered: {characteristic_uuid}")
        self._characteristic_status[characteristic_uuid] = True
        if characteristic_uuid == MudraCharacteristicUUID.COMMAND_CHARACTERISTIC:
            self.update_connection_properties()
       

    def update_connection_properties(self) -> None:
        import asyncio
        asyncio.create_task(self.get_emg_status())
        asyncio.create_task(self.get_h_imu_status())
        asyncio.create_task(self.get_f_imu_status())
        asyncio.create_task(self.get_ppg_status())
        asyncio.create_task(self.get_storage_record_state())
        asyncio.create_task(self.get_device_info())
        asyncio.create_task(self.get_firmware_version())
        asyncio.create_task(self._provision_license())
        asyncio.create_task(self._provision_user_id())
        self._license_manager.start()

    ### ----------------------- Is Callbacks set Methods ----------------------- ###

    def is_on_charging_state_changed_callback_set(self) -> bool:
        return self._on_charging_state_changed is not None
        
    def is_on_battery_level_changed_callback_set(self) -> bool:
        return self._on_battery_level_changed is not None

    def is_on_emg_ready_callback_set(self) -> bool:
        return self._on_emg_ready is not None

    def is_on_imu_h_ready_callback_set(self) -> bool:
        return self._on_imu_h_ready is not None

    def is_on_imu_f_ready_callback_set(self) -> bool:
        return self._on_imu_f_ready is not None

    def is_on_ppg_ready_callback_set(self) -> bool:
        return self._on_ppg_ready is not None

    def is_on_emg_status_received_callback_set(self) -> bool:
        return self._on_emg_status is not None

    def is_on_h_imu_status_received_callback_set(self) -> bool:
        return self._on_h_imu_status is not None

    def is_on_f_imu_status_received_callback_set(self) -> bool:
        return self._on_f_imu_status is not None

    def is_on_ppg_status_received_callback_set(self) -> bool:
        return self._on_ppg_status is not None

    def is_on_storage_record_state_received_callback_set(self) -> bool:
        return self._on_record_status is not None

    def is_on_storage_record_error_received_callback_set(self) -> bool:
        return self._on_record_error is not None

    def is_on_storage_next_file_num_received_callback_set(self) -> bool:
        return self._on_next_file_num is not None

    def is_on_command_error_received_callback_set(self) -> bool:
        return self._on_command_error is not None

    def is_on_ping_response_callback_set(self) -> bool:
        return self._on_ping_response is not None

    def is_on_license_device_info_received_callback_set(self) -> bool:
        return self._on_license_device_info is not None

    def is_on_firmware_version_received_callback_set(self) -> bool:
        return self._on_firmware_version is not None

    ### ----------------------- Is Data Needed ----------------------- ###

    async def _update_state_enabled(self) -> None:
        logger.debug("Updating state enabled for all firmware data types")
        for firmware_data_type in FirmwareDataType:
            await self._update_data_enabled(firmware_data_type)

    async def _update_data_enabled(self, firmware_data_type: FirmwareDataType) -> None:
        is_needed = self._computation_wrapper.is_data_needed(firmware_data_type.value)
        logger.debug(f"Is data needed for {firmware_data_type.name} is {is_needed}")
        if is_needed != self._state_enabled.get(firmware_data_type):
            logger.debug(f"Updating state enabled for {firmware_data_type.name} to {is_needed}")
            self._state_enabled[firmware_data_type] = is_needed
            await self._update_configuration(firmware_data_type)

    async def update_all_configurations(self) -> None:
        logger.debug("Updating all configurations")
        for firmware_data_type in self._state_enabled.keys():
            await self._update_configuration(firmware_data_type)

    async def _update_configuration(self, firmware_data_type: FirmwareDataType) -> None:
        enable = self._state_enabled.get(firmware_data_type, False)
        logger.debug(f"Update Configuration, enabled: {enable}, firmwareDataType: {firmware_data_type}")
        await mudraModule.Mudra().update_configuration(self, enable, firmware_data_type)

    async def get_firmware_command(self, command: int) -> bytes:
        """Byte template for `command` (an ordinal into *this device's own*
        command table — self.CMD) — see ProFirmwareCommands.h /
        UltimateFirmwareCommands.h."""
        return self.CMD.from_value(command).id

    async def send_command(self, payload: bytes) -> None:
        """Write a raw binary CONFIG frame to the device over BLE.

        CDC-transport devices never reach this — every wrapper method below
        branches on ``self.transport`` before building the binary frame and
        goes through ``_cdc_command``/``_cdc_send`` instead, which speak the
        ASCII grammar CDC's CONFIG port actually expects.
        """
        await mudraModule.Mudra().send_general_command(self, payload)

    def as_cdc_device(self) -> Optional[CdcDevice]:
        """Round-trip back into the ``CdcDevice`` this was created from (``None`` for BLE)."""
        return self._cdc_device

    # ---- CDC ASCII command helpers ------------------------------------------ #

    def _cdc_power_command(self, data_type: FirmwareDataType):
        """The ENABLE_* command for `data_type`, from this device's own
        command table. Was a module-level dict before commands were split
        per-model; now needs `self.CMD` since ProFirmwareCommand and
        UltimateFirmwareCommand are separate enums."""
        return {
            FirmwareDataType.emg: self.CMD.enableEmg,
            FirmwareDataType.imuH: self.CMD.enableHImu,
            FirmwareDataType.imuF: self.CMD.enableFImu,
            FirmwareDataType.ppg: self.CMD.enablePpg,
        }.get(data_type)

    def _cdc_token(self, cmd, enable: bool = True) -> str:
        """ASCII CDC token for `cmd` (a ProFirmwareCommand or
        UltimateFirmwareCommand member — dispatched by type since each has
        its own native CDC token table), looked up natively by the same
        ordinal BLE's `cmd.id` already uses. Combined status queries come
        back complete ("EMG?", not "EMG_STATUS"+something) — callers send
        that result as-is via `_cdc_send`; `_cdc_command` appends
        " value"/"?" itself for everything else. `enable` only matters for
        the 5 ENABLE_* (power) commands."""
        from mudra_sdk.models.enums import ProFirmwareCommand
        wrapper = computationWrapperModule.ComputationWrapper
        if isinstance(cmd, ProFirmwareCommand):
            return wrapper.get_pro_cdc_command_token(cmd.op_code, enable)
        return wrapper.get_ultimate_cdc_command_token(cmd.op_code, enable)

    async def _cdc_send(self, token: str) -> None:
        """Write `token` verbatim (a resolved status/power/action command —
        e.g. ``"EMG?"``, ``"EMG_ON"``, ``"PPG_CLEAR"`` — that needs no
        further suffix)."""
        await mudraModule.Mudra().send_cdc_command(self, token)

    async def _cdc_command(self, cmd, value=None) -> None:
        """Resolve `cmd`'s token and send it: appends `value` for a SET, or
        ``"?"`` for a bare GET when `value` is omitted."""
        token = self._cdc_token(cmd)
        token = f"{token}?" if value is None else f"{token} {value}"
        await self._cdc_send(token)

    async def on_cdc_ready(self) -> None:
        """Fire the same initial status queries BLE fires from
        ``on_characteristic_discovered`` once a CDC connection is up
        (there's no GATT discovery step to hang this off of over CDC).

        Must be awaited to completion *before* ``start_streaming()`` — if the
        device is already running (e.g. left streaming from a prior
        session/process) at a non-default EMG resolution, DATA-port bytes at
        that stride can start arriving the moment ``START`` is sent. The
        native parser only learns the real resolution once the ``EMG?``
        reply here calls ``set_parser_emg_resolution`` (mudra_device.py's
        `_on_emg_status_received`), so if these queries were still in flight
        when streaming began, EMG samples would misparse until the reply
        landed. Awaiting sequentially here (not `asyncio.create_task`,
        fire-and-forget) closes that window.
        """
        await self.get_emg_status()
        await self.get_h_imu_status()
        await self.get_f_imu_status()
        await self.get_ppg_status()
        await self.get_battery_status()
        # Mirrors update_connection_properties()'s BLE equivalent: best-effort
        # provision right after connect, not gated on anything above, so a
        # signed-in session gets pushed to the device the same way over CDC.
        asyncio.create_task(self._provision_license())
        asyncio.create_task(self._provision_user_id())
        self._license_manager.start()
        self._battery_poll_task = asyncio.create_task(self._battery_poll_loop())

    async def start_streaming(self) -> None:
        """CDC-only: global ``START`` — the DATA port stays silent until this
        is sent (BLE has no equivalent; it streams as soon as a sensor is on
        and a client is subscribed)."""
        await mudraModule.Mudra().send_cdc_command(self, "START")

    async def stop_streaming(self) -> None:
        """CDC-only: global ``STOP``, mirroring :meth:`start_streaming`."""
        await mudraModule.Mudra().send_cdc_command(self, "STOP")

    # ---- System / ping (0x00) ---------------------------------------------- #

    async def ping(self) -> None:
        if self.transport == "cdc":
            # CDC has no PING token; substitute the CDC? handshake as a
            # round-trip probe (fires on_ping_response_received on success).
            await mudraModule.Mudra().send_cdc_ping(self)
            return
        await self.send_command(bytes(self.CMD.systemPing.id))

    async def get_device_info(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.systemDeviceInfo)
            return
        await self.send_command(bytes(self.CMD.systemDeviceInfo.id))

    async def get_battery_status(self) -> None:
        """CDC-only: poll ``BAT_SOC?``/``BAT_CHG?`` and feed their replies
        into the same :meth:`set_on_battery_level_changed`/
        :meth:`set_on_charging_state_changed` callbacks BLE drives from GATT
        Battery Service notifications — CDC has no push equivalent, so
        :meth:`on_cdc_ready` calls this once at connect and polls it
        periodically (see ``_battery_poll_loop``). A no-op on BLE, which
        already gets both pushed continuously."""
        if self.transport != "cdc":
            return
        await self._cdc_command(self.CMD.batSoc)
        await self._cdc_command(self.CMD.batCharging)

    async def _battery_poll_loop(self, interval_s: float = 30.0) -> None:
        try:
            while True:
                await asyncio.sleep(interval_s)
                try:
                    await self.get_battery_status()
                except Exception as exc:  # noqa: BLE001 — a poll failure isn't fatal
                    logger.error(f"battery poll failed: {exc}")
        except asyncio.CancelledError:
            raise

    async def get_firmware_version(self) -> None:
        """BT_SYS_VERSION (0x00 0x01) — reply lands in
        :meth:`get_firmware_version_info` / the ``set_on_firmware_version_received``
        callback as a :class:`FirmwareVersion`, on both BLE and CDC.

        CDC's VERSION token is registered bare in firmware's cdc_commands.c
        table (unlike every other getter, which firmware registers with a
        literal trailing "?", e.g. "RING?"), so it must be sent as-is via
        `_cdc_send` rather than through `_cdc_command`'s usual "TOKEN?"
        suffixing — that would send "VERSION?", which firmware doesn't
        recognize and echoes back as "UNKNOWN" (confirmed against real
        hardware). The reply ("Version: X.Y.Z") is a free-form CONFIG-port
        string rather than the `[maj, min, patch, tweak]` binary struct BLE
        returns, so `CdcService._dispatch_reply` regex-parses it and
        re-encodes it into that same binary shape before handing it to
        `_parse_firmware_version` — see the `_VERSION_LINE_RE` comment there.
        """
        if self.transport == "cdc":
            await self._cdc_send(self._cdc_token(self.CMD.systemVersion))
            return
        await self.send_command(bytes(self.CMD.systemVersion.id))

    async def start_dfu(
        self,
        firmware_path: str,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_stage: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Update this device's firmware via MCUmgr/SMP over its USB-CDC SMP
        port (see mudra_sdk/service/dfu_service.py). USB (CDC) only — no BLE
        DFU transport exists on either product yet. Returns the staged
        image's version string; the device reboots and swaps to it right
        after this returns, so reconnect afterward to confirm."""
        return await mudraModule.Mudra().start_dfu(
            self, firmware_path, on_progress=on_progress, on_stage=on_stage
        )

    async def apply_license(self, token_hex: str) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.systemLicenseSet, token_hex)
            return
        await self.send_command(bytes(self.CMD.systemLicenseSet.id) + bytes.fromhex(token_hex))

    async def set_user_id(self, user_id: bytes) -> None:
        """BT_SYS_USER_ID_SET / CDC ``USER_ID`` — set the user_id required
        before starting an SD recording (see :meth:`set_storage_record`).
        Exactly 16 raw bytes; RAM-only on the device, so this must be
        (re)sent each power cycle before starting a recording. Unlike
        storage/SD commands, USER_ID has a CDC token too (firmware
        ``cdc_commands.c``), so both transports are supported here.
        """
        if len(user_id) != fp.USER_ID_LEN:
            raise ValueError(f"user_id must be exactly {fp.USER_ID_LEN} bytes, got {len(user_id)}")
        if self.transport == "cdc":
            await self._cdc_send(f"USER_ID {user_id.hex()}")
            return
        tmpl = bytearray(self.CMD.systemUserIdSet.id)
        tmpl[2:2 + fp.USER_ID_LEN] = user_id
        await self.send_command(bytes(tmpl))

    async def clear_license(self) -> None:
        """Clear the device's license (drop to FREE) over the connected transport."""
        if self.transport == "cdc":
            await self._cdc_send(self._cdc_token(self.CMD.systemLicenseClear))
            return
        await self.send_command(bytes(self.CMD.systemLicenseClear.id))

    # ---- EMG config (0x10) ------------------------------------------------ #

    async def set_emg_odr(self, odr: "ProEMGODR") -> None:
        """`odr` must come from `self.EMG_ODR_ENUM` (ProEMGODR on MudraPro,
        UltimateEMGODR on MudraUltimate) — the two products' EMG AFEs
        support different discrete rate sets."""
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.emgOdr, odr.value_int)
            return
        await self.send_command(fp.set_u16(self.CMD.emgOdr, odr.value_int))

    async def get_emg_odr(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.emgOdr)
            return
        await self.send_command(fp.get_paired(self.CMD.emgOdr))

    async def set_emg_res(self, res: EmgRes) -> None:
        # Update parser immediately so in-flight DATA uses the new stride.
        self._computation_wrapper.set_parser_emg_resolution(res.bits)
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.emgRes, res.bits)
            return
        await self.send_command(fp.set_u8(self.CMD.emgRes, res.bits))

    async def get_emg_res(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.emgRes)
            return
        await self.send_command(fp.get_paired(self.CMD.emgRes))

    async def get_emg_res_max(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.emgResMax)
            return
        await self.send_command(fp.get_standalone(self.CMD.emgResMax))

    async def get_emg_status(self) -> None:
        if self.transport == "cdc":
            await self._cdc_send(self._cdc_token(self.CMD.emgStatus))
            return
        await self.send_command(bytes(self.CMD.emgStatus.id))

    # ---- Hand IMU config (0x20) ------------------------------------------- #

    async def set_h_imu_odr(self, odr: IMUODR) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuOdr, odr.value_int)
            return
        await self.send_command(fp.set_u16(self.CMD.hImuOdr, odr.value_int))

    async def get_h_imu_odr(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuOdr)
            return
        await self.send_command(fp.get_paired(self.CMD.hImuOdr))

    async def set_h_imu_acc(self, range_g: int) -> None:
        gyr = (
            self._h_imu_status.gyro_range_dps.value_int
            if self._h_imu_status is not None
            else IMUGyrRange.imuGyrRange500.value_int
        )
        self._computation_wrapper.set_parser_imu_h_ranges(range_g, gyr)
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuAcc, range_g)
            return
        await self.send_command(fp.set_u8(self.CMD.hImuAcc, range_g))

    async def get_h_imu_acc(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuAcc)
            return
        await self.send_command(fp.get_paired(self.CMD.hImuAcc))

    async def set_h_imu_gyr(self, range_dps: int) -> None:
        acc = (
            self._h_imu_status.accel_range_g.value_int
            if self._h_imu_status is not None
            else IMUAccRange.imuAccRange4.value_int
        )
        self._computation_wrapper.set_parser_imu_h_ranges(acc, range_dps)
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuGyr, range_dps)
            return
        await self.send_command(fp.set_u16(self.CMD.hImuGyr, range_dps))

    async def get_h_imu_gyr(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuGyr)
            return
        await self.send_command(fp.get_paired(self.CMD.hImuGyr))

    async def get_h_imu_acc_res(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuAccRes)
            return
        await self.send_command(fp.get_standalone(self.CMD.hImuAccRes))

    async def get_h_imu_gyr_res(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuGyrRes)
            return
        await self.send_command(fp.get_standalone(self.CMD.hImuGyrRes))

    async def set_h_imu_acc_bw(self, divisor: int) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuAccBw, divisor)
            return
        await self.send_command(fp.set_u8(self.CMD.hImuAccBw, divisor))

    async def get_h_imu_acc_bw(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuAccBw)
            return
        await self.send_command(fp.get_paired(self.CMD.hImuAccBw))

    async def set_h_imu_gyr_bw(self, divisor: int) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuGyrBw, divisor)
            return
        await self.send_command(fp.set_u8(self.CMD.hImuGyrBw, divisor))

    async def get_h_imu_gyr_bw(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuGyrBw)
            return
        await self.send_command(fp.get_paired(self.CMD.hImuGyrBw))

    async def set_h_imu_acc_avg(self, samples: int) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuAccAvg, samples)
            return
        await self.send_command(fp.set_u8(self.CMD.hImuAccAvg, samples))

    async def get_h_imu_acc_avg(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuAccAvg)
            return
        await self.send_command(fp.get_paired(self.CMD.hImuAccAvg))

    async def set_h_imu_gyr_avg(self, samples: int) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuGyrAvg, samples)
            return
        await self.send_command(fp.set_u8(self.CMD.hImuGyrAvg, samples))

    async def get_h_imu_gyr_avg(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuGyrAvg)
            return
        await self.send_command(fp.get_paired(self.CMD.hImuGyrAvg))

    async def get_h_imu_status(self) -> None:
        if self.transport == "cdc":
            await self._cdc_send(self._cdc_token(self.CMD.hImuStatus))
            return
        await self.send_command(bytes(self.CMD.hImuStatus.id))

    # ---- Finger IMU config (0x30) ----------------------------------------- #

    async def set_f_imu_odr(self, odr: IMUODR) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuOdr, odr.value_int)
            return
        await self.send_command(fp.set_u16(self.CMD.fImuOdr, odr.value_int))

    async def get_f_imu_odr(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuOdr)
            return
        await self.send_command(fp.get_paired(self.CMD.fImuOdr))

    async def set_f_imu_acc(self, range_g: int) -> None:
        gyr = (
            self._f_imu_status.gyro_range_dps.value_int
            if self._f_imu_status is not None
            else IMUGyrRange.imuGyrRange500.value_int
        )
        self._computation_wrapper.set_parser_imu_f_ranges(range_g, gyr)
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuAcc, range_g)
            return
        await self.send_command(fp.set_u8(self.CMD.fImuAcc, range_g))

    async def get_f_imu_acc(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuAcc)
            return
        await self.send_command(fp.get_paired(self.CMD.fImuAcc))

    async def set_f_imu_gyr(self, range_dps: int) -> None:
        acc = (
            self._f_imu_status.accel_range_g.value_int
            if self._f_imu_status is not None
            else IMUAccRange.imuAccRange4.value_int
        )
        self._computation_wrapper.set_parser_imu_f_ranges(acc, range_dps)
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuGyr, range_dps)
            return
        await self.send_command(fp.set_u16(self.CMD.fImuGyr, range_dps))

    async def get_f_imu_gyr(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuGyr)
            return
        await self.send_command(fp.get_paired(self.CMD.fImuGyr))

    async def get_f_imu_acc_res(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuAccRes)
            return
        await self.send_command(fp.get_standalone(self.CMD.fImuAccRes))

    async def get_f_imu_gyr_res(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuGyrRes)
            return
        await self.send_command(fp.get_standalone(self.CMD.fImuGyrRes))

    async def set_f_imu_acc_bw(self, divisor: int) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuAccBw, divisor)
            return
        await self.send_command(fp.set_u8(self.CMD.fImuAccBw, divisor))

    async def get_f_imu_acc_bw(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuAccBw)
            return
        await self.send_command(fp.get_paired(self.CMD.fImuAccBw))

    async def set_f_imu_gyr_bw(self, divisor: int) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuGyrBw, divisor)
            return
        await self.send_command(fp.set_u8(self.CMD.fImuGyrBw, divisor))

    async def get_f_imu_gyr_bw(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuGyrBw)
            return
        await self.send_command(fp.get_paired(self.CMD.fImuGyrBw))

    async def set_f_imu_acc_avg(self, samples: int) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuAccAvg, samples)
            return
        await self.send_command(fp.set_u8(self.CMD.fImuAccAvg, samples))

    async def get_f_imu_acc_avg(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuAccAvg)
            return
        await self.send_command(fp.get_paired(self.CMD.fImuAccAvg))

    async def set_f_imu_gyr_avg(self, samples: int) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuGyrAvg, samples)
            return
        await self.send_command(fp.set_u8(self.CMD.fImuGyrAvg, samples))

    async def get_f_imu_gyr_avg(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuGyrAvg)
            return
        await self.send_command(fp.get_paired(self.CMD.fImuGyrAvg))

    async def get_f_imu_status(self) -> None:
        if self.transport == "cdc":
            await self._cdc_send(self._cdc_token(self.CMD.fImuStatus))
            return
        await self.send_command(bytes(self.CMD.fImuStatus.id))


    # ---- PPG config (0x40) ------------------------------------------------ #

    async def set_ppg_odr(self, odr: PPGODR) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.ppgOdr, odr.value_int)
            return
        await self.send_command(fp.set_u16(self.CMD.ppgOdr, odr.value_int))

    async def get_ppg_odr(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.ppgOdr)
            return
        await self.send_command(fp.get_paired(self.CMD.ppgOdr))

    async def set_ppg_dec(self, factor: int) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.ppgDec, factor)
            return
        await self.send_command(fp.set_u8(self.CMD.ppgDec, factor))

    async def get_ppg_dec(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.ppgDec)
            return
        await self.send_command(fp.get_paired(self.CMD.ppgDec))

    async def set_ppg_led(self, ch: int, drv1: int, drv2: int) -> None:
        if self.transport == "cdc":
            token = self._cdc_token(self.CMD.ppgLed)
            await mudraModule.Mudra().send_cdc_command(self, f"{token} {ch} {drv1} {drv2}")
            return
        await self.send_command(fp.ppg_led_set(ch, drv1, drv2))

    async def get_ppg_led(self, ch: int) -> None:
        if self.transport == "cdc":
            token = self._cdc_token(self.CMD.ppgLed)
            await mudraModule.Mudra().send_cdc_command(self, f"{token}? {ch}")
            return
        await self.send_command(fp.ppg_led_get(ch))

    async def set_ppg_tia(self, ch: int, rf: int, cf: int) -> None:
        if self.transport == "cdc":
            token = self._cdc_token(self.CMD.ppgTia)
            await mudraModule.Mudra().send_cdc_command(self, f"{token} {ch} {rf} {cf}")
            return
        await self.send_command(fp.ppg_tia_set(ch, rf, cf))

    async def get_ppg_tia(self, ch: int) -> None:
        if self.transport == "cdc":
            token = self._cdc_token(self.CMD.ppgTia)
            await mudraModule.Mudra().send_cdc_command(self, f"{token}? {ch}")
            return
        await self.send_command(fp.ppg_tia_get(ch))

    async def set_ppg_prpct(self, code: int) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.ppgPrpct, code)
            return
        await self.send_command(fp.set_u16(self.CMD.ppgPrpct, code))

    async def get_ppg_prpct(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.ppgPrpct)
            return
        await self.send_command(fp.get_paired(self.CMD.ppgPrpct))

    async def ppg_clear(self) -> None:
        if self.transport == "cdc":
            await self._cdc_send(self._cdc_token(self.CMD.ppgClear))
            return
        await self.send_command(fp.ppg_clear(self.model))

    async def set_ppg_src(self, ch: int, led: int, pd: int) -> None:
        if self.transport == "cdc":
            token = self._cdc_token(self.CMD.ppgSrc)
            await mudraModule.Mudra().send_cdc_command(self, f"{token} {ch} {led} {pd}")
            return
        await self.send_command(fp.ppg_src_set(ch, led, pd))

    async def get_ppg_src(self, ch: int) -> None:
        if self.transport == "cdc":
            token = self._cdc_token(self.CMD.ppgSrc)
            await mudraModule.Mudra().send_cdc_command(self, f"{token}? {ch}")
            return
        await self.send_command(fp.ppg_src_get(ch))

    async def get_ppg_status(self) -> None:
        if self.transport == "cdc":
            await self._cdc_send(self._cdc_token(self.CMD.ppgStatus))
            return
        await self.send_command(bytes(self.CMD.ppgStatus.id))


    # ---- Storage / SD recording (0x90) ------------------------------------ #

    async def set_storage_record(
        self,
        emg: bool,
        ppg: bool,
        imu_h: bool,
        imu_f: bool,
        file_num: int = 0,
        duration_min: int = 0,
        utc_ts: int = 0,
        description: str = "",
        is_test: bool = False,
    ) -> None:
        """Start/stop SD card recording per sensor (``BT_STORAGE_RECORD_SET``).

        Requires the device's **PRO** tier license — on FREE/PLUS a start is
        rejected with ``ERR_LICENSE`` (via the command-error callback)
        without touching any sensor; see :meth:`get_device_info` /
        :meth:`apply_license`.

        Recordings land on the device's own SD card as ``/SD:/REC_<n>.bin``
        (binary, ``MREC``-tagged). Optional ``description`` is written as the
        first line when the file is freshly opened (ignored while a session
        is already active).

        ``duration_min``: 0 (default) records until an explicit stop call;
        any other value (1-65535) arms a one-shot firmware timer that
        automatically stops the session after that many minutes — same
        sensor teardown and ``BT_STORAGE_RECORD_STATE`` push (``active=False``)
        as calling ``set_storage_record(False, False, False, False,
        file_num)`` yourself. Ignored when stopping. An earlier stop (manual,
        disconnect, or a write-failure abort) cancels the pending timer.

        ``utc_ts``: 0 (default) supplies no timestamp; any other value is
        your wall-clock time in Unix epoch seconds (``int(time.time())``) at
        session start. The device has no independent RTC, so this is folded
        verbatim into the firmware-generated meta line as ``UTC=<ts>`` when
        non-zero, and nothing else — it does not set the device's trusted
        clock. Ignored when stopping.

        ``is_test``: for each sensor newly started by this call, arm its
        packet-loss test-mode counter (channel 0 / accel-x becomes an
        incrementing counter) before it starts, so the recording captures
        the counter stream instead of real data — for offline packet-loss
        analysis without a BLE/USB link. Cleared automatically when that
        sensor's recording stops.

        Fails with ``ERR_STATE`` (via the command-error callback) if
        :meth:`set_user_id` was never called.

        CDC has no storage/SD-recording tokens at all (confirmed against
        firmware's cdc_commands.c) — over CDC this immediately reports
        ``ERR_UNKNOWN`` via the command-error callback instead of sending.
        """
        if self.transport == "cdc":
            self.on_command_error_received(BtCmdId.STORAGE, BtCmdStatus.ERR_UNKNOWN)
            return
        if not 0 <= duration_min <= _STORAGE_RECORD_DURATION_MAX_MIN:
            raise ValueError(
                f"duration_min must be 0-{_STORAGE_RECORD_DURATION_MAX_MIN}, got {duration_min}"
            )
        if not 0 <= utc_ts <= _STORAGE_RECORD_UTC_TS_MAX:
            raise ValueError(f"utc_ts must be 0-{_STORAGE_RECORD_UTC_TS_MAX}, got {utc_ts}")
        desc_bytes = b""
        if description:
            desc_bytes = description.encode("utf-8") if isinstance(description, str) else bytes(description)
            if len(desc_bytes) > _STORAGE_RECORD_DESC_MAX_LEN:
                raise ValueError(
                    f"record description max {_STORAGE_RECORD_DESC_MAX_LEN} bytes, "
                    f"got {len(desc_bytes)}"
                )
        tmpl = bytearray(self.CMD.storageRecordSet.id)
        tmpl[2] = 1 if emg else 0
        tmpl[3] = 1 if ppg else 0
        tmpl[4] = 1 if imu_h else 0
        tmpl[5] = 1 if imu_f else 0
        tmpl[6] = 1 if is_test else 0
        tmpl[7] = file_num & 0xFF
        tmpl[8] = duration_min & 0xFF
        tmpl[9] = (duration_min >> 8) & 0xFF
        tmpl[10] = utc_ts & 0xFF
        tmpl[11] = (utc_ts >> 8) & 0xFF
        tmpl[12] = (utc_ts >> 16) & 0xFF
        tmpl[13] = (utc_ts >> 24) & 0xFF
        await self.send_command(bytes(tmpl) + desc_bytes)

    async def get_storage_record_state(self) -> None:
        """Query SD recording state; reply arrives via record-state callback."""
        if self.transport == "cdc":
            self.on_command_error_received(BtCmdId.STORAGE, BtCmdStatus.ERR_UNKNOWN)
            return
        await self.send_command(fp.get_standalone(self.CMD.storageRecordState))

    async def get_storage_next_file_num(self) -> None:
        """Query first free ``REC_<n>.csv`` file number; reply via next-file callback."""
        if self.transport == "cdc":
            self.on_command_error_received(BtCmdId.STORAGE, BtCmdStatus.ERR_UNKNOWN)
            return
        await self.send_command(fp.get_standalone(self.CMD.storageNextFileNum))

    ### ----------------------- Data Recorder Methods ----------------------- ###
    def enable_recording(self):
        self._data_recorder.enable_recording(self._computation_wrapper)

    def disable_recording(self):
        self._data_recorder.disable_recording(self._computation_wrapper)

    def get_json_recording(self) -> str:
        return self._data_recorder.get_json_recording(self._computation_wrapper)

    def is_recording_enabled(self) -> bool:
        return self._data_recorder.is_recording_enabled(self._computation_wrapper)

    def record_event(self, event_type: EventType, event: str):
        self._data_recorder.record_event(self._computation_wrapper, event_type, event)

    def add_video(self, video_description: str, video_path: str):
        self._data_recorder.add_video(self._computation_wrapper, video_description, video_path)

    async def start_recording(
        self,
        recording_types: List[RecordingDataType],
    ) -> None:
        self._data_recorder.start_recording(
            self._computation_wrapper,
            recording_types,
        )
        # Recording a sensor (e.g. EMG) must keep it powered on even if no
        # live ready-callback is registered for it — see IsDataNeeded.
        await self._update_state_enabled()

    async def stop_recording(self):
        self._data_recorder.stop_recording(self._computation_wrapper)
        await self._update_state_enabled()

    async def upload_recording(
        self,
        on_progress: Optional[Callable[[int, int, float, str], None]] = None,
    ) -> None:
        if not self.is_recording_enabled():
            return

        def _sync_upload() -> None:
            self._data_recorder.upload_recording(
                self._computation_wrapper,
                on_progress=on_progress,
            )

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _sync_upload)
