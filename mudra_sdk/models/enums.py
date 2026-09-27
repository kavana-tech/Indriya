
from enum import Enum
from typing import Optional

class cmdType(Enum):
    BT_CMD_RESPONSE_HEADER = 0xF0

    @property
    def value_int(self) -> int:
        return self.value

    @staticmethod
    def from_value(value: int) -> Optional["cmdType"]:
        for item in cmdType:
            if item.value == value:
                return item
        return None

class BtCmdProEMG(Enum):
    POWER = 0x00          # STOP | START
    ODR = 0x01            # GET -> u16 | SET <u16>
    RES = 0x02            # GET -> u8  | SET <u8>
    RES_MAX = 0x03        # -> u32 ±max post-process value
    STATE = 0x04          # -> [enabled u8, odr u16 LE, res_bits u8] (4 bytes)

    @property
    def value_int(self) -> int:
        return self.value

    @staticmethod
    def from_value(value: int) -> Optional["BtCmdProEMG"]:
        for item in BtCmdProEMG:
            if item.value == value:
                return item
        return None

class BtCmdUltimateEMG(Enum):
    POWER = 0x00          # STOP | START
    ODR = 0x01            # GET -> u16 | SET <u16>
    RES = 0x02            # GET -> u8  | SET <u8>
    RES_MAX = 0x03        # -> u32 ±max post-process value
    STATE = 0x08          # -> [enabled u8, odr u16 LE, res_bits u8, test u8] (5 bytes)

    @property
    def value_int(self) -> int:
        return self.value

    @staticmethod
    def from_value(value: int) -> Optional["BtCmdUltimateEMG"]:
        for item in BtCmdUltimateEMG:
            if item.value == value:
                return item
        return None

class BtCmdHIMU(Enum):
    POWER = 0x00
    ODR = 0x01
    ACC = 0x02
    GYR = 0x03
    ACC_RES = 0x04
    GYR_RES = 0x05
    ACC_BW = 0x06
    GYR_BW = 0x07
    ACC_AVG = 0x08
    GYR_AVG = 0x09
    STATE = 0x0A

    @property
    def value_int(self) -> int:
        return self.value

    @staticmethod
    def from_value(value: int) -> Optional["BtCmdHIMU"]:
        for item in BtCmdHIMU:
            if item.value == value:
                return item
        return None


class BtCmdFIMU(Enum):
    POWER = 0x00
    ODR = 0x01
    ACC = 0x02
    GYR = 0x03
    ACC_RES = 0x04
    GYR_RES = 0x05
    ACC_BW = 0x06
    GYR_BW = 0x07
    ACC_AVG = 0x08
    GYR_AVG = 0x09
    STATE = 0x0A

    @property
    def value_int(self) -> int:
        return self.value

    @staticmethod
    def from_value(value: int) -> Optional["BtCmdFIMU"]:
        for item in BtCmdFIMU:
            if item.value == value:
                return item
        return None


class BtCmdPPG(Enum):
    POWER = 0x00
    ODR = 0x01
    DEC = 0x02
    LED = 0x03
    TIA = 0x04
    PRPCT = 0x05
    CLEAR = 0x06
    SRC = 0x07
    STATE = 0x08

    @property
    def value_int(self) -> int:
        return self.value

    @staticmethod
    def from_value(value: int) -> Optional["BtCmdPPG"]:
        for item in BtCmdPPG:
            if item.value == value:
                return item
        return None


class BtCmdStorage(Enum):
    RECORD_SET = 0x00    # emg, ppg, hand_imu, finger_imu, file_num, [description...]
    RECORD_STATE = 0x01  # -> [active, emg, ppg, hand_imu, finger_imu, file_num]
    RECORD_ERROR = 0x02  # push-only: [RECORD_ERROR, status]
    NEXT_FILE_NUM = 0x03  # -> [NEXT_FILE_NUM, file_num]

    @property
    def value_int(self) -> int:
        return self.value

    @staticmethod
    def from_value(value: int) -> Optional["BtCmdStorage"]:
        for item in BtCmdStorage:
            if item.value == value:
                return item
        return None


class BtCmdStatus(Enum):
    """BLE CONFIG status codes (status-only replies and RECORD_ERROR payload)."""
    OK = 0x00
    ERR_UNKNOWN = 0x01
    ERR_INVALID = 0x02
    ERR_BUSY = 0x03          # RECORD_SET on a sensor already running
    ERR_STATE = 0x04
    ERR_HARDWARE = 0x05
    ERR_INTERNAL = 0x06
    ERR_BT_NOT_READY = 0x07
    ERR_LICENSE = 0x08
    ERR_BLE_RATE = 0x09
    ERR_FILE_EXISTS = 0x0A   # RECORD_SET file_num already on SD card
    ERR_SD_WRITE = 0x0B      # SD write failed; recording was stopped

    @property
    def value_int(self) -> int:
        return self.value

    @property
    def description(self) -> str:
        return {
            BtCmdStatus.OK: "OK",
            BtCmdStatus.ERR_UNKNOWN: "ERR_UNKNOWN",
            BtCmdStatus.ERR_INVALID: "ERR_INVALID",
            BtCmdStatus.ERR_BUSY: "ERR_BUSY",
            BtCmdStatus.ERR_STATE: "ERR_STATE",
            BtCmdStatus.ERR_HARDWARE: "ERR_HARDWARE",
            BtCmdStatus.ERR_INTERNAL: "ERR_INTERNAL",
            BtCmdStatus.ERR_BT_NOT_READY: "ERR_BT_NOT_READY",
            BtCmdStatus.ERR_LICENSE: "ERR_LICENSE",
            BtCmdStatus.ERR_BLE_RATE: "ERR_BLE_RATE",
            BtCmdStatus.ERR_FILE_EXISTS: "ERR_FILE_EXISTS",
            BtCmdStatus.ERR_SD_WRITE: "ERR_SD_WRITE",
        }[self]

    @staticmethod
    def from_value(value: int) -> Optional["BtCmdStatus"]:
        for item in BtCmdStatus:
            if item.value == value:
                return item
        return None


