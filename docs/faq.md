# FAQ

## Do I need an account to use the SDK?

No. Connecting to a device never requires an account — a signed-out app
connects and streams fine, at whatever license tier the device already
holds. Signing in (`mudra_sdk.auth`) is what lets you *raise* that tier; see
[AUTH.md](AUTH.md).

## Why do BLE and CDC behave slightly differently?

They're genuinely different links with different setup steps: BLE needs its
GATT services discovered and notifications subscribed, while CDC's DATA port
stays silent until the SDK queries sensor status and explicitly sends
`START`. The SDK does both inside `connect()` and hides most of the rest — every typed method already branches
internally — but a few things are transport-specific by nature: SD-card
recording and the PING firmware token are BLE-only; raw commands are binary
frames on BLE vs. ASCII lines on CDC. See [CONNECTION.md](CONNECTION.md).

## What does `device.connect()` returning tell me?

That the SDK's connect sequence has finished and you can enable sensors —
*if* the connection succeeded. `connect()` returns only after its setup
(BLE: services discovered, notifications subscribed, initial status/license
queries sent; CDC: both ports open and handshaken, initial status queries
sent, then `START`). It never raises on failure: the reason goes to
`MudraDelegate.on_mudra_device_connection_failed`, so check
`await Mudra().is_connected(device)` afterwards.

`MudraDelegate.on_mudra_device_connected` fires *earlier* — as soon as the
link opens, before that setup — so use it for UI state, not for enabling
sensors. Status replies arrive asynchronously after `connect()` returns. See
[SDK_USAGE.md §4](SDK_USAGE.md#4-minimal-end-to-end-example).

## Why does setting a callback also enable the sensor?

It's a deliberate design choice, not a side effect to work around: for the
five sensor streams, "I want this data" and "the sensor should be powered
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

Only for cloud calls. `Mudra()` itself constructs with a log warning if the
native `MudraSDK` library is missing for your platform, but every
`MudraDevice` raises `RuntimeError("Native library is not loaded")` when it's
created — so scans find nothing and no device can be connected. The library
also supplies command encoding, sensor-data parsing, packet-loss statistics
and `get_json_recording()`. Without it, only `mudra_sdk.auth` and the cloud
client work. See
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
