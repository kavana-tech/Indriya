"""MudraPro — Mudra Pro device (3-channel EMG).

See mudra_device.py's MudraDevice for shared transport/status-parsing
plumbing common to both hardware models; this file only adds what's
Pro-specific.
"""

from mudra_sdk.models.enums import MudraModel, ProFirmwareCommand, ProEMGODR, FirmwareDataType
from mudra_sdk.models.mudra_device import MudraDevice
import mudra_sdk.models.firmware_protocol as fp


class MudraPro(MudraDevice):
    """Mudra Pro (3-channel EMG). Adds the packet-loss test-mode commands —
    present on Pro's IMU_H/IMU_F/PPG/EMG firmware, absent on Ultimate (which
    has its own, unrelated EMG bench self-test surface instead — see
    MudraUltimate.set_emg_test)."""

    MODEL = MudraModel.PRO
    EMG_CHANNEL_COUNT = 3
    EMG_ODR_ENUM = ProEMGODR
    CMD = ProFirmwareCommand

    # ---- Packet-loss test mode (Pro-only) ---------------------------------- #

    async def set_emg_test_mode(self, enable: bool) -> None:
        """Packet-loss test: over BLE this is one combined firmware command
        (`handle_sensor_test_mode(emg_test_set, emg_power)` in
        bt_command_manager.c) that both replaces ch1 with an incrementing
        counter AND starts/stops EMG. CDC's ASCII equivalent, `EMG_TESTMODE`,
        only calls `emg_set_test_mode` — firmware's own comment says it's
        "deliberately NOT gated on m_is_running" (a pure software overlay),
        so it does NOT power the sensor on/off by itself over CDC. This
        method sends only that one command either way, matching BLE's single
        `EMG_TESTMODE`/`TEST_MODE` token — over CDC, EMG must already be (or
        separately be made) enabled for the counter substitution to actually
        appear in the DATA stream. Entirely independent of set_on_emg_ready.
        Read results via sample_emg_packet_loss()."""
        if enable:
            self._computation_wrapper.reset_packet_loss_stats(FirmwareDataType.emg.value)
            self._emg_packet_loss.reset()
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.emgTestMode, 1 if enable else 0)
            return
        await self.send_command(fp.set_power(self.CMD.emgTestMode, enable))

    async def set_h_imu_test_mode(self, enable: bool) -> None:
        """Packet-loss test: BLE combines this into one firmware command
        (`handle_sensor_test_mode`) that both replaces accel-x (ch0) with an
        incrementing counter AND starts/stops H_IMU. CDC's `H_IMU_TESTMODE`
        only toggles the software overlay, same as EMG's — this method sends
        only that one command either way; over CDC, H_IMU must already be
        (or separately be made) enabled for the counter substitution to
        actually appear in the DATA stream. Independent of
        set_on_imu_h_ready. Read results via sample_h_imu_packet_loss()."""
        if enable:
            self._computation_wrapper.reset_packet_loss_stats(FirmwareDataType.imuH.value)
            self._h_imu_packet_loss.reset()
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.hImuTestMode, 1 if enable else 0)
            return
        await self.send_command(fp.set_power(self.CMD.hImuTestMode, enable))

    async def set_f_imu_test_mode(self, enable: bool) -> None:
        """Packet-loss test: BLE combines this into one firmware command
        (`handle_sensor_test_mode`) that both replaces accel-x (ch0) with an
        incrementing counter AND starts/stops F_IMU. CDC's `F_IMU_TESTMODE`
        only toggles the software overlay — this method sends only that one
        command either way; over CDC, F_IMU must already be (or separately
        be made) enabled for the counter substitution to actually appear in
        the DATA stream. Independent of set_on_imu_f_ready. Read results via
        sample_f_imu_packet_loss()."""
        if enable:
            self._computation_wrapper.reset_packet_loss_stats(FirmwareDataType.imuF.value)
            self._f_imu_packet_loss.reset()
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.fImuTestMode, 1 if enable else 0)
            return
        await self.send_command(fp.set_power(self.CMD.fImuTestMode, enable))

    async def set_ppg_test_mode(self, enable: bool) -> None:
        """Packet-loss test: BLE combines this into one firmware command
        (`handle_sensor_test_mode`) that both replaces ch0 with an
        incrementing counter AND starts/stops PPG. CDC's `PPG_TESTMODE`
        only toggles the software overlay — this method sends only that one
        command either way; over CDC, PPG must already be (or separately be
        made) enabled for the counter substitution to actually appear in
        the DATA stream. Independent of set_on_ppg_ready. Read results via
        sample_ppg_packet_loss()."""
        if enable:
            self._computation_wrapper.reset_packet_loss_stats(FirmwareDataType.ppg.value)
            self._ppg_packet_loss.reset()
        if self.transport == "cdc":
            await self._cdc_command(self.CMD.ppgTestMode, 1 if enable else 0)
            return
        await self.send_command(fp.set_power(self.CMD.ppgTestMode, enable))
