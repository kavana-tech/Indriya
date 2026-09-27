"""MudraUltimate — Mudra Ultimate device (8-channel EMG).

See mudra_device.py's MudraDevice for shared transport/status-parsing
plumbing common to both hardware models; this file only adds what's
Ultimate-specific.
"""

from mudra_sdk.models.enums import MudraModel, UltimateFirmwareCommand, UltimateEMGODR, BtCmdId, BtCmdStatus
from mudra_sdk.models.mudra_device import MudraDevice
import mudra_sdk.models.firmware_protocol as fp


class MudraUltimate(MudraDevice):
    """Mudra Ultimate (8-channel EMG). Adds SYSTEM_TSYNC/SYSTEM_LINKSTATS and
    the EMG bench self-test surface (input-mux TEST, CHMASK, RLD, ISOLATE) —
    see mudra_ultimate's bt_command_manager.h/cdc_commands.c for the firmware
    side. Has no packet-loss test-mode commands (that's Pro-only — see
    MudraPro)."""

    MODEL = MudraModel.ULTIMATE
    EMG_CHANNEL_COUNT = 8
    CMD = UltimateFirmwareCommand
    EMG_ODR_ENUM = UltimateEMGODR

    # ---- SYSTEM (0x00) — Ultimate-only ------------------------------------- #

    async def get_tsync(self) -> None:
        """Host clock-sync anchor: firmware echoes its live 64-bit GRTC cycle
        counter (BT_SYS_TSYNC / CDC "TSYNC?" -> "TSYNC ts_cyc=<u64>"). Reply
        arrives via the normal command-reply path — there's no dedicated
        status dataclass for this, just the raw payload."""
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.systemTsync)
            return
        await self.send_command(fp.get_standalone(self.CMD.systemTsync))

    async def get_linkstats(self) -> None:
        """BLE notification-drop stats by cause + live connection params
        (BT_SYS_LINKSTATS) — BLE-only, no CDC equivalent (confirmed against
        mudra_ultimate's cdc_commands.c)."""
        if self.transport == "cdc":
            self.on_command_error_received(BtCmdId.SYSTEM, BtCmdStatus.ERR_UNKNOWN)
            return
        await self.send_command(fp.get_standalone(self.CMD.systemLinkstats))

    # ---- EMG (0x10) — Ultimate-only bench self-test surface ---------------- #

    async def set_emg_test(self, mode: int) -> None:
        """Input mux self-test (BT_EMG_TEST / CDC "EMG_TEST"): 0=normal,
        1=test signal, 2=inputs shorted, 3=temp sensor, 4=supply monitor
        (forces gain 1, RLD parked). Applies live, mid-stream. Unrelated to
        Pro's set_emg_test_mode (a packet-loss counter overlay) — Ultimate
        has no equivalent to that Pro-only feature."""
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.emgTest, mode)
            return
        await self.send_command(fp.set_u8(self.CMD.emgTest, mode))

    async def get_emg_test(self) -> None:
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.emgTest)
            return
        await self.send_command(fp.get_paired(self.CMD.emgTest))

    async def set_emg_channel_mask(self, mask: int) -> None:
        """Power a subset of the 8 EMG channels — bit n = channel n powered
        (BT_EMG_CHMASK / CDC "EMG_CHMASK"). SET-only on both transports (no
        "?" getter registered in firmware); read current state back via
        EMG_TEST?/EMG_HEALTH? instead."""
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.emgChmask, mask)
            return
        await self.send_command(fp.set_u8(self.CMD.emgChmask, mask))

    async def set_emg_rld(self, enable: bool) -> None:
        """RLD/bias amplifier (BT_EMG_RLD / CDC "EMG_RLD"). On this board RLD
        DC-centers the body at midsupply — it is NOT a common-mode servo (see
        mudra_ultimate's CLAUDE.md for why). SET-only on both transports (no
        "?" getter registered in firmware)."""
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.emgRld, 1 if enable else 0)
            return
        await self.send_command(fp.set_bool(self.CMD.emgRld, enable))

    async def emg_isolate(self) -> None:
        """Stop PPG/IMUs/TinyTap/LEDs/advertising, leave EMG running
        (BT_EMG_ISOLATE / CDC "EMG_ISOLATE") — bare action, no action byte,
        no GET."""
        if self.transport == "cdc":
            await self._cdc_send(self._cdc_token(self.CMD.emgIsolate))
            return
        await self.send_command(fp.get_standalone(self.CMD.emgIsolate))