class BtCmdId(Enum):
    """Top-level BLE CONFIG command IDs (first byte of request / second of 0xF0 reply)."""
    SYSTEM = 0x00
    EMG = 0x10
    H_IMU = 0x20
    F_IMU = 0x30
    PPG = 0x40
    BAT = 0x50
    LED = 0x60
    BT_CTRL = 0x70
    TAP = 0x80
    STORAGE = 0x90

    @property
    def value_int(self) -> int:
        return self.value

    @property
    def description(self) -> str:
        return self.name

    @staticmethod
    def from_value(value: int) -> Optional["BtCmdId"]:
        for item in BtCmdId:
            if item.value == value:
                return item
        return None


class SensorTypes(Enum):
    EMG = 0x10
    H_IMU = 0x20
    F_IMU = 0x30
    PPG = 0x40

    @property
    def value_int(self) -> int:
        return self.value

    @staticmethod
    def from_value(value: int) -> Optional["SensorTypes"]:
        for item in SensorTypes:
            if item.value == value:
                return item
        return None

class MudraBLEServicesUUID(Enum):
    COMMAND_SERVICE = "0000fff0-0000-1000-8000-00805f9b34fb"
    BATTERY_SERVICE = "0000180f-0000-1000-8000-00805f9b34fb"
    INFORMATION_SERVICE = "0000180a-0000-1000-8000-00805f9b34fb"

    @property
    def value_str(self) -> str:
        return self.value

    @staticmethod
    def from_value(value: str) -> Optional["MudraBLEServicesUUID"]:
        for item in MudraBLEServicesUUID:
            if item.value == value:
                return item
        return None

class MudraCharacteristicUUID(Enum):
    COMMAND_CHARACTERISTIC = "0000fff1-0000-1000-8000-00805f9b34fb"
    MESSAGE_CHARACTERISTIC = "0000fff2-0000-1000-8000-00805f9b34fb"
    DATA_CHARACTERISTIC = "0000fff3-0000-1000-8000-00805f9b34fb"
    BATTERY_CHARACTERISTIC = "00002a19-0000-1000-8000-00805f9b34fb"
    BATTERY_POWER_STATE_CHARACTERISTIC = "00002a1a-0000-1000-8000-00805f9b34fb"

    @property
    def value_str(self) -> str:
        return self.value

    @staticmethod
    def from_value(value: str) -> Optional["MudraCharacteristicUUID"]:
        for item in MudraCharacteristicUUID:
            if item.value == value:
                return item
        return None

