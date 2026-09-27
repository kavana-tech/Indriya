"""Standalone CDC (USB serial) transport service, mirroring BleService's shape.

A Mudra Pro exposes two USB CDC-ACM virtual COM ports under one composite USB
device (VID `0x2FE3` / PID `0x0001`): `CONFIG` (bidirectional ASCII commands)
and `DATA` (binary sensor stream; host only ever sends the `CDC?` handshake).
See `docs/usb-cdc.md` in the firmware repo for the full protocol.

Kept as an independent sibling of `BleService` (not behind a shared transport
interface) — see the standalone-services-first preference recorded for this
codebase. `send_command`/`query` speak the device's native ASCII grammar
directly (e.g. `"EMG_ON"`, `"EMG_ODR?"` -> `"EMG_ODR 800"`) rather than
reusing BLE's binary `[cmd_id, feature, ...]` frames, which the firmware does
not accept on the CONFIG port.
"""

import asyncio
import re
import struct
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import serial
import serial.tools.list_ports

from mudra_sdk.models.cdc_device import CdcDevice
from mudra_sdk.models.enums import (
    BtCmdProEMG,
    BtCmdFIMU,
    BtCmdHIMU,
    BtCmdId,
    BtCmdPPG,
    BtCmdStatus,
    BtCmdUltimateEMG,
    FirmwareCallbacks,
    MudraModel,
    SensorTypes,
    cmdType,
)
from ..models.callbacks import CdcServiceDelegate
from ..logging_config import get_logger

logger = get_logger(__name__)

# ASCII leading token -> BtCmdId, for mapping a setter's "<TOKEN> ERROR ..."
# ack back to the same command-id space BLE's status-only replies use.
# "LICENSE" also covers "LICENSE_CLEAR" (startswith("LICENSE_") below).
_CDC_ERROR_TOKEN_PREFIXES = {
    "EMG": BtCmdId.EMG,
    "H_IMU": BtCmdId.H_IMU,
    "F_IMU": BtCmdId.F_IMU,
    "PPG": BtCmdId.PPG,
    "BAT": BtCmdId.BAT,
    "LED": BtCmdId.LED,
    "BT": BtCmdId.BT_CTRL,
    "LICENSE": BtCmdId.SYSTEM,
}


def _cdc_cmd_id_for_token(token: str) -> Optional[BtCmdId]:
    for prefix, cmd_id in _CDC_ERROR_TOKEN_PREFIXES.items():
        if token == prefix or token.startswith(prefix + "_"):
            return cmd_id
    return None

# VERSION's reply is firmware's Zephyr APP_VERSION_STRING ("Version: 2.0.2")
# — a free-form string, not a "<TOKEN> field field ..." combined-status line,
# so it needs its own regex rather than a from_cdc_line() token match. Only
# major.minor.patchlevel are present in that string (Zephyr's macro drops
# VERSION_TWEAK); an optional 4th component is accepted for forward
# compatibility but is normally absent, so tweak defaults to 0 here — unlike
# BLE's BT_SYS_VERSION reply, which always carries the real tweak byte.
# mudra_ultimate's h_version() additionally appends " git=<hash>[+]" (the same
# provenance MUDRA_GIT_HASH/DEVICE_INFO carry, "+" meaning a dirty build tree)
# — optional and ignored here so it doesn't break the match, present or not.
_VERSION_LINE_RE = re.compile(
    r"^Version:\s*(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?(?:\s+git=\S+)?\s*$", re.IGNORECASE
)

# DEVICE_INFO?'s reply (h_device_info() in cdc_handlers.c) is a free-form
# "key=value" line, not a "<TOKEN> field field ..." combined-status line, so
# it needs its own regex too. token_tier/issued are CDC-only extras with no
# BLE counterpart (BT_SYS_DEVICE_INFO's binary reply carries neither) and are
# intentionally not captured here. A firmware build of 2026-09-08 appends a
# trailing " usb_sn=<hex>" field (multi-unit identification -- see
# docs/host-examples/multi_pro/SDK_HANDOFF.md in the firmware repo for the
# fuller change the SDK is asked to make around it); matched-but-ignored here
# so it doesn't break this line's parsing on newer firmware, and optional so
# older firmware without it still matches. mudra_ultimate additionally inserts
# " init_faults=<hex>" (see main.c's partial-boot bitmask) before usb_sn and
# appends " git=<hash>[+]" after it — both matched-but-ignored, both optional,
# same reasoning as usb_sn above.
_DEVICE_INFO_LINE_RE = re.compile(
    r"^DEVICE_INFO serial=(\S+) fw=\d+\.\d+\.\d+ tier=(\d+) token_tier=\d+ valid=(\d+) "
    r"now=(\d+) floor=(\d+) issued=\d+ expires=(\d+)"
    r"(?: init_faults=\S+)?(?: usb_sn=\S+)?(?: git=\S+)?\s*$"
)
_DEVICE_INFO_SERIAL_LEN = 13

