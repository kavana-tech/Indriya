"""Status formatters, indicators, and firmware callback registration."""

from __future__ import annotations

from typing import Optional

from mudra_sdk import MudraDevice
from mudra_sdk.models.enums import BtCmdId, BtCmdStatus, LicenseTier
from mudra_sdk.models.mudra_device import (
    EmgStatus,
    FirmwareVersion,
    ImuStatus,
    LicenseDeviceInfo,
    PpgStatus,
    RecordStatus,
)
from mudra_sdk.logging_config import get_logger

from .anim import set_indicator, set_text
from .state import AppState
from .theme import ACCENT, ERR, FG_MUTED, OK, WARN

logger = get_logger(__name__)

_CONFIG_KEY = {
    "EMG": "EMG",
    "IMU_H": "H_IMU",
    "IMU_F": "F_IMU",
    "PPG": "PPG",
}


def format_emg_status(status: EmgStatus) -> str:
    state = "ON" if status.enabled else "OFF"
    return f"{state} · {status.odr_sps.value_int} Hz · {status.resolution_bits.bits}-bit"


def format_imu_status(status: ImuStatus) -> str:
    state = "ON" if status.enabled else "OFF"
    return (
        f"{state} · {status.odr_hz.value_int} Hz · "
        f"±{status.accel_range_g.value_int}g · ±{status.gyro_range_dps.value_int}dps"
    )


def format_ppg_status(status: PpgStatus) -> str:
    state = "ON" if status.enabled else "OFF"
    return (
        f"{state} · {status.odr_hz.value_int} Hz · "
        f"{status.channel_count.value_int} ch"
    )


def format_record_status(status: RecordStatus) -> str:
    sensors = []
    if status.emg:
        sensors.append("EMG")
    if status.ppg:
        sensors.append("PPG")
    if status.imu_hand:
        sensors.append("H_IMU")
    if status.imu_ring:
        sensors.append("F_IMU")
    active = "ON" if status.active else "OFF"
    which = ",".join(sensors) if sensors else "none"
    return f"{active}  sensors=[{which}]  file={status.file_num}"


def update_sensor_indicator(
    state: AppState,
    sensor_key: str,
    *,
    enabled: Optional[bool],
    summary: str,
    config_key: Optional[str] = None,
) -> None:
    ui = state.sensor_status_ui.get(sensor_key)
    if ui is not None:
        if enabled is None:
            color = FG_MUTED
        elif enabled:
            color = OK
        else:
            color = ERR
        set_indicator(ui["dot"], color)
        set_text(ui["text"], summary, foreground=FG_MUTED)

    cfg_key = config_key or sensor_key
    fg = OK if enabled else (ERR if enabled is False else FG_MUTED)
    for label in state.config_status_labels.get(cfg_key, []):
        set_text(label, summary, foreground=fg)


def format_license_device_info(info: LicenseDeviceInfo) -> str:
    validity = "valid" if info.valid else "invalid"
    serial = f" · {info.serial}" if info.serial else ""
    return f"License {info.tier.name} · {validity}{serial}"


def update_license_indicator(
    state: AppState, info: Optional[LicenseDeviceInfo]
) -> None:
    if state.license_tier_dot is None or state.license_tier_label is None:
        return
    if info is None:
        set_indicator(state.license_tier_dot, FG_MUTED)
        set_text(state.license_tier_label, "License —", foreground=FG_MUTED)
        return

    text = format_license_device_info(info)
    if not info.valid:
        color = ERR
    elif info.tier is LicenseTier.PRO:
        color = ACCENT
    elif info.tier is LicenseTier.PLUS:
        color = OK
    else:
        color = WARN
    set_indicator(state.license_tier_dot, color)
    set_text(state.license_tier_label, text, foreground=color)


def format_firmware_version(info: FirmwareVersion) -> str:
    return f"FW {info.version_string}"


def update_firmware_version_indicator(
    state: AppState, info: Optional[FirmwareVersion]
) -> None:
    if state.firmware_version_dot is None or state.firmware_version_label is None:
        return
    if info is None:
        set_indicator(state.firmware_version_dot, FG_MUTED)
        set_text(state.firmware_version_label, "FW —", foreground=FG_MUTED)
        return
    set_indicator(state.firmware_version_dot, OK)
    set_text(state.firmware_version_label, format_firmware_version(info), foreground=OK)