class FirmwareCallbacks(Enum):
    EMG_STATUS = 1
    H_IMU_STATUS = 2
    F_IMU_STATUS = 3
    PPG_STATUS = 4
    STORAGE_RECORD_STATE = 5
    STORAGE_RECORD_ERROR = 6
    STORAGE_NEXT_FILE_NUM = 7
    PING_RESPONSE = 8
    DEVICE_INFO = 9
    SYSTEM_VERSION = 10

    @property
    def description(self) -> str:
        return {
            FirmwareCallbacks.EMG_STATUS: "EMG_STATUS",
            FirmwareCallbacks.H_IMU_STATUS: "H_IMU_STATUS",
            FirmwareCallbacks.F_IMU_STATUS: "F_IMU_STATUS",
            FirmwareCallbacks.PPG_STATUS: "PPG_STATUS",
            FirmwareCallbacks.STORAGE_RECORD_STATE: "STORAGE_RECORD_STATE",
            FirmwareCallbacks.STORAGE_RECORD_ERROR: "STORAGE_RECORD_ERROR",
            FirmwareCallbacks.STORAGE_NEXT_FILE_NUM: "STORAGE_NEXT_FILE_NUM",
            FirmwareCallbacks.PING_RESPONSE: "PING_RESPONSE",
            FirmwareCallbacks.DEVICE_INFO: "DEVICE_INFO",
            FirmwareCallbacks.SYSTEM_VERSION: "SYSTEM_VERSION",
        }[self]

    # Static byte-array values as bytes objects
    EMG_STATUS_BYTES   = bytes([cmdType.BT_CMD_RESPONSE_HEADER.value_int, BtCmdId.EMG.value_int, BtCmdProEMG.STATE.value_int])
    # Ultimate's EMG_STATE feature byte is 0x08, not Pro's 0x04 (Ultimate
    # inserts TEST/CHMASK/RLD/ISOLATE at 0x04-0x07 — see
    # UltimateFirmwareCommands.h). 0x04 is a *different, real* command on
    # Ultimate (EMG_TEST), so from_data() must pick one pattern or the other
    # per-device, never both — matching the wrong one would misclassify an
    # Ultimate EMG_TEST reply as an EMG_STATUS push (or vice versa on Pro).
    EMG_STATUS_BYTES_ULTIMATE = bytes([cmdType.BT_CMD_RESPONSE_HEADER.value_int, BtCmdId.EMG.value_int, BtCmdUltimateEMG.STATE.value_int])
    H_IMU_STATUS_BYTES = bytes([cmdType.BT_CMD_RESPONSE_HEADER.value_int, BtCmdId.H_IMU.value_int, BtCmdHIMU.STATE.value_int])
    F_IMU_STATUS_BYTES = bytes([cmdType.BT_CMD_RESPONSE_HEADER.value_int, BtCmdId.F_IMU.value_int, BtCmdFIMU.STATE.value_int])
    PPG_STATUS_BYTES   = bytes([cmdType.BT_CMD_RESPONSE_HEADER.value_int, BtCmdId.PPG.value_int, BtCmdPPG.STATE.value_int])
    PING_RESPONSE_BYTES = bytes([cmdType.BT_CMD_RESPONSE_HEADER.value_int, BtCmdId.SYSTEM.value_int, BtCmdStatus.OK.value_int])
    # BT_SYS_DEVICE_INFO's reply has NO feature byte on the wire — firmware
    # never echoes req->params[0] for this command (bt_command_manager.c
    # handle_system(), case BT_SYS_DEVICE_INFO): the frame is bare
    # [0xF0, cmd_id, tier, valid, now32, floor32, expires32, serial[13]],
    # 29 bytes total. Matched by exact length in from_data() (checked
    # first, below) rather than a 3-byte prefix like the others — a
    # FREE-tier reply (tier byte = 0x00) would otherwise collide with
    # PING_RESPONSE_BYTES ([0xF0, SYSTEM, OK]) on their shared first 3 bytes.
    DEVICE_INFO_HEADER_BYTES = bytes([cmdType.BT_CMD_RESPONSE_HEADER.value_int, BtCmdId.SYSTEM.value_int])
    DEVICE_INFO_FRAME_LEN = 29

    # BT_SYS_VERSION shares SYSTEM_VERSION's request cmd_id (0x00) with
    # DEVICE_INFO/PING and, like DEVICE_INFO, is sent via `resp_ok(cmd_id, ...)`
    # with no feature byte echoed: bare [0xF0, 0x00, maj, min, patch, tweak],
    # 6 bytes total (bt_command_manager.c handle_system(), case
    # BT_SYS_VERSION). Matched by exact length against the same 2-byte
    # DEVICE_INFO_HEADER_BYTES prefix, checked before PING_RESPONSE_BYTES'
    # 3-byte prefix match below so a version reply whose major byte happens
    # to equal BtCmdStatus.OK's value can't be misread as a ping ack.

    STORAGE_RECORD_STATE_BYTES = bytes([
        cmdType.BT_CMD_RESPONSE_HEADER.value_int,
        BtCmdId.STORAGE.value_int,
        BtCmdStorage.RECORD_STATE.value_int,
    ])
    # len must be >= 4 — a 3-byte status reply with ERR_INVALID is also [0xF0, 0x90, 0x02]
    STORAGE_RECORD_ERROR_BYTES = bytes([
        cmdType.BT_CMD_RESPONSE_HEADER.value_int,
        BtCmdId.STORAGE.value_int,
        BtCmdStorage.RECORD_ERROR.value_int,
    ])
    STORAGE_NEXT_FILE_NUM_BYTES = bytes([
        cmdType.BT_CMD_RESPONSE_HEADER.value_int,
        BtCmdId.STORAGE.value_int,
        BtCmdStorage.NEXT_FILE_NUM.value_int,
    ])

    @staticmethod
    def are_bytes_equal(bytes1: bytes, bytes2: bytes) -> bool:
        return bytes1 == bytes2

    @staticmethod
    def from_data(data: bytes) -> Optional["FirmwareCallbacks"]:
        # Checked first, by exact length — see DEVICE_INFO_HEADER_BYTES above
        # for why this can't be a 3-byte prefix match like the others.
        if (
            len(data) == FirmwareCallbacks.DEVICE_INFO_FRAME_LEN.value
            and FirmwareCallbacks.are_bytes_equal(data[:2], FirmwareCallbacks.DEVICE_INFO_HEADER_BYTES.value)
        ):
            return FirmwareCallbacks.DEVICE_INFO
        # SYSTEM_VERSION: bare [0xF0, 0x00, maj, min, patch, tweak], 6 bytes —
        # see the SYSTEM_VERSION comment above DEVICE_INFO_FRAME_LEN. Checked
        # by exact length, same as DEVICE_INFO, and before PING_RESPONSE_BYTES.
        if (
            len(data) == 6
            and FirmwareCallbacks.are_bytes_equal(data[:2], FirmwareCallbacks.DEVICE_INFO_HEADER_BYTES.value)
        ):
            return FirmwareCallbacks.SYSTEM_VERSION
        # EMG_STATE's feature byte differs by model (0x04 Pro / 0x08
        # Ultimate) — pick the one matching `model` only; don't check both,
        # since Pro's byte is a live, different command (EMG_TEST) on
        if len(data) >= 3 and FirmwareCallbacks.are_bytes_equal(data[:3], FirmwareCallbacks.EMG_STATUS_BYTES.value):
            return FirmwareCallbacks.EMG_STATUS
        if len(data) >= 3 and FirmwareCallbacks.are_bytes_equal(data[:3], FirmwareCallbacks.EMG_STATUS_BYTES_ULTIMATE.value):
            return FirmwareCallbacks.EMG_STATUS
        if len(data) >= 3 and FirmwareCallbacks.are_bytes_equal(data[:3], FirmwareCallbacks.H_IMU_STATUS_BYTES.value):
            return FirmwareCallbacks.H_IMU_STATUS
        if len(data) >= 3 and FirmwareCallbacks.are_bytes_equal(data[:3], FirmwareCallbacks.F_IMU_STATUS_BYTES.value):
            return FirmwareCallbacks.F_IMU_STATUS
        if len(data) >= 3 and FirmwareCallbacks.are_bytes_equal(data[:3], FirmwareCallbacks.PPG_STATUS_BYTES.value):
            return FirmwareCallbacks.PPG_STATUS
        if len(data) >= 3 and FirmwareCallbacks.are_bytes_equal(
            data[:3], FirmwareCallbacks.STORAGE_RECORD_STATE_BYTES.value
        ):
            return FirmwareCallbacks.STORAGE_RECORD_STATE
        # Require 4+ bytes so status-only ERR_INVALID ([0xF0, 0x90, 0x02]) is not mistaken.
        if len(data) >= 4 and FirmwareCallbacks.are_bytes_equal(
            data[:3], FirmwareCallbacks.STORAGE_RECORD_ERROR_BYTES.value
        ):
            return FirmwareCallbacks.STORAGE_RECORD_ERROR
        if len(data) >= 4 and FirmwareCallbacks.are_bytes_equal(
            data[:3], FirmwareCallbacks.STORAGE_NEXT_FILE_NUM_BYTES.value
        ):
            return FirmwareCallbacks.STORAGE_NEXT_FILE_NUM
        if len(data) >= 3 and FirmwareCallbacks.are_bytes_equal(
            data[:3], FirmwareCallbacks.PING_RESPONSE_BYTES.value
        ):
            return FirmwareCallbacks.PING_RESPONSE
        return None

    @staticmethod
    def from_cdc_line(line: str) -> Optional["FirmwareCallbacks"]:
        """CDC counterpart to `from_data`: classify an ASCII CONFIG-port
        reply line by its leading token instead of a binary byte prefix.
        Only the combined sensor-status queries have a CDC equivalent — CDC
        has no storage/recording tokens at all, and no PING token (the
        "CDC?" handshake substitutes for it, handled separately)."""
        if not line:
            return None
        token = line.split(" ", 1)[0]
        return {
            "EMG": FirmwareCallbacks.EMG_STATUS,
            "H_IMU": FirmwareCallbacks.H_IMU_STATUS,
            "F_IMU": FirmwareCallbacks.F_IMU_STATUS,
            "PPG": FirmwareCallbacks.PPG_STATUS,
        }.get(token)


