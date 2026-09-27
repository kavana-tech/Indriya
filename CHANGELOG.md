# Changelog

## [Unreleased]

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