def format_battery_status(level: Optional[int], is_charging: Optional[bool]) -> str:
    level_text = f"{level}%" if level is not None else "—"
    return f"⚡ {level_text}" if is_charging else level_text


def update_battery_indicator(
    state: AppState, level: Optional[int], is_charging: Optional[bool]
) -> None:
    if state.battery_dot is None or state.battery_label is None:
        return
    if level is None and not is_charging:
        set_indicator(state.battery_dot, FG_MUTED)
        set_text(state.battery_label, "Battery —", foreground=FG_MUTED)
        return

    text = f"Battery {format_battery_status(level, is_charging)}"
    if is_charging:
        color = ACCENT
    elif level is None:
        color = FG_MUTED
    elif level <= 15:
        color = ERR
    elif level <= 30:
        color = WARN
    else:
        color = OK
    set_indicator(state.battery_dot, color)
    set_text(state.battery_label, text, foreground=color)


def reset_sensor_indicators(state: AppState) -> None:
    for key in ("EMG", "IMU_H", "IMU_F", "PPG"):
        update_sensor_indicator(
            state,
            key,
            enabled=None,
            summary="—",
            config_key=_CONFIG_KEY[key],
        )
    if state.record_status_label is not None:
        set_text(state.record_status_label, "—", foreground=FG_MUTED)
    update_license_indicator(state, None)
    update_firmware_version_indicator(state, None)
    state.battery_level = None
    state.battery_is_charging = None
    update_battery_indicator(state, None, None)


def _make_emg_handler(state: AppState):
    def _on_emg_status_ui(status: EmgStatus) -> None:
        text = format_emg_status(status)
        assert state.post_ui is not None

        def _apply() -> None:
            # Sync the chart's assumed sample rate from the device's own
            # report — not just when the user explicitly sets a new ODR via
            # the config panel. Without this, a device that's already
            # running at a non-default ODR when the app connects (or one
            # changed via the raw-command box) leaves the chart's rolling
            # window sized for the wrong rate: same point count, but
            # representing far less (or more) real time than intended.
            if state.charts is not None:
                state.charts.set_odr("EMG", status.odr_sps.value_int)
            update_sensor_indicator(
                state, "EMG", enabled=status.enabled, summary=text, config_key="EMG"
            )
            if state.set_status is not None:
                state.set_status(f"EMG status: {text}")

        state.post_ui(_apply)

    return _on_emg_status_ui


def _make_h_imu_handler(state: AppState):
    def _on_h_imu_status_ui(status: ImuStatus) -> None:
        text = format_imu_status(status)
        assert state.post_ui is not None

        def _apply() -> None:
            if state.charts is not None:
                state.charts.set_odr("IMU_H_ACC", status.odr_hz.value_int)
                state.charts.set_odr("IMU_H_GYRO", status.odr_hz.value_int)
            update_sensor_indicator(
                state, "IMU_H", enabled=status.enabled, summary=text, config_key="H_IMU"
            )
            if state.set_status is not None:
                state.set_status(f"H_IMU status: {text}")

        state.post_ui(_apply)

    return _on_h_imu_status_ui


def _make_f_imu_handler(state: AppState):
    def _on_f_imu_status_ui(status: ImuStatus) -> None:
        text = format_imu_status(status)
        assert state.post_ui is not None

        def _apply() -> None:
            if state.charts is not None:
                state.charts.set_odr("IMU_F_ACC", status.odr_hz.value_int)
                state.charts.set_odr("IMU_F_GYRO", status.odr_hz.value_int)
            update_sensor_indicator(
                state, "IMU_F", enabled=status.enabled, summary=text, config_key="F_IMU"
            )
            if state.set_status is not None:
                state.set_status(f"F_IMU status: {text}")

        state.post_ui(_apply)

    return _on_f_imu_status_ui


def _make_ppg_handler(state: AppState):
    def _on_ppg_status_ui(status: PpgStatus) -> None:
        text = format_ppg_status(status)
        assert state.post_ui is not None

        def _apply() -> None:
            if state.charts is not None:
                state.charts.set_odr("PPG1", status.odr_hz.value_int)
                state.charts.set_odr("PPG2", status.odr_hz.value_int)
            update_sensor_indicator(
                state, "PPG", enabled=status.enabled, summary=text, config_key="PPG"
            )
            if state.set_status is not None:
                state.set_status(f"PPG status: {text}")

        state.post_ui(_apply)

    return _on_ppg_status_ui