class MudraModel(Enum):
    """Hardware product line — used only to pick which subclass/command table
    a discovered device gets (MudraPro+ProFirmwareCommand vs.
    MudraUltimate+UltimateFirmwareCommand). Named to avoid any confusion with
    LicenseTier's PRO member (a feature tier, unrelated to hardware). Carries
    no protocol/command logic of its own — see ProFirmwareCommand /
    UltimateFirmwareCommand for that."""
    PRO = 0
    ULTIMATE = 1

    @property
    def value_int(self) -> int:
        return self.value

    @staticmethod
    def from_ble_name(name: Optional[str]) -> Optional["MudraModel"]:
        """Classify a device from its BLE advertised name (e.g. "Mudra Pro
        48-25" / "Mudra Ultimate 12-04"). Returns None if `name` doesn't look
        like a Mudra device at all."""
        if not name:
            return None
        if "Mudra Ultimate" in name:
            return MudraModel.ULTIMATE
        if "Mudra Pro" in name:
            return MudraModel.PRO
        return None


class ProFirmwareCommand(Enum):
    """BLE CONFIG command table for Mudra PRO — fully independent of
    UltimateFirmwareCommand (see that class for Ultimate's own table).
    Mirrors mudra_pro/src/bt_layer/bt_command_manager.h."""

    # System
    systemPing = 0
    systemVersion = 1
    systemSerial = 2
    systemRing = 3
    systemDeviceInfo = 4
    systemLicenseSet = 5
    systemLicenseClear = 6

    # EMG — trailing template bytes are SDK-filled
    enableEmg = 7
    emgOdr = 8
    emgRes = 9
    emgResMax = 10
    emgStatus = 11

    # Hand IMU
    enableHImu = 12
    hImuOdr = 13
    hImuAcc = 14
    hImuGyr = 15
    hImuAccRes = 16
    hImuGyrRes = 17
    hImuAccBw = 18
    hImuGyrBw = 19
    hImuAccAvg = 20
    hImuGyrAvg = 21
    hImuStatus = 22

    # Finger IMU
    enableFImu = 23
    fImuOdr = 24
    fImuAcc = 25
    fImuGyr = 26
    fImuAccRes = 27
    fImuGyrRes = 28
    fImuAccBw = 29
    fImuGyrBw = 30
    fImuAccAvg = 31
    fImuGyrAvg = 32
    fImuStatus = 33

    # PPG
    enablePpg = 34
    ppgOdr = 35
    ppgDec = 36
    ppgLed = 37
    ppgTia = 38
    ppgPrpct = 39
    ppgClear = 40
    ppgSrc = 41
    ppgStatus = 42

    # Battery
    batStatus = 43
    batSoc = 44
    batVoltage = 45
    batCharging = 46
    batConnected = 47
    batReset = 48

    # LED
    ledSetState = 49
    ledClrState = 50
    ledRgb = 51
    ledBlink = 52
    ledOff = 53
    ledGet = 54

    # BT control
    btAdvStart = 55
    btAdvStop = 56
    btAdvGet = 57
    btConnGet = 58
    btNameSet = 59
    btNameGet = 60
    btNameReset = 61
    btPhySet = 62

    # TinyTap
    enableTap = 63

    # Storage
    storageRecordSet = 64
    storageRecordState = 65
    storageNextFileNum = 66

    # Packet-loss test mode — Pro-only, no Ultimate equivalent. Appended at
    # the end; matches ProFirmwareCommands.h, where these are also appended
    # last so no existing ordinal shifts.
    emgTestMode = 67
    hImuTestMode = 68
    fImuTestMode = 69
    ppgTestMode = 70

    # Required before SD recording — also appended at the end; matches
    # ProFirmwareCommands.h, where this is likewise appended last (grouped
    # with the other end-of-enum entries) so no existing ordinal shifts.
    systemUserIdSet = 71

    @property
    def description(self) -> str:
        return {
            ProFirmwareCommand.systemPing: "SYSTEM_PING",
            ProFirmwareCommand.systemVersion: "SYSTEM_VERSION",
            ProFirmwareCommand.systemSerial: "SYSTEM_SERIAL",
            ProFirmwareCommand.systemRing: "SYSTEM_RING",
            ProFirmwareCommand.systemDeviceInfo: "SYSTEM_DEVICE_INFO",
            ProFirmwareCommand.systemLicenseSet: "SYSTEM_LICENSE_SET",
            ProFirmwareCommand.systemLicenseClear: "SYSTEM_LICENSE_CLEAR",
            ProFirmwareCommand.enableEmg: "ENABLE_EMG",
            ProFirmwareCommand.emgOdr: "EMG_ODR",
            ProFirmwareCommand.emgRes: "EMG_RES",
            ProFirmwareCommand.emgResMax: "EMG_RES_MAX",
            ProFirmwareCommand.emgStatus: "EMG_STATUS",
            ProFirmwareCommand.enableHImu: "ENABLE_H_IMU",
            ProFirmwareCommand.hImuOdr: "H_IMU_ODR",
            ProFirmwareCommand.hImuAcc: "H_IMU_ACC",
            ProFirmwareCommand.hImuGyr: "H_IMU_GYR",
            ProFirmwareCommand.hImuAccRes: "H_IMU_ACC_RES",
            ProFirmwareCommand.hImuGyrRes: "H_IMU_GYR_RES",
            ProFirmwareCommand.hImuAccBw: "H_IMU_ACC_BW",
            ProFirmwareCommand.hImuGyrBw: "H_IMU_GYR_BW",
            ProFirmwareCommand.hImuAccAvg: "H_IMU_ACC_AVG",
            ProFirmwareCommand.hImuGyrAvg: "H_IMU_GYR_AVG",
            ProFirmwareCommand.hImuStatus: "H_IMU_STATUS",
            ProFirmwareCommand.enableFImu: "ENABLE_F_IMU",
            ProFirmwareCommand.fImuOdr: "F_IMU_ODR",
            ProFirmwareCommand.fImuAcc: "F_IMU_ACC",
            ProFirmwareCommand.fImuGyr: "F_IMU_GYR",
            ProFirmwareCommand.fImuAccRes: "F_IMU_ACC_RES",
            ProFirmwareCommand.fImuGyrRes: "F_IMU_GYR_RES",
            ProFirmwareCommand.fImuAccBw: "F_IMU_ACC_BW",
            ProFirmwareCommand.fImuGyrBw: "F_IMU_GYR_BW",
            ProFirmwareCommand.fImuAccAvg: "F_IMU_ACC_AVG",
            ProFirmwareCommand.fImuGyrAvg: "F_IMU_GYR_AVG",
            ProFirmwareCommand.fImuStatus: "F_IMU_STATUS",
            ProFirmwareCommand.enablePpg: "ENABLE_PPG",
            ProFirmwareCommand.ppgOdr: "PPG_ODR",
            ProFirmwareCommand.ppgDec: "PPG_DEC",
            ProFirmwareCommand.ppgLed: "PPG_LED",
            ProFirmwareCommand.ppgTia: "PPG_TIA",
            ProFirmwareCommand.ppgPrpct: "PPG_PRPCT",
            ProFirmwareCommand.ppgClear: "PPG_CLEAR",
            ProFirmwareCommand.ppgSrc: "PPG_SRC",
            ProFirmwareCommand.ppgStatus: "PPG_STATUS",
            ProFirmwareCommand.batStatus: "BAT_STATUS",
            ProFirmwareCommand.batSoc: "BAT_SOC",
            ProFirmwareCommand.batVoltage: "BAT_VOLTAGE",
            ProFirmwareCommand.batCharging: "BAT_CHARGING",
            ProFirmwareCommand.batConnected: "BAT_CONNECTED",
            ProFirmwareCommand.batReset: "BAT_RESET",
            ProFirmwareCommand.ledSetState: "LED_SET_STATE",
            ProFirmwareCommand.ledClrState: "LED_CLR_STATE",
            ProFirmwareCommand.ledRgb: "LED_RGB",
            ProFirmwareCommand.ledBlink: "LED_BLINK",
            ProFirmwareCommand.ledOff: "LED_OFF",
            ProFirmwareCommand.ledGet: "LED_GET",
            ProFirmwareCommand.btAdvStart: "BT_ADV_START",
            ProFirmwareCommand.btAdvStop: "BT_ADV_STOP",
            ProFirmwareCommand.btAdvGet: "BT_ADV_GET",
            ProFirmwareCommand.btConnGet: "BT_CONN_GET",
            ProFirmwareCommand.btNameSet: "BT_NAME_SET",
            ProFirmwareCommand.btNameGet: "BT_NAME_GET",
            ProFirmwareCommand.btNameReset: "BT_NAME_RESET",
            ProFirmwareCommand.btPhySet: "BT_PHY_SET",
            ProFirmwareCommand.enableTap: "ENABLE_TAP",
            ProFirmwareCommand.storageRecordSet: "STORAGE_RECORD_SET",
            ProFirmwareCommand.storageRecordState: "STORAGE_RECORD_STATE",
            ProFirmwareCommand.storageNextFileNum: "STORAGE_NEXT_FILE_NUM",
            ProFirmwareCommand.emgTestMode: "EMG_TEST_MODE",
            ProFirmwareCommand.hImuTestMode: "H_IMU_TEST_MODE",
            ProFirmwareCommand.fImuTestMode: "F_IMU_TEST_MODE",
            ProFirmwareCommand.ppgTestMode: "PPG_TEST_MODE",
            ProFirmwareCommand.systemUserIdSet: "SYSTEM_USER_ID_SET",
        }[self]

    @property
    def op_code(self) -> int:
        return self.value

    @property
    def id(self) -> bytes:
        from mudra_sdk.models.computation_wrapper import ComputationWrapper
        return ComputationWrapper.get_pro_firmware_command_bytes(self.op_code)

    @staticmethod
    def from_value(value: int) -> Optional["ProFirmwareCommand"]:
        for item in ProFirmwareCommand:
            if item.value == value:
                return item
        return None


