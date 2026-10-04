# FAQ

## Do I need an account to use the SDK?

No. Connecting to a device never requires an account — a signed-out app
connects and streams fine, at whatever license tier the device already
holds. Signing in (`mudra_sdk.auth`) is what lets you *raise* that tier; see
[AUTH.md](AUTH.md).

## Why do BLE and CDC behave slightly differently?

They're genuinely different links with different readiness semantics: BLE is
ready once its COMMAND characteristic is discovered, while CDC's DATA port
stays silent until the SDK queries sensor status and explicitly sends
`START`. The SDK hides most of this — every typed method already branches
internally — but a few things are transport-specific by nature: SD-card
recording and the PING firmware token are BLE-only; raw commands are binary
frames on BLE vs. ASCII lines on CDC. See [CONNECTION.md](CONNECTION.md).

## Why is `device.connect()` returning not enough to know the device is ready?

Because "the socket/GATT connection is open" and "the SDK has finished its
own readiness handshake" are two different moments — especially on CDC,
where sensor status queries and `START` happen *after* the serial ports are
open. Drive readiness-dependent logic off
`MudraDelegate.on_mudra_device_connected` instead of the `connect()`
coroutine's return. See
[SDK_USAGE.md §4](SDK_USAGE.md#4-minimal-end-to-end-example).

## Why does setting a callback also enable the sensor?

It's a deliberate design choice, not a side effect to work around: for the
four sensor streams, "I want this data" and "the sensor should be powered
on" are the same fact, so there's exactly one call
(`set_on_<sensor>_ready(fn)` / `set_on_<sensor>_ready(None)`) instead of a
separate enable/disable pair plus a separate callback registration. See
[SENSORS.md §1](SENSORS.md#1-enable--disable-a-sensors-data-stream).

## Why does SD-card recording require the `PRO` tier?

That's a device-side policy enforced by firmware
(`BtCmdStatus.ERR_LICENSE` on `FREE`/`PLUS`), not an SDK limitation — the SDK
just surfaces whatever the firmware decides. See
[supported_devices.md](supported_devices.md#license-tiers).

## Can I use this SDK without the native library?

Yes — `Mudra()` degrades gracefully (a log warning, not an exception) if the
native `MudraSDK` library is missing for your platform. Everything except
binary sensor-data parsing and packet-loss statistics still works. See
[native_library.md](native_library.md).

## Can I record Mudra data with LabRecorder / alongside an EEG system?

Yes — `mudra_sdk.lsl` publishes each sensor as a Lab Streaming Layer stream,
timestamped from the device's own clock, so LabRecorder (or any LSL consumer)
records it time-aligned with everything else on the network. It takes one
line of code (`async with MudraLslBridge(device): ...`), or none at all
(`python examples/lsl_app.py`). `pylsl` is an optional extra. See [LSL.md](LSL.md).

## Is there a PyPI package?

Not yet — add the repo root to `sys.path` and `import mudra_sdk` directly.
See [installation.md](installation.md).
