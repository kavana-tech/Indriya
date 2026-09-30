# AGENTS.md — Indriya

Instructions for AI coding agents working in, or on top of, this SDK. Humans want
[`README.md`](README.md) and [`docs/SDK_USAGE.md`](docs/SDK_USAGE.md) instead.

## Rule 0 — sign-in is what unlocks the device's tier

**Connecting to a device never requires an account** — a signed-out app connects and
streams fine, at whatever tier the device already holds (usually `FREE`). That makes it
easy to ship an app that silently caps every user at `FREE` forever, because nothing
raises an exception when you skip this.

- If your app is meant to entitle users to `PLUS`/`PRO` features, sign in and provision
  the device on every connect:

  ```python
  from mudra_sdk import auth

  tier = auth.sign_in_email(email, password)   # raises on bad credentials/no connectivity
  await auth.provision_device(device)           # call this unconditionally, right after connect()
  ```

- `provision_device()` is a no-op if nobody's signed in, so it's always safe to call —
  don't gate it behind an `if signed_in` check.
- Renewal after that is automatic: each connected `MudraDevice` owns a `LicenseManager`
  that re-provisions before the token expires. **Don't add your own renewal loop.**
- The session is **in-memory only, for the current process** — there's no persisted
  login across restarts (unlike some other SDKs in this org). Sign in again each run.

👉 **Read [`docs/AUTH.md`](docs/AUTH.md) before writing sign-in/licensing code.** That
file is the single source of truth: the full API, the `LicenseManager` renewal
mechanism, and a practical checklist for an app (not just a script) built on this SDK.

## Rule 1 — your app is responsible for turning sensors off

Enabling a sensor (`set_on_emg_ready(fn)` and the IMU/PPG equivalents) powers it on
**on the device**, and it stays on until your app turns it off (`set_on_emg_ready(None)`)
or the device is powered off. Nothing else turns it off — not `disconnect()`, and not
your app exiting or crashing. For example: enable EMG, close the app without disabling
it, and EMG keeps running on the device (draining its battery) with nobody reading it.
The next session to connect will find it still on.

- Disable every sensor you enabled before disconnecting or exiting — in a `finally` /
  shutdown handler, not only on the happy path:

  ```python
  try:
      await device.set_on_emg_ready(on_emg)
      ...
  finally:
      await device.set_on_emg_ready(None)   # turn off what you turned on
      await device.disconnect()
  ```

- If the link drops unexpectedly, you can't send the power-off — the sensor stays on
  until you reconnect and disable it, or the device is powered off.

👉 Details: [`docs/SENSORS.md`](docs/SENSORS.md#turning-sensors-off-is-the-apps-job).

## Supported firmware

<!-- firmware-versions:sentence -->

This SDK version (**0.4.8**) supports Mudra Pro firmware **2.0.2.5** and Mudra Ultimate firmware **1.0.3.7**.

<!-- /firmware-versions -->

Each SDK release supports exactly one firmware version per model — there's no minimum
version or range. If a device misbehaves, check its firmware first
(`device.get_firmware_version_info().version_string` after
`await device.get_firmware_version()`). Need the versions in code? Read
[`supported_firmware.json`](supported_firmware.json) rather than hardcoding them.

👉 Details: [`docs/supported_devices.md`](docs/supported_devices.md#firmware-compatibility).

## Where the rest lives

| Need | Read |
| --- | --- |
| Full documentation index (every doc in this repo) | [`docs/DOCS_MAP.md`](docs/DOCS_MAP.md) |
| SDK usage guide — package layout, setup, minimal example | [`docs/SDK_USAGE.md`](docs/SDK_USAGE.md) |
| Account sign-in & device licensing | [`docs/AUTH.md`](docs/AUTH.md) |
| Scanning/connecting (BLE + CDC), firmware update (DFU) | [`docs/CONNECTION.md`](docs/CONNECTION.md) |
| Sensor streams, status/config, SD recording | [`docs/SENSORS.md`](docs/SENSORS.md) |
| Every callback in the SDK | [`docs/CALLBACKS.md`](docs/CALLBACKS.md) |
| Publishing sensors to Lab Streaming Layer (`mudra_sdk.lsl`) | [`docs/LSL.md`](docs/LSL.md) |

## Related documentation

- Doc index: **[`docs/DOCS_MAP.md`](docs/DOCS_MAP.md)** · Repo landing: **[`README.md`](README.md)**
- Sign-in & licensing reference: **[`docs/AUTH.md`](docs/AUTH.md)**
- Docs site (built from these same docs): **[kavana-tech.github.io/Indriya](https://kavana-tech.github.io/Indriya/)**