class UltimateFirmwareCommand(Enum):
    """BLE CONFIG command table for Mudra ULTIMATE — fully independent of
    ProFirmwareCommand (see that class for Pro's own table). Mirrors
    mudra_ultimate/src/bt_layer/bt_command_manager.h."""

    # System
    systemPing = 0
    systemVersion = 1
    systemSerial = 2
    systemRing = 3
    systemDeviceInfo = 4
    systemLicenseSet = 5
    systemLicenseClear = 6
    systemTsync = 7
    systemLinkstats = 8

    # EMG — trailing template bytes are SDK-filled
    enableEmg = 9
    emgOdr = 10
    emgRes = 11
    emgResMax = 12
    emgTest = 13
    emgChmask = 14
    emgRld = 15
    emgIsolate = 16
    emgStatus = 17

    # Hand IMU
    enableHImu = 18
    hImuOdr = 19
    hImuAcc = 20
    hImuGyr = 21
    hImuAccRes = 22
    hImuGyrRes = 23
    hImuAccBw = 24
    hImuGyrBw = 25
    hImuAccAvg = 26
    hImuGyrAvg = 27
    hImuStatus = 28

    # Finger IMU
    enableFImu = 29
    fImuOdr = 30
    fImuAcc = 31
    fImuGyr = 32
    fImuAccRes = 33
    fImuGyrRes = 34
    fImuAccBw = 35
    fImuGyrBw = 36
    fImuAccAvg = 37
    fImuGyrAvg = 38
    fImuStatus = 39

    # PPG
    enablePpg = 40
    ppgOdr = 41
    ppgDec = 42
    ppgLed = 43
    ppgTia = 44
    ppgPrpct = 45
    ppgClear = 46
    ppgSrc = 47
    ppgStatus = 48

    # Battery
    batStatus = 49
    batSoc = 50
    batVoltage = 51
    batCharging = 52
    batConnected = 53
    batReset = 54

    # LED
    ledSetState = 55
    ledClrState = 56
    ledRgb = 57
    ledBlink = 58
    ledOff = 59
    ledGet = 60

    # BT control
    btAdvStart = 61
    btAdvStop = 62
    btAdvGet = 63
    btConnGet = 64
    btNameSet = 65
    btNameGet = 66
    btNameReset = 67
    btPhySet = 68

    # TinyTap
    enableTap = 69

    # Storage
    storageRecordSet = 70
    storageRecordState = 71
    storageNextFileNum = 72

    # Required before SD recording. RAM-only on the device, no action byte,
    # no getter (mirrors LICENSE_SET).
    systemUserIdSet = 73

    @property
    def description(self) -> str:
        return {
            UltimateFirmwareCommand.systemPing: "SYSTEM_PING",
            UltimateFirmwareCommand.systemVersion: "SYSTEM_VERSION",
            UltimateFirmwareCommand.systemSerial: "SYSTEM_SERIAL",
            UltimateFirmwareCommand.systemRing: "SYSTEM_RING",
            UltimateFirmwareCommand.systemDeviceInfo: "SYSTEM_DEVICE_INFO",
            UltimateFirmwareCommand.systemLicenseSet: "SYSTEM_LICENSE_SET",
            UltimateFirmwareCommand.systemLicenseClear: "SYSTEM_LICENSE_CLEAR",
            UltimateFirmwareCommand.systemTsync: "SYSTEM_TSYNC",
            UltimateFirmwareCommand.systemLinkstats: "SYSTEM_LINKSTATS",
            UltimateFirmwareCommand.enableEmg: "ENABLE_EMG",
            UltimateFirmwareCommand.emgOdr: "EMG_ODR",
            UltimateFirmwareCommand.emgRes: "EMG_RES",
            UltimateFirmwareCommand.emgResMax: "EMG_RES_MAX",
            UltimateFirmwareCommand.emgTest: "EMG_TEST",
            UltimateFirmwareCommand.emgChmask: "EMG_CHMASK",
            UltimateFirmwareCommand.emgRld: "EMG_RLD",
            UltimateFirmwareCommand.emgIsolate: "EMG_ISOLATE",
            UltimateFirmwareCommand.emgStatus: "EMG_STATUS",
            UltimateFirmwareCommand.enableHImu: "ENABLE_H_IMU",
            UltimateFirmwareCommand.hImuOdr: "H_IMU_ODR",
            UltimateFirmwareCommand.hImuAcc: "H_IMU_ACC",
            UltimateFirmwareCommand.hImuGyr: "H_IMU_GYR",
            UltimateFirmwareCommand.hImuAccRes: "H_IMU_ACC_RES",
            UltimateFirmwareCommand.hImuGyrRes: "H_IMU_GYR_RES",
            UltimateFirmwareCommand.hImuAccBw: "H_IMU_ACC_BW",
            UltimateFirmwareCommand.hImuGyrBw: "H_IMU_GYR_BW",
            UltimateFirmwareCommand.hImuAccAvg: "H_IMU_ACC_AVG",
            UltimateFirmwareCommand.hImuGyrAvg: "H_IMU_GYR_AVG",
            UltimateFirmwareCommand.hImuStatus: "H_IMU_STATUS",
            UltimateFirmwareCommand.enableFImu: "ENABLE_F_IMU",
            UltimateFirmwareCommand.fImuOdr: "F_IMU_ODR",
            UltimateFirmwareCommand.fImuAcc: "F_IMU_ACC",
            UltimateFirmwareCommand.fImuGyr: "F_IMU_GYR",
            UltimateFirmwareCommand.fImuAccRes: "F_IMU_ACC_RES",
            UltimateFirmwareCommand.fImuGyrRes: "F_IMU_GYR_RES",
            UltimateFirmwareCommand.fImuAccBw: "F_IMU_ACC_BW",
            UltimateFirmwareCommand.fImuGyrBw: "F_IMU_GYR_BW",
            UltimateFirmwareCommand.fImuAccAvg: "F_IMU_ACC_AVG",
            UltimateFirmwareCommand.fImuGyrAvg: "F_IMU_GYR_AVG",
            UltimateFirmwareCommand.fImuStatus: "F_IMU_STATUS",
            UltimateFirmwareCommand.enablePpg: "ENABLE_PPG",
            UltimateFirmwareCommand.ppgOdr: "PPG_ODR",
            UltimateFirmwareCommand.ppgDec: "PPG_DEC",
            UltimateFirmwareCommand.ppgLed: "PPG_LED",
            UltimateFirmwareCommand.ppgTia: "PPG_TIA",
            UltimateFirmwareCommand.ppgPrpct: "PPG_PRPCT",
            UltimateFirmwareCommand.ppgClear: "PPG_CLEAR",
            UltimateFirmwareCommand.ppgSrc: "PPG_SRC",
            UltimateFirmwareCommand.ppgStatus: "PPG_STATUS",
            UltimateFirmwareCommand.batStatus: "BAT_STATUS",
            UltimateFirmwareCommand.batSoc: "BAT_SOC",
            UltimateFirmwareCommand.batVoltage: "BAT_VOLTAGE",
            UltimateFirmwareCommand.batCharging: "BAT_CHARGING",
            UltimateFirmwareCommand.batConnected: "BAT_CONNECTED",
            UltimateFirmwareCommand.batReset: "BAT_RESET",
            UltimateFirmwareCommand.ledSetState: "LED_SET_STATE",
            UltimateFirmwareCommand.ledClrState: "LED_CLR_STATE",
            UltimateFirmwareCommand.ledRgb: "LED_RGB",
            UltimateFirmwareCommand.ledBlink: "LED_BLINK",
            UltimateFirmwareCommand.ledOff: "LED_OFF",
            UltimateFirmwareCommand.ledGet: "LED_GET",
            UltimateFirmwareCommand.btAdvStart: "BT_ADV_START",
            UltimateFirmwareCommand.btAdvStop: "BT_ADV_STOP",
            UltimateFirmwareCommand.btAdvGet: "BT_ADV_GET",
            UltimateFirmwareCommand.btConnGet: "BT_CONN_GET",
            UltimateFirmwareCommand.btNameSet: "BT_NAME_SET",
            UltimateFirmwareCommand.btNameGet: "BT_NAME_GET",
            UltimateFirmwareCommand.btNameReset: "BT_NAME_RESET",
            UltimateFirmwareCommand.btPhySet: "BT_PHY_SET",
            UltimateFirmwareCommand.enableTap: "ENABLE_TAP",
            UltimateFirmwareCommand.storageRecordSet: "STORAGE_RECORD_SET",
            UltimateFirmwareCommand.storageRecordState: "STORAGE_RECORD_STATE",
            UltimateFirmwareCommand.storageNextFileNum: "STORAGE_NEXT_FILE_NUM",
            UltimateFirmwareCommand.systemUserIdSet: "SYSTEM_USER_ID_SET",
        }[self]

    @property
    def op_code(self) -> int:
        return self.value

    @property
    def id(self) -> bytes:
        from mudra_sdk.models.computation_wrapper import ComputationWrapper
        return ComputationWrapper.get_ultimate_firmware_command_bytes(self.op_code)

    @staticmethod
    def from_value(value: int) -> Optional["UltimateFirmwareCommand"]:
        for item in UltimateFirmwareCommand:
            if item.value == value:
                return item
        return None



