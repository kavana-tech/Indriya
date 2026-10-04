# Troubleshooting

Common problems when integrating against the SDK, and how to resolve them.
If something here doesn't cover your case, [SDK_USAGE.md](SDK_USAGE.md) and
the guide pages it links to explain the design in more depth.

## Nothing happens after calling a `get_*`/`set_*` method

Almost everything in this SDK is **fire-and-forget** — the reply comes back
asynchronously through a registered callback, not the coroutine's return
value. Register the callback *before* triggering the request if you need to
be sure not to miss it. See [SENSORS.md §6](SENSORS.md#6-sensor-pitfalls) and
[CALLBACKS.md](CALLBACKS.md).

## Sensor data never arrives

- **You didn't register a streaming callback.** Setting
  `set_on_emg_ready`/`set_on_imu_h_ready`/`set_on_imu_f_ready`/`set_on_ppg_ready`
  to a non-`None` function *is* the enable action — there's no separate
  "power on" call. See [SENSORS.md §1](SENSORS.md#1-enable--disable-a-sensors-data-stream).
- **On CDC, `connect()` returned but the device isn't fully ready yet.** CDC
  needs the SDK to query sensor status and then send `START` before the DATA
  port produces anything; BLE only needs its COMMAND characteristic
  discovered. Drive readiness-dependent logic off `on_mudra_device_connected`,
  not the `connect()` return. See
  [SDK_USAGE.md §4](SDK_USAGE.md#4-minimal-end-to-end-example).
- **You reconnected the same `MudraDevice` object.** Disconnecting (expected
  or not) clears every streaming/status/storage/error/ping callback — you
  must re-register them after reconnecting. See
  [CALLBACKS.md §3](CALLBACKS.md#3-callbacks-dont-survive-a-disconnect).

## Config change (ODR/resolution/range) seems to do nothing, or corrupts the stream

`set_*_odr`/`set_*_res`/range calls don't stop the sensor for you — the
firmware doesn't either. Disable the sensor
(`set_on_<sensor>_ready(None)`), change config, then re-enable it if it was
running. See [SENSORS.md §3](SENSORS.md#3-configure-a-sensor-odr-resolution-ranges-etc).

## Streaming works, but at a lower tier than expected

Connecting to a device **never requires an account** — a signed-out app
still streams fine, at whatever tier the device already holds (usually
`FREE`). Nothing raises if you skip sign-in, so this fails silently:

- Call `auth.sign_in_email(...)` then `await auth.provision_device(device)`
  right after every `connect()` — it's a no-op if nobody's signed in, so it's
  always safe to call unconditionally.
- Read the device's actual tier back via
  `set_on_license_device_info_received` rather than assuming sign-in success
  implies the device got provisioned — the two are asynchronous and
  independent.

See [AUTH.md](AUTH.md) for the full checklist.

## SD recording rejected with `ERR_LICENSE` or `ERR_STATE`

- **`ERR_LICENSE`** — SD-card recording requires the device's **`PRO`** tier;
  `FREE`/`PLUS` are rejected without touching any sensor. See
  [supported_devices.md](supported_devices.md#license-tiers).
- **`ERR_STATE`** — `set_user_id(...)` was never sent. This is normally
  automatic (sent right after connecting, if signed in — see
  [AUTH.md](AUTH.md#user_id-provisioning-sd-card-recording)); this fires if
  the device connected while signed out. Sign in and reconnect, or call
  `set_user_id(...)` yourself. See
  [SENSORS.md §5](SENSORS.md#5-sd-card-recording-ble-only).
- **On CDC** — every SD/storage call reports `BtCmdStatus.ERR_UNKNOWN`
  immediately; there is no SD storage protocol over CDC at all, by design.

## The native library won't load

Symptom: a log warning ("Could not load native library: ...") right after
constructing `Mudra()`. This is **not fatal** — scanning, connecting, sensor
enable/disable, status/config, licensing, and SD recording control all still
work; only binary sensor-data parsing and packet-loss stats are affected.

- Check that a prebuilt binary exists for your platform/arch under
  `mudra_sdk/libs/<platform>/<arch>/`. See [supported_devices.md](supported_devices.md#platform-support-host-side)
  for the supported list, and [native_library.md](native_library.md) for how
  it's built.

## Firmware update (`start_dfu`) fails

- **`RuntimeError` before anything starts** — either `device` has no CDC
  identity (DFU is USB-only, no BLE transport exists on either product yet)
  or the SDK couldn't find a third USB-CDC SMP port on the device (it needs
  DFU-enabled firmware already running).
- **`DfuError` mid-flow** — its `.stage`/`.message` identify which step
  failed (connect / upload / mark / reset). MCUboot swaps and boots the new
  image on its own after reset; there's no device-side "update complete"
  push, so reconnect afterward to confirm the new version actually landed.

See [CONNECTION.md §6](CONNECTION.md#6-firmware-update-dfu-usb-only).

## LSL consumers can't see the streams

`MudraLslBridge.start()` returned and `bridge.streams` lists the streams, but
LabRecorder / `pylsl.resolve_streams()` on another machine shows nothing:

- **Firewall / several network interfaces.** `liblsl` finds streams over UDP
  multicast and sends data over TCP — both must be allowed, on the interface
  that actually reaches the other machine. This is by far the most common
  cause and has nothing to do with the bridge. Check on the publishing
  machine first (`python -c "import pylsl; print(pylsl.resolve_streams(2.0))"`).
- **`ImportError: mudra_sdk.lsl needs pylsl`** — install the optional
  dependency: `pip install pylsl`. On Linux, also install `liblsl` itself.
- **`RuntimeError: none of the requested sensors reported status`** — you
  started the bridge before the device was ready; wait for
  `on_mudra_device_connected` (see "Sensor data never arrives" above).
- **A stream went quiet after you registered your own callback** — the
  bridge uses the `set_on_*_ready` slot of every sensor it publishes; read
  the samples back from LSL instead. See [LSL.md §4](LSL.md#4-the-bridge-turns-sensors-on-and-off).
- **Streams went quiet after the device reconnected** — a disconnect clears
  the bridge's callbacks; call `bridge.start()` again. See
  [LSL.md §6](LSL.md#6-changing-configuration-and-reconnecting).

## `bleak`/`smpclient` import errors when installing

`bleak` is pinned to the [wearable-devices fork's](https://github.com/wearable-devices/bleak)
`develop` branch, not upstream PyPI `bleak` — make sure you installed from
`mudra_sdk/requirements.txt` rather than a stray `pip install bleak`. Git
access to that fork is required for the install to succeed.
