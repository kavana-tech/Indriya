# Changelog

## [Unreleased]

## [0.5.1] - 2026-10-13

### Changed

- Supported Mudra Ultimate firmware is now **1.0.3.9** — see [Firmware compatibility](docs/supported_devices.md#firmware-compatibility).
- The Mudra Connect example app (`examples/connect_app.py`) now connects to
  any number of devices at once and opens a separate window for each one,
  with its own sensor charts, config, recording, ping, packet-loss, command
  and firmware-update tabs. The main window keeps scanning, sign-in and the
  device list. Closing a device's window disconnects that device.
- `set_emg_test_mode`, `set_h_imu_test_mode`, `set_f_imu_test_mode`,
  `set_ppg_h_test_mode` and `set_ppg_f_test_mode` moved from `MudraPro` to
  `MudraDevice`, so they work on **Mudra Ultimate** too. Ultimate needs
  firmware newer than 1.0.3.8 for them. See
  [SENSORS.md §4](docs/SENSORS.md#4-packet-loss-test-mode).
- Mudra Connect's Packet Loss tab now runs on Mudra Ultimate the same way as
  on Pro, and offers each device's own EMG rates (Ultimate: 500–4000 Hz).
- Mudra Connect's window titles (main window and each device window) now
  show the SDK version, e.g. `Mudra Pro — Signal Explorer — SDK v0.5.1`.

### Documentation

- CDC test mode starts and stops the sensor, the same as BLE. The guide
  said it didn't.

## [0.5.0] - 2026-10-12

### Changed

- Supported Mudra Ultimate firmware is now **1.0.3.8** — see [Firmware compatibility](docs/supported_devices.md#firmware-compatibility).
- Supported Mudra Pro firmware is now **2.0.2.6** — see [Firmware compatibility](docs/supported_devices.md#firmware-compatibility).
- **Breaking: PPG is now two sensors, `PPG_H` (hand) and `PPG_F` (finger /
  ring)**, mirroring the hand/finger IMU split. Each has its own stream,
  status, enable/disable and per-channel settings, and always carries 2
  channels (`ch0`, `ch1`); `PPG_F` needs the ring connected. Needs firmware
  with the matching PPG_H/PPG_F protocol — the wire format changed (new
  `0xA0` PPG_F data section, 2-channel PPG samples, `PPG_H_*`/`PPG_F_*` USB
  commands) and older firmware won't work with this SDK. Every `*ppg*` API
  was replaced, with no aliases:
  - `set_on_ppg_ready` → `set_on_ppg_h_ready` / `set_on_ppg_f_ready`;
    `set_on_ppg_status_received` → `set_on_ppg_h_status_received` /
    `set_on_ppg_f_status_received`; `get_ppg_status` / `get_ppg_status_info`
    → `get_ppg_h_status` / `get_ppg_h_status_info` and the `_f_` pair.
  - Config: `set_ppg_odr`, `set_ppg_dec`, `set_ppg_led`, `set_ppg_tia`,
    `set_ppg_prpct`, `set_ppg_src`, their `get_*` twins and `ppg_clear()` →
    `set_ppg_h_odr` … `ppg_h_clear()` and `set_ppg_f_odr` … `ppg_f_clear()`.
    ODR, decimation and PRPCT are shared by both sensors (setting one
    through either changes both). LED/TIA/SRC take the sensor's own channel,
    0 or 1 — any other `ch` raises `ValueError`.
  - Packet loss: `get_ppg_packet_loss_stats`, `get_ppg_packet_loss_rate_hz`,
    `reset_ppg_packet_loss_window`, `sample_ppg_packet_loss` → `_ppg_h_` /
    `_ppg_f_` versions. Mudra Pro: `set_ppg_test_mode` →
    `set_ppg_h_test_mode` / `set_ppg_f_test_mode`.
  - Enums: `SensorTypes.PPG` / `BtCmdId.PPG` → `PPG_H` / `PPG_F`;
    `FirmwareDataType.ppg` → `ppgH` / `ppgF`;
    `FirmwareCallbacks.PPG_STATUS` → `PPG_H_STATUS` / `PPG_F_STATUS`;
    `RecordingDataType.ppg1`…`ppg4`/`ppgTS` → `ppgH1`, `ppgH2`, `ppgHTS`,
    `ppgF1`, `ppgF2`, `ppgFTS`; `PpgStatus.channel_count` and the
    `PPGChannelCount` enum are gone (every PPG sensor is 2 channels; with no
    ring, `get_ppg_f_status()` gets `ERR_STATE` like F_IMU's); `BtCmdPPG` → `BtCmdPPGH` /
    `BtCmdPPGF`; the `ProFirmwareCommand` / `UltimateFirmwareCommand` PPG
    members are now `ppgH*` / `ppgF*` (and `enablePpgH` / `enablePpgF`).
  - PC-side JSON recordings have `ppg_h` and `ppg_f` sections instead of
    `ppg`.
  - LSL: the `ppg` stream is replaced by `ppg_h` (`…-PPG_H`) and `ppg_f`
    (`…-PPG_F`), 2 channels each; `metadata.PPG` → `metadata.PPG_H` /
    `metadata.PPG_F`. The bridge skips `ppg_f` when no ring is connected.
- **Breaking: `set_storage_record()` takes a fifth sensor flag**:
  `set_storage_record(emg, ppg_h, imu_h, imu_f, ppg_f, *, file_num=…, …)`.
  Everything after the flags is now keyword-only, and a flag that isn't a
  bool raises `TypeError`, so an old call that passed `file_num`
  positionally fails instead of silently recording the wrong sensors.
  `RecordStatus` has `ppg_h` and `ppg_f` in place of `ppg`.
- Mudra Connect: PPG_F with no ring no longer reads as a red OFF — like F_IMU,
  it has no status then, so its indicator stays at a neutral "—". The PPG tabs keep
  their shared ODR in sync, pick the channel from a 0/1 list, default SRC to
  each sensor's own optics (PPG_F: LED 5 / PD 4), and say which settings
  are shared.

### Fixed

- Mudra Connect renders the same on Windows, macOS and Linux. Columns were
  fixed pixel widths while fonts weren't (Windows-only font names, and Linux
  desktop scaling enlarging text but nothing else), so on many machines the
  Connect button, the sensor Disable buttons and the Sensor Config tabs were
  cut off or squashed. Fonts, spacing and charts now follow the display's
  scale (override with `MUDRA_UI_SCALE`), side columns start at their
  content's width and can be dragged wider, device rows put Connect on its
  own line, and status/data rates moved to a bottom status bar. The mouse
  wheel now scrolls any panel under the pointer on all three OSes, and no
  longer changes a dropdown's value (which sent a command) while scrolling.
- Mudra Connect: a failed config command or stream toggle now shows its
  error in the status bar instead of raising `NameError` on the UI thread.
- Mudra Connect: the Packet Loss chart no longer smears every past spike into
  a solid band with a black box over the legend. It kept its first-draw size
  and background after the window (or display scale) changed, so each refresh
  only wiped a small corner of the plot.

### Documentation

- The README and the docs site now carry the **Kavana** logo instead of the
  Mudra one (README: wordmark with the "Neural Intent Data" tagline; docs
  sidebar: wordmark only; favicon: the K mark). Both have light and dark
  variants.
- Corrected connect readiness: `await device.connect()` returning is the
  point where the device is ready for sensor commands;
  `on_mudra_device_connected` fires earlier, when the link opens; and
  `connect()` doesn't raise on failure (check `Mudra().is_connected()`).
- License and user-ID provisioning is automatic on every connect while
  signed in — sign in before connecting.
- Cloud tokens are stored on disk (`~/.mudra_sdk/auth_storage.json`) and
  survive restarts and `auth.logout()`.
- The native library is required for any device work, not just data
  parsing; only cloud calls work without it.
- Callbacks must be plain `def` functions — an `async def` callback never
  runs.
- Windows: only 64-bit (x64) is supported.

## [0.4.8] - 2026-09-30

### Changed

- Supported Mudra Ultimate firmware is now **1.0.3.7** — see [Firmware compatibility](docs/supported_devices.md#firmware-compatibility).

### Added

- **Lab Streaming Layer publishing** (`mudra_sdk.lsl`, guide:
  `docs/LSL.md`). `MudraLslBridge` publishes a connected Mudra Pro or Mudra
  Ultimate device (BLE or USB) as one LSL stream per sensor —
  `MudraPro-<device_id>-EMG` / `-IMU_HAND` / `-IMU_RING` / `-PPG`
  (`MudraUltimate-…` on Ultimate), named like the Mudra Pro C++ SDK's LSL
  streams. Each stream's sample rate and channel count come from the
  device's status (3- or 8-channel EMG, 1–4 PPG channels), with channel
  labels and units and a stable `source_id`. Timestamps come from the
  device's own clock, converted to LSL time by `DeviceClockMapper`. The
  bridge turns on the sensors it publishes and turns them off on `stop()`.
  `pylsl` is
  an optional dependency (`pip install pylsl`); importing the package
  doesn't need it.
- `examples/lsl_app.py`: a headless command-line streamer — finds an
  already-connected or advertising device (BLE or USB), optionally signs in
  and changes sensor ODRs, then publishes the sensors to LSL until stopped.

- `supported_firmware.json`: the supported firmware version per model, in
  machine-readable form.

### Documentation

- `docs/data_format.md`: a package's `timestamp` is its **first** sample's
  device time, not its last (measured on Mudra Pro fw 2.0.2.0 and Mudra
  Ultimate fw 1.0.3.0).

- `docs/supported_devices.md`: new "Firmware compatibility" section — the
  firmware this SDK release supports: Mudra Pro 2.0.2.5 and Mudra Ultimate
  1.0.3.6. Also notes that Mudra Pro firmware has no finger IMU. Summarized
  in the README, `AGENTS.md` and `docs/installation.md`.

## [0.4.6] - 2026-09-28

### Changed

- The SDK got its own name (now **Kavana SDK**). The docs site moved to
  https://kavana-tech.github.io/Kavana-SDK/, and the README, docs and
  site title use the new name. The Python package is still imported as
  `mudra_sdk` — no code changes are needed.

## [0.4.5] - 2026-09-27

### Fixed

- A CDC (USB) device now fires `on_mudra_device_disconnected` when its USB
  link drops — cable unplugged or device rebooted — whether it was already
  connected or still connecting. Previously the drop went unreported and
  the device stayed marked as connected. A detach while the ports are
  still opening fires `on_mudra_device_connection_failed` followed by
  `on_mudra_device_disconnected`.
- Reconnecting over BLE after an unexpected disconnect (e.g. the device
  was powered off) works again on Windows. The dropped connection's GATT
  service handles were never released, so every later connection in the
  same process lost access to the Mudra service and failed with
  "Characteristic ... fff1 was not found" until the app was restarted.

### Documentation

- `docs/SENSORS.md`: turning off the sensors an app enabled is the app's
  responsibility — disconnecting or closing the app doesn't turn them off.

## [0.4.4] - 2026-09-27

Initial release.