class FirmwareDataType(Enum):
    emg = 0
    imuH = 1
    imuF = 2
    ppg = 3

    @property
    def value_int(self) -> int:
        return self.value

    @staticmethod
    def from_value(value: int) -> Optional["FirmwareDataType"]:
        for item in FirmwareDataType:
            if item.value == value:
                return item
        return None

class RecordingDataType(Enum):
    button = 0
    fsr = 1
    endAppTS = 2

    emg1 = 3
    emg2 = 4
    emg3 = 5
    emgTS = 6

    # Hand IMU (FirmwareDataType.imuH)
    acc1 = 7
    acc2 = 8
    acc3 = 9
    accTS = 10

    gyro1 = 11
    gyro2 = 12
    gyro3 = 13
    gyroTS = 14

    # Finger IMU (FirmwareDataType.imuF)
    accF1 = 15
    accF2 = 16
    accF3 = 17
    accFTS = 18

    gyroF1 = 19
    gyroF2 = 20
    gyroF3 = 21
    gyroFTS = 22

    ppg1 = 23
    ppg2 = 24
    ppg3 = 25
    ppg4 = 26
    ppgTS = 27

    @property
    def value_int(self) -> int:
        return self.value

    @staticmethod
    def from_value(value: int) -> Optional["RecordingDataType"]:
        for item in RecordingDataType:
            if item.value == value:
                return item
        return None


