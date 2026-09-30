# Changelog

## [Unreleased]

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

- The SDK is now named **Indriya**. The docs site moved to
  https://kavana-tech.github.io/Indriya/, and the README, docs and
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