# BAT_SOC?/BAT_CHG? replies (h_bat_soc()/h_bat_chg() in cdc_handlers.c) — the
# CDC analogues of BLE's GATT Battery Service / power-state notifications.
# Deliberately not the combined BAT? line (h_bat_status(), volts/current/temp/
# etc.): BLE only ever pushes level + charging, so only those two get parsed.
_BAT_SOC_LINE_RE = re.compile(r"^BAT_SOC (\d+)\s*$")
_BAT_CHG_LINE_RE = re.compile(r"^BAT_CHG ([01])\s*$")

MUDRA_USB_VID = 0x2FE3
MUDRA_USB_PID = 0x0001

# Nominal USB-CDC baud. The pro is a USB CDC ACM device, so the host-side
# baudrate is ignored by the link — any value works, this is just the
# canonical one used elsewhere (e.g. the reference Pro_SDK serial transport).
BAUDRATE = 921600

_PROBE_TIMEOUT = 0.6
_DATA_READ_TIMEOUT = 0.1
_CONFIG_READ_TIMEOUT = 0.5


@dataclass
class _CdcConnection:
    device: CdcDevice
    config_ser: serial.Serial
    data_ser: Optional[serial.Serial]
    loop: asyncio.AbstractEventLoop
    reader_thread: Optional[threading.Thread] = None
    stop_event: threading.Event = None
    config_lock: asyncio.Lock = None

    def __post_init__(self):
        if self.stop_event is None:
            self.stop_event = threading.Event()
        if self.config_lock is None:
            self.config_lock = asyncio.Lock()