class EventType(Enum):
    buttonType = 1

    @property
    def value_int(self) -> int:
        return self.value

    @staticmethod
    def from_value(value: int) -> Optional["EventType"]:
        for item in EventType:
            if item.value == value:
                return item
        return None


class EmgRes(Enum):
    emgRes16 = 16
    emgRes24 = 24

    @property
    def value_int(self) -> int:
        return self.value

    @property
    def bits(self) -> int:
        """Wire value for EMG_RES SET/GET and STATUS (firmware uses 16 or 24)."""
        return self.value

    @staticmethod
    def from_value(value: int) -> Optional["EmgRes"]:
        """Accept wire 16/24 and legacy 0/1 encodings."""
        if value in (16, 0):
            return EmgRes.emgRes16
        if value in (24, 1):
            return EmgRes.emgRes24
        return None

    @staticmethod
    def from_bits(bits: int) -> Optional["EmgRes"]:
        return EmgRes.from_value(bits)


class ProEMGODR(Enum):
    """Valid EMG output data rates on Mudra Pro's ADS1293 AFE (see
    sensor_core/.../components/ads1293/ads1293.h — ADS1293_ODR_200..6400).
    A SET above the connected license tier's ceiling (license.c's CAPS[]:
    FREE 200, PLUS 800, PRO 6400) is rejected with ERR_LICENSE."""

    emgOdr200 = 200
    emgOdr400 = 400
    emgOdr800 = 800
    emgOdr1600 = 1600
    emgOdr2133 = 2133
    emgOdr3200 = 3200
    emgOdr4267 = 4267
    emgOdr6400 = 6400

    @property
    def value_int(self) -> int:
        return self.value

    @staticmethod
    def from_value(value: int) -> Optional["ProEMGODR"]:
        for item in ProEMGODR:
            if item.value == value:
                return item
        return None