def _make_record_status_handler(state: AppState):
    def _on_record_status_ui(status: RecordStatus) -> None:
        text = format_record_status(status)

        def _apply() -> None:
            if state.record_status_label is not None:
                fg = OK if status.active else FG_MUTED
                set_text(state.record_status_label, text, foreground=fg)
            if "emg" in state.record_vars:
                state.record_vars["emg"].set(status.emg)
                state.record_vars["ppg"].set(status.ppg)
                state.record_vars["imu_h"].set(status.imu_hand)
                state.record_vars["imu_f"].set(status.imu_ring)
            if state.record_file_var is not None:
                state.record_file_var.set(str(status.file_num))
            if state.set_status is not None:
                state.set_status(f"SD record: {text}")

        assert state.post_ui is not None
        state.post_ui(_apply)

    return _on_record_status_ui


def _make_record_error_handler(state: AppState):
    def _on_record_error_ui(status: BtCmdStatus) -> None:
        text = f"ERROR {status.description} (0x{status.value_int:02X})"

        def _apply() -> None:
            if state.record_status_label is not None:
                set_text(state.record_status_label, text, foreground=ERR)
            if state.set_status is not None:
                state.set_status(f"SD record: {text}")

        assert state.post_ui is not None
        state.post_ui(_apply)

    return _on_record_error_ui


def _make_command_error_handler(state: AppState):
    def _on_command_error_ui(cmd_id: BtCmdId, status: BtCmdStatus) -> None:
        text = (
            f"{cmd_id.description} error: {status.description} "
            f"(0x{status.value_int:02X})"
        )
        assert state.post_ui is not None

        def _apply() -> None:
            if state.set_status is not None:
                state.set_status(text)

        state.post_ui(_apply)

    return _on_command_error_ui


def _make_next_file_num_handler(state: AppState):
    def _on_next_file_num_ui(file_num: int) -> None:
        def _apply() -> None:
            if state.record_file_var is not None:
                state.record_file_var.set(str(file_num))
            if state.set_status is not None:
                state.set_status(f"SD next file #: {file_num}")

        assert state.post_ui is not None
        state.post_ui(_apply)

    return _on_next_file_num_ui


def _make_battery_level_handler(state: AppState):
    def _on_battery_level_ui(level: int) -> None:
        def _apply() -> None:
            state.battery_level = level
            update_battery_indicator(state, state.battery_level, state.battery_is_charging)

        assert state.post_ui is not None
        state.post_ui(_apply)

    return _on_battery_level_ui


def _make_charging_state_handler(state: AppState):
    def _on_charging_state_ui(is_charging: bool) -> None:
        def _apply() -> None:
            state.battery_is_charging = is_charging
            update_battery_indicator(state, state.battery_level, state.battery_is_charging)

        assert state.post_ui is not None
        state.post_ui(_apply)

    return _on_charging_state_ui


def _make_license_device_info_handler(state: AppState):
    def _on_license_device_info_ui(info: LicenseDeviceInfo) -> None:
        text = format_license_device_info(info)
        assert state.post_ui is not None

        def _apply() -> None:
            update_license_indicator(state, info)
            if state.set_status is not None:
                state.set_status(text)

        state.post_ui(_apply)

    return _on_license_device_info_ui


def _make_firmware_version_handler(state: AppState):
    def _on_firmware_version_ui(info: FirmwareVersion) -> None:
        text = format_firmware_version(info)
        assert state.post_ui is not None

        def _apply() -> None:
            update_firmware_version_indicator(state, info)
            if state.set_status is not None:
                state.set_status(text)

        state.post_ui(_apply)

    return _on_firmware_version_ui


def _refresh_emg_odr_combo(state: AppState, device: MudraDevice) -> None:
    """Re-populate every EMG ODR combobox in state.emg_odr_combos with
    `device`'s actual valid rate set. build_sensor_config_ui() (config.py)
    runs once per host tab — Explorer (sensors.py), Ping (panels/ping.py) —
    each building its OWN
    combobox instance, so this must reach all of them, not just one (a
    single-widget version of this previously left whichever tab was built
    last frozen at Pro's list). Pro (ADS1293) and Ultimate (ADS1298) support
    different discrete rates — see ProEMGODR/UltimateEMGODR in enums.py — so
    every combo, built at app-startup before any device was known and
    defaulting to Pro's list, must be refreshed per-connection, not just
    re-validated on selection."""
    combos = state.emg_odr_combos
    if not combos:
        return
    odr_enum = device.EMG_ODR_ENUM
    values = [e.value_int for e in odr_enum]

    def _apply() -> None:
        for combo_widget in combos:
            combo_widget.configure(values=[str(v) for v in values])
            current = combo_widget.get()
            if current not in {str(v) for v in values} and values:
                combo_widget.set(str(values[0]))

    if state.post_ui is not None:
        state.post_ui(_apply)
    else:
        _apply()