class CdcService:
    _instance = None
    _delegate: Optional[CdcServiceDelegate] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, delegate: CdcServiceDelegate):
        if not hasattr(self, '_initialized'):
            self._delegate = delegate
            self._discovered_devices: Dict[str, CdcDevice] = {}
            self._connections: Dict[str, _CdcConnection] = {}
            self._scan_task: Optional[asyncio.Task] = None
            self._initialized = True

    ### ----------------------- Connection Methods ----------------------- ###

    async def connect(self, device: CdcDevice):
        address = device.address
        if address in self._connections:
            logger.warning(f"CDC device {address} is already connected")
            return

        if self._delegate:
            self._delegate.on_mudra_device_connecting(device)

        loop = asyncio.get_running_loop()
        try:
            config_ser, data_ser = await loop.run_in_executor(None, self._open_ports, device)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to connect to CDC device {address}: {error_msg}")
            if self._delegate:
                self._delegate.on_mudra_device_connection_failed(device, error_msg)
                # USB pulled mid-handshake: report the drop too.
                ports = await loop.run_in_executor(None, serial.tools.list_ports.comports)
                if device.config_port not in {p.device for p in ports}:
                    self._delegate.on_mudra_device_disconnected(device)
            return

        conn = _CdcConnection(device=device, config_ser=config_ser, data_ser=data_ser, loop=loop)
        self._connections[address] = conn

        if data_ser is not None:
            self._start_reader(conn)

        logger.info(f"Successfully connected to CDC device {device.name} ({address})")
        if self._delegate:
            await self._delegate.on_mudra_device_connected(device)

    def _open_ports(self, device: CdcDevice):
        """Open + handshake both CDC ports. Runs on a worker thread."""
        config_ser = serial.Serial(device.config_port, BAUDRATE, timeout=_CONFIG_READ_TIMEOUT)
        role = self._handshake(config_ser)
        if role != "CONFIG":
            config_ser.close()
            raise RuntimeError(f"{device.config_port} did not answer CDC? as CONFIG (got {role!r})")

        data_ser = None
        if device.data_port:
            data_ser = serial.Serial(device.data_port, BAUDRATE, timeout=_DATA_READ_TIMEOUT)
            role = self._handshake(data_ser)
            if role != "DATA":
                data_ser.close()
                config_ser.close()
                raise RuntimeError(f"{device.data_port} did not answer CDC? as DATA (got {role!r})")

        return config_ser, data_ser

    @staticmethod
    def _handshake(ser: serial.Serial) -> Optional[str]:
        ser.reset_input_buffer()
        ser.write(b"CDC?\r\n")
        ser.flush()
        deadline = time.monotonic() + _PROBE_TIMEOUT
        buf = b""
        while time.monotonic() < deadline:
            buf += ser.read(256)
            if b"CONFIG" in buf:
                return "CONFIG"
            if b"DATA" in buf:
                return "DATA"
        return None

    def _start_reader(self, conn: _CdcConnection):
        conn.stop_event.clear()
        thread = threading.Thread(
            target=self._reader_loop, args=(conn,), daemon=True,
            name=f"CdcReader({conn.device.data_port})",
        )
        conn.reader_thread = thread
        thread.start()

    def _reader_loop(self, conn: _CdcConnection):
        ser = conn.data_ser
        address = conn.device.address
        try:
            while not conn.stop_event.is_set():
                chunk = ser.read(4096)
                if chunk and self._delegate:
                    conn.loop.call_soon_threadsafe(
                        self._delegate.on_data_received, address, bytes(chunk)
                    )
        except Exception as e:
            if not conn.stop_event.is_set():  # not our own teardown -> USB dropped
                logger.warning(f"CDC device {address} disconnected unexpectedly: {e}")
                conn.loop.call_soon_threadsafe(self._on_connection_lost, conn)

    def _on_connection_lost(self, conn: _CdcConnection):
        """CDC counterpart of `BleService._on_disconnect_callback`."""
        if self._connections.get(conn.device.address) is not conn:
            return  # disconnect() already tearing it down
        del self._connections[conn.device.address]
        conn.loop.run_in_executor(None, self._teardown_connection, conn)
        if self._delegate:
            self._delegate.on_mudra_device_disconnected(conn.device)

    async def disconnect(self, device: CdcDevice):
        address = device.address
        conn = self._connections.get(address)
        if conn is None:
            logger.warning(f"CDC device {address} is not connected")
            return

        if self._delegate:
            self._delegate.on_mudra_device_disconnecting(device)

        del self._connections[address]
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._teardown_connection, conn)

        logger.info(f"Successfully disconnected from CDC device {device.name} ({address})")
        if self._delegate:
            self._delegate.on_mudra_device_disconnected(device)

    def _teardown_connection(self, conn: _CdcConnection):
        conn.stop_event.set()
        if conn.reader_thread is not None:
            conn.reader_thread.join(timeout=2.0)
        for ser in (conn.data_ser, conn.config_ser):
            try:
                if ser is not None and ser.is_open:
                    ser.close()
            except Exception:
                pass

    async def disconnect_all(self):
        for address in list(self._connections.keys()):
            conn = self._connections[address]
            try:
                await self.disconnect(conn.device)
            except Exception as e:
                logger.error(f"Error disconnecting CDC device {address}: {e}")

    def is_connected(self, device: CdcDevice) -> bool:
        conn = self._connections.get(device.address)
        return conn is not None and conn.config_ser.is_open

    def get_connected_devices(self) -> List[CdcDevice]:
        return [conn.device for conn in self._connections.values()]

    ### ------------------------- Command Methods ------------------------- ###

    async def send_command(self, device: CdcDevice, command: str) -> None:
        """Send one ASCII command line over the CONFIG port (no reply read)."""
        conn = self._connections.get(device.address)
        if conn is None:
            logger.warning(f"CDC device {device.address} is not connected")
            return
        loop = asyncio.get_running_loop()
        async with conn.config_lock:
            await loop.run_in_executor(None, self._write_line, conn, command)

    def _write_line(self, conn: _CdcConnection, command: str) -> None:
        logger.debug(f"Sending CDC command: {command}")
        conn.config_ser.reset_input_buffer()
        conn.config_ser.write(command.encode("ascii") + b"\r\n")
        conn.config_ser.flush()

    async def query(self, device: CdcDevice, command: str, settle: float = 0.1) -> str:
        """Send an ASCII command and return the device's reply line (stripped).

        Also classifies the reply the way `BleService._command_notification_handler`
        classifies a binary GATT notification — via `_dispatch_reply` below —
        so a delegate sees the same typed events (`on_sensor_status_received`,
        `on_command_error_received`, ...) regardless of transport, not just
        the one awaiting this call.

        Serialized per-connection (`conn.config_lock`): the CONFIG port is one
        physical serial link, so two overlapping request/reply cycles would
        otherwise race — one call's `reset_input_buffer()` can wipe out
        another's reply before it's read. Concurrent callers (e.g. several
        status queries fired via `asyncio.create_task`) simply queue here
        instead of corrupting each other's replies.
        """
        conn = self._connections.get(device.address)
        if conn is None:
            logger.warning(f"CDC device {device.address} is not connected")
            return ""
        loop = asyncio.get_running_loop()
        async with conn.config_lock:
            raw_reply = await loop.run_in_executor(None, self._query_sync, conn, command, settle)
        # A single blind read can catch more than one line: firmware pushes
        # a state-change notification (e.g. "EMG 1 3200 16") *before* it acks
        # the command that triggered it (e.g. "EMG_ON OK") — see
        # peripherals_emg_start()/on_emg_state_change() in the firmware.
        # Dispatch each line on its own; the direct reply to `command` is
        # always the last one.
        lines = [l for l in raw_reply.splitlines() if l]
        for line in lines:
            self._dispatch_reply(device, line)
        return lines[-1] if lines else ""

    def _dispatch_reply(self, device: CdcDevice, line: str) -> None:
        """Classify one CONFIG-port reply line and call the matching typed
        delegate method directly — the ASCII counterpart to
        `BleService._command_notification_handler`'s binary match/case."""
        if not self._delegate:
            return
        address = device.address
        parts = line.split()
        if not parts:
            return
        token, rest = parts[0], parts[1:]

        # Check for an error ack first — a combined-status query can itself
        # fail (e.g. "F_IMU ERROR" on a license-gated sensor), and its token
        # matches a FirmwareCallbacks status case just like real status data
        # would, so this must be ruled out before attempting to decode
        # numeric fields. CDC has no numeric status code, so the mapping is
        # necessarily best-effort: "running"/"license" are the shared-setter
        # reasons (see CLAUDE.md's config-while-running guard / tier gate);
        # "format"/"bind"/"expired"/"internal" are h_license_set's own
        # reasons (license.c's license_apply_token) — anything else (e.g. a
        # bare numeric errno, as some getters emit) becomes ERR_UNKNOWN.
        if rest and rest[0].upper() == "ERROR":
            cmd_id = _cdc_cmd_id_for_token(token)
            if cmd_id is not None:
                reason = rest[1].lower() if len(rest) > 1 else ""
                status = {
                    "running": BtCmdStatus.ERR_BUSY,
                    "license": BtCmdStatus.ERR_LICENSE,
                    "format": BtCmdStatus.ERR_INVALID,
                    "bind": BtCmdStatus.ERR_LICENSE,
                    "expired": BtCmdStatus.ERR_LICENSE,
                    "internal": BtCmdStatus.ERR_INTERNAL,
                }.get(reason, BtCmdStatus.ERR_UNKNOWN)
                logger.warning(f"CDC command error from {address}: {line!r} -> {cmd_id.name}/{status.name}")
                self._delegate.on_command_error_received(address, cmd_id, status)
                return

        version_match = _VERSION_LINE_RE.match(line)
        if version_match:
            # Re-encode into the exact [0xF0, cmd_id, maj, min, patch, tweak]
            # frame BLE's BT_SYS_VERSION reply already uses, so both
            # transports share MudraDevice._parse_firmware_version's one
            # decoder — same pattern as _emit_sensor_status below.
            major, minor, patch, tweak = (
                int(g) if g is not None else 0 for g in version_match.groups()
            )
            frame = bytes([cmdType.BT_CMD_RESPONSE_HEADER.value_int, BtCmdId.SYSTEM.value_int, major, minor, patch, tweak])
            self._delegate.on_firmware_version_received(address, frame)
            return

        device_info_match = _DEVICE_INFO_LINE_RE.match(line)
        if device_info_match:
            # Re-encode into the exact [0xF0, SYSTEM, tier, valid, now32,
            # floor32, expires32, serial[13]] frame BLE's BT_SYS_DEVICE_INFO
            # reply already uses, so both transports share MudraDevice
            # ._on_license_device_info_received's one decoder — same pattern
            # as the VERSION line above.
            serial, tier, valid, now, floor, expires_at = device_info_match.groups()
            serial_bytes = serial.encode("ascii", errors="replace")[:_DEVICE_INFO_SERIAL_LEN]
            serial_bytes = serial_bytes.ljust(_DEVICE_INFO_SERIAL_LEN, b"\x00")
            payload = struct.pack("<BBIII", int(tier), int(valid), int(now), int(floor), int(expires_at))
            frame = bytes([cmdType.BT_CMD_RESPONSE_HEADER.value_int, BtCmdId.SYSTEM.value_int]) + payload + serial_bytes
            self._delegate.on_device_info_received(address, frame)
            return

        bat_soc_match = _BAT_SOC_LINE_RE.match(line)
        if bat_soc_match:
            self._delegate.on_battery_level_changed(address, int(bat_soc_match.group(1)))
            return

        bat_chg_match = _BAT_CHG_LINE_RE.match(line)
        if bat_chg_match:
            self._delegate.on_charging_state_changed(address, bat_chg_match.group(1) == "1")
            return

        firmware_callback = FirmwareCallbacks.from_cdc_line(line)
        match firmware_callback:
            case FirmwareCallbacks.EMG_STATUS:
                # EMG_STATE's feature byte differs by model (0x04 Pro / 0x08
                # Ultimate — see enums.py's EMG_STATUS_BYTES_ULTIMATE).
                # MudraDevice.on_sensor_status_received's payload slicing is
                # offset-based and doesn't actually check this byte, so this
                # was functionally harmless either way — fixed for
                # correctness/consistency with the synthesized frame BLE
                # would have sent for the same device.
                emg_feature = BtCmdUltimateEMG.STATE.value_int if device.model == MudraModel.ULTIMATE else BtCmdProEMG.STATE.value_int
                self._emit_sensor_status(address, SensorTypes.EMG, line, BtCmdId.EMG, emg_feature, "<BHB")
            case FirmwareCallbacks.H_IMU_STATUS:
                self._emit_sensor_status(address, SensorTypes.H_IMU, line, BtCmdId.H_IMU, BtCmdHIMU.STATE.value_int, "<BHBH")
            case FirmwareCallbacks.F_IMU_STATUS:
                self._emit_sensor_status(address, SensorTypes.F_IMU, line, BtCmdId.F_IMU, BtCmdFIMU.STATE.value_int, "<BHBH")
            case FirmwareCallbacks.PPG_STATUS:
                self._emit_sensor_status(address, SensorTypes.PPG, line, BtCmdId.PPG, BtCmdPPG.STATE.value_int, "<BHB")
            case _:
                # Not a combined-status push — a setter's "<TOKEN> OK" ack or
                # a plain GET reply.
                self._delegate.on_command_reply_received(address, line)

    def _emit_sensor_status(
        self,
        address: str,
        sensor_type: SensorTypes,
        line: str,
        cmd_id: BtCmdId,
        feature: int,
        fmt: str,
    ) -> None:
        """Re-encode a combined-status line's numeric fields into the exact
        ``[0xF0, cmd_id, feature, payload...]`` frame BLE already produces,
        so both transports share `MudraDevice.on_sensor_status_received`'s
        one binary decoder. `feature` is a raw byte value (not an Enum) since
        EMG's differs by model — see the EMG_STATUS case above."""
        fields = line.split()[1:]
        try:
            payload = struct.pack(fmt, *(int(f) for f in fields))
        except (ValueError, struct.error):
            logger.warning(f"CDC status line doesn't match {sensor_type.name} shape: {line!r}")
            return
        frame = bytes([cmdType.BT_CMD_RESPONSE_HEADER.value_int, cmd_id.value_int, feature]) + payload
        self._delegate.on_sensor_status_received(address, sensor_type, frame)

    def _query_sync(self, conn: _CdcConnection, command: str, settle: float) -> str:
        self._write_line(conn, command)
        time.sleep(settle)
        raw = conn.config_ser.read(conn.config_ser.in_waiting or 1)
        return raw.decode("ascii", errors="replace").strip()

    async def ping(self, device: CdcDevice) -> bool:
        """Round-trip probe via the `CDC?` handshake (CDC has no PING token)."""
        reply = await self.query(device, "CDC?")
        ok = "CONFIG" in reply.upper()
        if ok and self._delegate:
            self._delegate.on_ping_response_received(device.address)
        return ok

    ### ----------------------- Scan/Discovery Methods ---------------------- ###

    @property
    def _is_scanning(self) -> bool:
        return self._scan_task is not None and not self._scan_task.done()

    async def scan(self, poll_interval: float = 2.0):
        """Start polling for Mudra Pro CDC port pairs."""
        if self._is_scanning:
            return
        logger.info("Starting CDC scan")
        self._discovered_devices.clear()
        self._scan_task = asyncio.create_task(self._scan_loop(poll_interval))

    async def stop_scanning(self):
        if not self._is_scanning:
            return
        logger.info("Stopping CDC scan")
        self._scan_task.cancel()
        try:
            await self._scan_task
        except asyncio.CancelledError:
            pass
        self._scan_task = None

    async def _scan_loop(self, poll_interval: float):
        loop = asyncio.get_running_loop()
        try:
            while True:
                devices = await loop.run_in_executor(None, self._find_devices)
                for device in devices:
                    # Compare by value, not just address: a device whose DATA
                    # port probe transiently failed on an earlier poll (e.g.
                    # the port was still binding right after enumeration) is
                    # re-announced once the retry inside _find_devices/a later
                    # poll fills it in, instead of being stuck with a stale
                    # data_port=None forever.
                    if self._discovered_devices.get(device.address) != device:
                        self._discovered_devices[device.address] = device
                        if self._delegate:
                            self._delegate.on_device_discovered(device)
                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            raise

    def _find_devices(self) -> List[CdcDevice]:
        """Find attached Mudra Pro CDC port pairs. Runs on a worker thread.

        Candidate ports are grouped by USB serial number (each physical
        device's two composite CDC-ACM interfaces share one), then each port
        in a group is probed via `CDC?` to tell CONFIG from DATA apart.
        """
        candidates = [
            p for p in serial.tools.list_ports.comports()
            if p.vid == MUDRA_USB_VID and p.pid == MUDRA_USB_PID
        ]
        groups: Dict[str, list] = {}
        for p in candidates:
            key = p.serial_number or p.device
            groups.setdefault(key, []).append(p)

        devices: List[CdcDevice] = []
        for serial_number, ports in groups.items():
            data_port, config_port = self._scan_roles_with_retry([p.device for p in ports])
            if config_port is None:
                continue
            has_serial = any(p.serial_number for p in ports)
            model = self._probe_model(config_port)
            name = "Mudra Ultimate (CDC)" if model == MudraModel.ULTIMATE else "Mudra Pro (CDC)"
            devices.append(CdcDevice(
                address=serial_number,
                name=name,
                config_port=config_port,
                data_port=data_port,
                serial_number=serial_number if has_serial else None,
                model=model,
            ))
        return devices

    def _probe_model(self, config_port: str) -> MudraModel:
        """Classify Pro vs. Ultimate over the CONFIG port. Both products
        share an identical USB VID/PID/product string, so there's no
        descriptor-level discriminator (see cdc_device.py) — instead, probe
        with "TSYNC?": Ultimate registers that token (replies
        "TSYNC ts_cyc=<u64>"); Pro has no such command, so its shared
        dispatcher (byte-identical to Ultimate's for every command both
        products share) falls through to "UNKNOWN". Read-only, no side
        effects. Runs on the same worker thread as the rest of _find_devices."""
        try:
            with serial.Serial(config_port, BAUDRATE, timeout=_PROBE_TIMEOUT) as s:
                s.reset_input_buffer()
                s.write(b"TSYNC?\r\n")
                s.flush()
                deadline = time.monotonic() + _PROBE_TIMEOUT
                buf = b""
                while time.monotonic() < deadline:
                    buf += s.read(256)
                    if b"TSYNC" in buf:
                        return MudraModel.ULTIMATE
                    if b"UNKNOWN" in buf:
                        return MudraModel.PRO
        except Exception as e:
            logger.warning(f"CDC model probe failed for {config_port}: {e}")
        return MudraModel.PRO

    def _scan_roles_with_retry(self, candidates: List[str], attempts: int = 3, backoff: float = 0.3):
        """Probe `candidates` for CONFIG/DATA roles, retrying while a role is
        still missing. Guards against a port that hasn't finished driver
        binding yet right after enumeration — a real single-CONFIG-only
        device (no data port at all) still resolves after `attempts`."""
        data_port = None
        config_port = None
        for attempt in range(attempts):
            d, c = self._scan_roles(candidates)
            data_port = data_port or d
            config_port = config_port or c
            if data_port and config_port:
                break
            if len(candidates) > 1 and attempt < attempts - 1:
                time.sleep(backoff)
            else:
                break
        return data_port, config_port

    def _scan_roles(self, candidates: List[str]):
        data_port = None
        config_port = None
        for dev in candidates:
            role = self._probe_cdc_role(dev)
            if role == "DATA":
                data_port = dev
            elif role == "CONFIG":
                config_port = dev
        return data_port, config_port

    def _probe_cdc_role(self, dev: str) -> Optional[str]:
        try:
            with serial.Serial(dev, BAUDRATE, timeout=0.2) as s:
                return self._handshake(s)
        except Exception:
            return None