class UltimateEMGODR(Enum):
    """Valid EMG output data rates on Mudra Ultimate's ADS1298 AFE (see
    sensor_core/.../components/ads1298/ads1298.h: "Allowed:
    500/1000/2000/4000/8000"). 8000 is intentionally omitted — no license
    tier ever permits it (license.c's CAPS[] comment: "no tier permits it —
    4000 is the ULTIMATE ceiling"), so listing it would only offer a value
    guaranteed to fail with ERR_LICENSE."""

    emgOdr500 = 500
    emgOdr1000 = 1000
    emgOdr2000 = 2000
    emgOdr4000 = 4000

    @property
    def value_int(self) -> int:
        return self.value

    @staticmethod
    def from_value(value: int) -> Optional["UltimateEMGODR"]:
        for item in UltimateEMGODR:
            if item.value == value:
                return item
        return None


class IMUODR(Enum):
    imuHOdr25 = 25
    imuHOdr50 = 50
    imuHOdr100 = 100
    imuHOdr200 = 200
    imuHOdr400 = 400
    imuHOdr800 = 800
    imuHOdr1600 = 1600

    @property
    def value_int(self) -> int:
        return self.value

    @staticmethod
    def from_value(value: int) -> Optional["IMUODR"]:
        for item in IMUODR:
            if item.value == value:
                return item
        return None

class PPGODR(Enum):
    ppgOdr25 = 25
    ppgOdr50 = 50
    ppgOdr100 = 100
    ppgOdr200 = 200
    ppgOdr400 = 400

    @property
    def value_int(self) -> int:
        return self.value
        
    @staticmethod
    def from_value(value: int) -> Optional["PPGODR"]:
        for item in PPGODR:
            if item.value == value:
                return item
        return None

class PPGChannelCount(Enum):
    ppgChannelCount1 = 1
    ppgChannelCount2 = 2
    ppgChannelCount3 = 3
    ppgChannelCount4 = 4

    @property
    def value_int(self) -> int:
        return self.value
        
    @staticmethod
    def from_value(value: int) -> Optional["PPGChannelCount"]:

        for item in PPGChannelCount:
            if item.value == value:
                return item
        return None

class IMUAccRange(Enum):
    imuAccRange2 = 2
    imuAccRange4 = 4
    imuAccRange8 = 8
    imuAccRange16 = 16

    @property
    def value_int(self) -> int:
        return self.value
        
    @staticmethod
    def from_value(value: int) -> Optional["IMUAccRange"]:
        for item in IMUAccRange:
            if item.value == value:
                return item
        return None

class IMUGyrRange(Enum):
    imuGyrRange125 = 125
    imuGyrRange250 = 250
    imuGyrRange500 = 500
    imuGyrRange1000 = 1000
    imuGyrRange2000 = 2000

    @property
    def value_int(self) -> int:
        return self.value
        
    @staticmethod
    def from_value(value: int) -> Optional["IMUGyrRange"]:
        for item in IMUGyrRange:
            if item.value == value:
                return item
        return None


class LicenseTier(Enum):
    """Firmware license tier byte, as reported in ``BT_SYS_DEVICE_INFO`` (see ``LicenseDeviceInfo.tier``)."""

    FREE = 0
    PLUS = 1
    PRO = 2

    @property
    def value_int(self) -> int:
        return self.value

    @staticmethod
    def from_value(value: int) -> Optional["LicenseTier"]:
        for item in LicenseTier:
            if item.value == value:
                return item
        return None