def _refresh_emg_chart_channels(state: AppState, device: MudraDevice) -> None:
    """Rebuild the EMG chart panel (charts.py's Explorer tab) for `device`'s
    actual channel count (3 Pro / 8 Ultimate) — same rationale as
    _refresh_emg_odr_combo above: the chart is built once at app startup,
    before any device was known, with a fixed 3-channel EMG legend."""
    if state.charts is None:
        return
    count = device.EMG_CHANNEL_COUNT

    def _apply() -> None:
        state.charts.set_emg_channel_count(count)

    if state.post_ui is not None:
        state.post_ui(_apply)
    else:
        _apply()


async def register_status_callbacks(device: MudraDevice, state: AppState) -> None:
    _refresh_emg_odr_combo(state, device)
    _refresh_emg_chart_channels(state, device)
    await device.set_on_emg_status_received(_make_emg_handler(state))
    await device.set_on_h_imu_status_received(_make_h_imu_handler(state))
    await device.set_on_f_imu_status_received(_make_f_imu_handler(state))
    await device.set_on_ppg_status_received(_make_ppg_handler(state))
    await device.set_on_storage_record_state_received(_make_record_status_handler(state))
    await device.set_on_storage_record_error_received(_make_record_error_handler(state))
    await device.set_on_storage_next_file_num_received(_make_next_file_num_handler(state))
    await device.set_on_command_error_received(_make_command_error_handler(state))
    await device.set_on_license_device_info_received(
        _make_license_device_info_handler(state)
    )
    await device.set_on_firmware_version_received(
        _make_firmware_version_handler(state)
    )
    await device.set_on_battery_level_changed(_make_battery_level_handler(state))
    await device.set_on_charging_state_changed(_make_charging_state_handler(state))
    # Seed the battery indicator if a BLE initial-read already landed before
    # these callbacks were registered. get_battery_level()/get_is_charging()
    # read an attribute that's only ever assigned by the first notification
    # (no CDC support, no default in __init__), so guard against it not
    # having fired yet.
    try:
        cached_level = device.get_battery_level()
    except AttributeError:
        cached_level = None
    try:
        cached_charging: Optional[bool] = device.get_is_charging()
    except AttributeError:
        cached_charging = None
    if (cached_level is not None or cached_charging is not None) and state.post_ui is not None:
        state.battery_level = cached_level
        state.battery_is_charging = cached_charging
        state.post_ui(
            lambda: update_battery_indicator(state, state.battery_level, state.battery_is_charging)
        )
    # Seed UI if BT_SYS_DEVICE_INFO already landed before this callback was set,
    # then re-request so a late registration still gets a fresh reply.
    cached = device.get_license_device_info()
    if cached is not None and state.post_ui is not None:
        state.post_ui(lambda info=cached: update_license_indicator(state, info))
    try:
        await device.get_device_info()
    except Exception as exc:  # noqa: BLE001 — indicator is best-effort
        logger.error(f"License device-info request failed: {exc}")

    # Same seed-then-re-request pattern for BT_SYS_VERSION (0x00 0x01).
    cached_version = device.get_firmware_version_info()
    if cached_version is not None and state.post_ui is not None:
        state.post_ui(lambda info=cached_version: update_firmware_version_indicator(state, info))
    try:
        await device.get_firmware_version()
    except Exception as exc:  # noqa: BLE001 — indicator is best-effort
        logger.error(f"Firmware version request failed: {exc}")

    # Seed every pinned sensor-status label (Explorer/Advanced tabs) right
    # away instead of leaving them at "—" until the user changes something
    # or clicks a Get Status button. Fire-and-forget
    # like every other getter here -- a missing ring (F_IMU) reports
    # ERR_STATE via the command-error callback, not an exception.
    try:
        await device.get_emg_status()
        await device.get_h_imu_status()
        await device.get_f_imu_status()
        await device.get_ppg_status()
    except Exception as exc:  # noqa: BLE001 — status is best-effort
        logger.error(f"Initial sensor status request failed: {exc}")
