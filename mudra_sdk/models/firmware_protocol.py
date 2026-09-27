"""BLE CONFIG command builders for Mudra firmware.

Frame layout (see firmware ble.md):
  request  [cmd_id, feature, action_or_payload...]
  paired features use action GET=0x00 / SET=0x01
  power features use STOP=0x00 / START=0x01
  standalone features (RES_MAX, CLEAR, …) have no action byte

Every builder is generic over which command table `cmd` comes from —
ProFirmwareCommand or UltimateFirmwareCommand (see enums.py) — since both
expose the same `.id: bytes` shape. Each enum's `.id` already resolves to
that product's own byte template, so callers never pass a device/model here;
which table a caller uses (MudraPro vs. MudraUltimate) is what selects Pro
vs. Ultimate bytes.
"""

from __future__ import annotations

from typing import Union

from mudra_sdk.models.enums import ProFirmwareCommand, UltimateFirmwareCommand

FirmwareCommand = Union[ProFirmwareCommand, UltimateFirmwareCommand]

ACT_GET = 0x00
ACT_SET = 0x01

# BT_SYS_USER_ID_SET raw payload length — shared with examples that need to
# validate/generate a user_id independent of MudraDevice.set_user_id().
USER_ID_LEN = 16


def get_paired(cmd: FirmwareCommand) -> bytes:
    tmpl = bytes(cmd.id)
    return bytes((tmpl[0], tmpl[1], ACT_GET))


def get_standalone(cmd: FirmwareCommand) -> bytes:
    tmpl = bytes(cmd.id)
    return tmpl[:2]


def set_u8(cmd: FirmwareCommand, value: int) -> bytes:
    tmpl = bytearray(cmd.id)
    tmpl[2] = ACT_SET
    tmpl[3] = value & 0xFF
    return bytes(tmpl[:4])


def set_u16(cmd: FirmwareCommand, value: int) -> bytes:
    tmpl = bytearray(cmd.id)
    tmpl[2] = ACT_SET
    tmpl[3] = value & 0xFF
    tmpl[4] = (value >> 8) & 0xFF
    return bytes(tmpl[:5])


def set_bool(cmd: FirmwareCommand, enabled: bool) -> bytes:
    return set_u8(cmd, 1 if enabled else 0)


def set_power(cmd: FirmwareCommand, enable: bool) -> bytes:
    """POWER-style command: ``[cmd_id, feature, STOP(0)|START(1)]`` — 3 bytes,
    no separate action byte (unlike the paired GET/SET features above)."""
    tmpl = bytearray(cmd.id)
    tmpl[2] = 1 if enable else 0
    return bytes(tmpl[:3])


# ---- PPG multi-arg helpers (cmd 0x40) -------------------------------------- #
# Byte-identical on Pro and Ultimate (feature bytes 0x03/0x04/0x07 aren't
# among the ones that differ), so these stay literal-byte builders rather
# than going through a per-product enum.

def ppg_led_get(ch: int) -> bytes:
    return bytes((0x40, 0x03, ACT_GET, ch & 0xFF))


def ppg_led_set(ch: int, drv1: int, drv2: int) -> bytes:
    return bytes((0x40, 0x03, ACT_SET, ch & 0xFF, drv1 & 0xFF, drv2 & 0xFF))


def ppg_tia_get(ch: int) -> bytes:
    return bytes((0x40, 0x04, ACT_GET, ch & 0xFF))


def ppg_tia_set(ch: int, rf: int, cf: int) -> bytes:
    return bytes((0x40, 0x04, ACT_SET, ch & 0xFF, rf & 0xFF, cf & 0xFF))


def ppg_src_get(ch: int) -> bytes:
    return bytes((0x40, 0x07, ACT_GET, ch & 0xFF))


def ppg_src_set(ch: int, led: int, pd: int) -> bytes:
    return bytes((0x40, 0x07, ACT_SET, ch & 0xFF, led & 0xFF, pd & 0xFF))


def ppg_clear(cmd: FirmwareCommand) -> bytes:
    return get_standalone(cmd)
