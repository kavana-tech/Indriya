# Changelog

## [Unreleased]

## [0.4.4] - 2026-09-27

### Fixed

- License info from a Mudra Ultimate device over BLE is decoded again.
  Ultimate sends a wider serial field in `BT_SYS_DEVICE_INFO` (31-byte
  frame vs. mudra_pro's 29), and those replies were being silently dropped
  by a fixed length check; the serial width is now derived from the frame
  actually received.
- `get_firmware_version()`/`get_device_info()` over CDC fire their
  callbacks again on Mudra Ultimate firmware, whose `VERSION`/`DEVICE_INFO`
  replies carry extra `git=` (and `init_faults=`) fields the parser didn't
  tolerate. Older firmware without them still parses.

### Removed

- Mudra Studio (`examples/mudra_studio/`, `examples/studio_app.py`),
  including its `decode.py` recording-to-CSV converter. `cryptography` is
  no longer an example-app dependency.

## [0.4.3] - 2026-09-19

### Changed

- Firmware now writes an SD-card recording as a `/SD:/REC_<n>/` folder of
  size-capped part files (10 KiB each) instead of one unbounded `.bin`
  file. `examples/mudra_studio/decode.py`'s `decode_recording()`/
  `decode_all()`/`convert_file()`/`convert_all()` accept either shape
  transparently (reassembling a folder's parts before decrypting/
  decoding), and the Recordings panel gained a "Load Recording Folder..."
  button alongside the existing single-file picker. No API change for
  callers already going through `decode_recording()`.
- Loading or converting a recording now shows a modal progress dialog
  with a real percentage (bytes/parts read, network key request, decode
  progress) instead of an indeterminate spinner.

## [0.4.2] - 2026-09-17

### Added

- `auth.get_user_ref()` — the signed-in account's identifier, as the
  hex string `MudraDevice.set_user_id()` expects.
- Automatic `user_id` provisioning: a device that finishes connecting
  while signed in gets `set_user_id()` sent for it automatically —
  mirrors the existing automatic license provisioning
  (`auth.provision_device()`). Sign in before connecting (or reconnect
  after signing in) for this to take effect; see `docs/AUTH.md`.
  `examples/mudra_connect`'s recording panel no longer needs a manual
  User ID field.
- `MudraServerClient.open_recording_header()` — resolves an encrypted
  recording's crypto header into the key needed to decrypt it, via the
  account's decrypt host. `examples/mudra_studio/decode.py` no longer
  holds any key material of its own; decrypting a recording now needs
  an active signed-in session.

## [0.4.1] - 2026-09-14

### Added

- Published documentation site (`docs/` gains a Sphinx build: `conf.py`,
  `index.rst`, `installation.md`, `getting_started.md`,
  `supported_devices.md`, `examples.md`, `api_reference.rst`,
  `native_library.md`, `troubleshooting.md`, `faq.md`) deployed to
  `gh-pages` via `.github/workflows/docs.yml`, published at
  https://wearable-devices.github.io/mudra_pro_sdk/. The existing
  `SDK_USAGE.md`/`CONNECTION.md`/`SENSORS.md`/`CALLBACKS.md`/`AUTH.md`
  guide pages are toctree'd in as-is — no content fork. See `docs/CLAUDE.md`.
- `docs/data_format.md` — documents that sensor-streaming `samples` are
  channel-major (each channel's full run back to back, not interleaved
  per-sample), per-sensor units, and that the callback's `frequency` is the
  package rate, not the sensor's configured ODR. Traced directly from the
  native parser (`CommonTypes.h`, `computation_wrapper.cpp`).
- `docs/supported_devices.md` gained a verified Status LED section (state
  tables + a visual gallery) sourced from the firmware repos'
  `led_manager.h`/`.c`, including the full `LED_SET_STATE`/`LED_RGB`/
  `LED_BLINK`/`LED_GET` wire behavior.
- `docs/CONNECTION.md` §8 "Multiple devices at once", documenting that
  `Mudra`'s per-address device registry already supports several
  simultaneously-connected devices.

### Changed

- Bumped to 0.4.1 (patch) for this docs-site release; no SDK API changes.

## [0.4.0] - 2026-09-08

### Breaking

- **`Mudra.scan()`/`stop_scan()` (which drove BLE + CDC together) are
  replaced by transport-specific `scan_ble()`/`stop_scan_ble()` and
  `scan_cdc()`/`stop_scan_cdc()`** — code scanning both transports at once
  should now call both pairs explicitly. See `docs/CONNECTION.md` §1.
  `examples/mudra_connect` (and `mudra_studio`, which reuses its device
  panel) replaced the single "Start Scan"/"Stop Scan" pair with independent
  "BLE Scan"/"CDC Scan" toggle buttons.

### Added

- Firmware update (DFU) support (`mudra_sdk/service/dfu_service.py`,
  `device.start_dfu()`) — uploads a signed image to the device over a
  dedicated USB-CDC SMP port via MCUmgr (`smpclient`, new dependency).
  USB (CDC) only — no BLE DFU transport on either product yet — and requires
  DFU-enabled firmware already running on the device. See
  `docs/CONNECTION.md` §6. `examples/mudra_connect` gained a "Firmware
  Update" tab (`panels/dfu.py`).
- CDC battery/charging status: `on_cdc_ready()` now polls `BAT_SOC?`/
  `BAT_CHG?` once at connect and every 30s thereafter, feeding the same
  `on_battery_level_changed`/`on_charging_state_changed` callbacks BLE's
  GATT Battery Service notifications already drive. Previously a
  CDC-connected device showed no battery info at all.
- `LicenseManager`: `MudraDevice` now periodically renews its license —
  re-requests `BT_SYS_DEVICE_INFO` every 5 minutes and re-provisions once
  the token's `expires_at` drops under a 7-minute threshold, so a
  long-running connection no longer silently drops tier when its license
  token lapses mid-session. Started on connect, stopped on disconnect.
- Firmware version query (`BT_SYS_VERSION`) on connect over both BLE and
  CDC, shown in `examples/mudra_connect` next to the battery/license
  indicators.
- Mandatory recording encryption: `device.set_user_id(user_id: bytes)`
  (16 bytes) is now required before SD recording — firmware rejects
  `set_storage_record()` with `ERR_STATE` if no user_id was ever sent.
  `examples/mudra_connect`'s recording panel now sends a (generatable)
  user ID before every SD recording.
- PC-side (non-SD) JSON recording of IMU/EMG/PPG sample data
  (`DataRecorder`, `device.start_recording()`/`stop_recording()`/
  `get_json_recording()` — data-only, no `json_string` param), with a
  dedicated Recording tab in `examples/mudra_connect` (moved out of
  Explorer's sidebar, alongside SD recording).
- Mudra Studio (`examples/mudra_studio`, `examples/studio_app.py`) — a
  second reference app for SD-card recording plus offline
  decrypt-and-convert-to-CSV, gated behind sign-in; gained its own sensor
  ODR/Resolution controller on the Recording tab.
- Device license status indicator (color-coded dot + tier/validity/serial
  text) in `examples/mudra_connect`'s auth bar.
- BLE/CDC battery+charging status indicator in `examples/mudra_connect`/
  `mudra_studio`'s auth bar, wired to `on_battery_level_changed`/
  `on_charging_state_changed`.
- `docs/AUTH.md`, `AGENTS.md`, `docs/DOCS_MAP.md`, `CLAUDE.md` —
  agent-facing documentation covering sign-in/licensing and repo/dev
  guidance.
- linux-aarch64 added to the native-library CI build matrix.
- Separate `mudra_sdk/requirements.txt`/`examples/requirements.txt`
  (previously one combined file).

### Changed

- `LicenseDeviceInfo`'s tier field switched from raw ints to the
  `LicenseTier` enum, with explicit handling for unknown tier values.
- `print()` calls across the SDK and example apps replaced with leveled
  logging (`mudra_sdk/logging_config.py`).
- `bleak` pinned to the wearable-devices fork's `develop` branch.
- `SYSTEM_USER_ID_SET`/`STORAGE_RECORD_SET` wire frames now built from
  native `FirmwareCommand` templates instead of hand-rolled bytes in
  `firmware_protocol.py`.
- `examples/mudra_connect`'s config and packet-loss panels apply changes
  immediately on selection instead of requiring a Set button (Get buttons
  kept only where no live status push already covers the value).

### Fixed

- CDC license status/provisioning parity with BLE: `get_device_info()`'s
  CDC reply is now decoded into `LicenseDeviceInfo`, `on_cdc_ready()` now
  triggers auto-provisioning the way BLE's `update_connection_properties()`
  does, `LICENSE`/`LICENSE_CLEAR` error replies are now classified instead
  of silently dropped at DEBUG, and `provision_device()` now re-queries
  device info afterward on CDC too. Previously CDC apps couldn't see or
  provision a device's license tier at all.
- `DEVICE_INFO?`'s CDC reply parsing, broken by firmware's new trailing
  `usb_sn=<hex>` field (added for multi-unit identification): the reply
  regex was anchored right after `expires=`, so the whole line stopped
  matching and `LicenseDeviceInfo` stopped updating — the license indicator
  went blank on CDC after updating firmware. The trailing field is now
  optional and ignored.
- CDC firmware-version query token bug: firmware registers `VERSION`
  without the trailing `?` every other getter uses.
- Explorer's sensor charts in `examples/mudra_connect`: matplotlib's own
  resize handler was being silently overwritten by the panel's own
  `<Configure>` binding (fixed with `add="+"`), and chart margins were
  figure-fraction based (tuned for a fixed width), so a narrow window
  clipped the y-axis "1.00" label down to ".00".

## [0.3.0]

### Breaking

- **Native parser widened live BLE/CDC sample timestamps from 32-bit to
  64-bit** (`Parser::ConsumeSection`), matching the firmware's own protocol
  change. **This SDK version requires firmware 2.0.0+** — pairing it with
  older firmware (still sending 4-byte timestamps) will misparse every
  packet, since each section's timestamp read will consume 4 bytes of the
  next section's data. See the firmware repo's
  `docs/migration-2.0.0.md` for the exact wire-format spec.
- **`storage_record_set()`'s wire frame gained a 2-byte `duration_min`
  field** between `file_num` and `description`, matching firmware's
  `BT_STORAGE_RECORD_SET`. Requires the matching firmware update — older
  firmware reads the low `duration_min` byte as the first description byte
  and everything shifts by one. `set_storage_record()`'s Python signature
  changed to match: `duration_min` is now a required-position keyword
  argument between `file_num` and `description` — code calling it
  positionally past `file_num` needs updating.
- **`storage_record_set()`'s wire frame gained a further 4-byte `utc_ts`
  field** between `duration_min` and `description`, matching firmware's
  `BT_STORAGE_RECORD_SET`. Same requirement as above — matching firmware
  update needed, and `set_storage_record()`'s Python signature gained
  `utc_ts` as a keyword argument between `duration_min` and `description`.
- **SD card recording (`BT_STORAGE_RECORD_SET`) now requires the device's
  PRO license tier** — starting a session on FREE/PLUS is rejected with
  `BtCmdStatus.ERR_LICENSE` (via the command-error callback) without
  touching any sensor. No SDK-side enforcement change was needed (the
  existing command-error callback already surfaces `ERR_LICENSE`), but any
  code assuming recording works on every tier needs updating.

### Added

- Mudra Ultimate device support — `MudraPro`/`MudraUltimate` now subclass a
  shared `MudraDevice` base, each with its own fully separated command
  table (native `ProFirmwareCommands.h`/`UltimateFirmwareCommands.h` +
  Python enums), mirroring how each firmware defines its own
  `bt_command_manager.h` from scratch rather than sharing one table with a
  device-branch parameter. Device model is detected automatically from the
  BLE advertised name, both when a device is found via scan and via
  `get_connected_devices()`. Per-device EMG ODR value sets are exposed as
  `ProEMGODR` (200-6400 Hz, ADS1293) and `UltimateEMGODR` (500-4000 Hz,
  ADS1298) — see `MudraDevice.EMG_ODR_ENUM`. `MudraDevice.EMG_CHANNEL_COUNT`
  (3 on Pro, 8 on Ultimate) is plumbed through sample ingestion, the inbound
  EMG_STATUS reply classifier, and `examples/mudra_connect`'s EMG chart/ODR
  controls.
- `examples/mudra_connect`: per-sensor "Split into separate charts" toggle
  (EMG/IMU_H/IMU_F) rendering each channel as its own full-width panel
  instead of one combined chart, and a scrollable chart area (mirroring the
  existing scrollable controls column) so panel count is no longer bounded
  by window height.
- USB CDC (serial) transport, unified with BLE behind the same `Mudra`/
  `MudraDevice` API (`cdc_service.py`, `cdc_device.py`).
- Account sign-in and device licensing (`mudra_sdk.auth`, `get_device_info()`
  / `LicenseDeviceInfo`, `apply_license()`/`clear_license()`) — see
  `docs/CONNECTION.md` §5.
- Ping/latency check (`device.ping()`) with a configurable-interval UI
  panel.
- Packet-loss test-mode UI and SDK support (`set_*_test_mode`,
  `sample_*_packet_loss`, live packet-loss chart with alert badges).
- SD recording test mode (`is_test=True` on `set_storage_record`) for
  offline packet-loss analysis of recorded files.
- `duration_min` parameter on `set_storage_record()` — a non-zero value
  auto-stops the SD recording session after that many minutes, matching
  firmware's new one-shot timer on `BT_STORAGE_RECORD_SET`; 0 (default)
  keeps the existing record-until-stopped behavior.
- `utc_ts` parameter on `set_storage_record()` — client-supplied wall-clock
  start time (Unix epoch seconds); the device has no independent RTC, so
  firmware folds this into the recording's meta line as `UTC=<ts>` when
  non-zero. 0 (default) omits it. Recording panel (shared by
  `connect_app.py`/`studio_app.py`) gained a "Send UTC timestamp" checkbox
  that sends the PC's current time.
- v4 recording format support in `bin_to_csv.py` — 64-bit timestamps,
  eliminates the ~71 min rollover; auto-detects file version and still
  decodes v1-v3 recordings.
- Comprehensive SDK usage guide (`docs/SDK_USAGE.md` +
  `CONNECTION.md`/`SENSORS.md`/`CALLBACKS.md`).
- "Find Connected" button for direct device discovery without a full BLE
  scan.
- `.gitignore` for Python build artifacts.

### Changed

- Packet-loss monitoring decoupled from data-ready callbacks — the UI now
  polls `sample_*_packet_loss()` each refresh tick instead of the SDK
  pushing dedicated packet-loss callbacks.
- CDC status handling streamlined: removed the explicit
  `_cdc_refresh_status` re-query mechanism (no longer needed).
- Five near-identical CDC command helpers folded down to two (`_cdc_send`/
  `_cdc_command`).
- CDC reply dispatch unified with BLE's typed event model.

### Fixed

- `ComputationManager`'s mutex made recursive, fixing deadlocks from
  re-entrant calls.
- `PacketLossWindow` history initialization, so loss is reported
  accurately from the very first update.
- Docs and `set_storage_record()`'s own docstring corrected: SD recordings
  are the binary `MREC` format (`/SD:/REC_<n>.bin`), not CSV — CSV is only
  what `bin_to_csv.py` produces on decode. This was wrong in both places
  before this release.

### Removed

- Obsolete CDC standalone connection example (superseded by full CDC
  integration into the main SDK).
- Obsolete test-mode packet-loss detection script for the old CSV format
  (superseded by v4-aware `bin_to_csv.py`).

## [0.2.7]

Baseline prior to this batch.
