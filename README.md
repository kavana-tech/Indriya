<img src="docs/_static/brand-logo.svg" alt="Mudra" height="44">

# Indriya

Python SDK for the **Mudra Pro** and **Mudra Ultimate** wrist-worn sensor devices —
one unified, `asyncio`-based API over two transports (**BLE** and **USB-CDC**) for
four sensor streams, SD-card recording, firmware update, and account sign-in/licensing.

📖 **Docs site: [kavana-tech.github.io/Indriya](https://kavana-tech.github.io/Indriya/)**
— installation, quickstart, guides, and the full API reference, built from the same
`docs/*.md` files linked below.

## Sensors

| Sensor | `FirmwareDataType` | Channels | Notes |
|---|---|---|---|
| EMG | `emg` | 3 (Mudra Pro) / 8 (Mudra Ultimate) | Different AFE per model, different ODR set — see [docs/supported_devices.md](docs/supported_devices.md) |
| Hand IMU | `imuH` | accel + gyro (6) | |
| Finger IMU | `imuF` | accel + gyro (6) | |
| PPG | `ppg` | 1–4, runtime-configurable | |

ODR, EMG resolution, and PPG channel/range config are all runtime-configurable —
see the [key enums quick reference](docs/SDK_USAGE.md#5-quick-reference--key-enums-mudra_sdkmodelsenums).

## Firmware compatibility

<!-- firmware-versions:sentence -->

This SDK version (**0.4.8**) supports Mudra Pro firmware **2.0.2.5** and Mudra Ultimate firmware **1.0.3.7**.

<!-- /firmware-versions -->

Other firmware versions aren't supported — see
[docs/supported_devices.md](docs/supported_devices.md#firmware-compatibility)
to check and update a device's firmware.

## Sign-in & licensing

**Connecting to a device never requires an account** — a signed-out app connects
and streams fine, at whatever license tier (`FREE`/`PLUS`/`PRO`) the device already
holds. Sign in via `mudra_sdk.auth` and provision the device on every connect if
your app is meant to unlock higher tiers — see [`AGENTS.md`](AGENTS.md) Rule 0 and
[docs/AUTH.md](docs/AUTH.md).

## Recording

SD-card recording (**`PRO`** tier, BLE only) — see
[docs/SENSORS.md §5](docs/SENSORS.md#5-sd-card-recording-ble-only) for usage.

## Lab Streaming Layer

Publish any connected device (Pro or Ultimate, BLE or USB) as LSL streams for
LabRecorder and other LSL consumers, timestamped from the device's own clock:

```python
from mudra_sdk.lsl import MudraLslBridge
async with MudraLslBridge(device, device_id="band0"):
    ...            # MudraPro-band0-EMG / -IMU_HAND / -IMU_RING / -PPG are live
```

or run `python examples/lsl_app.py` with no code. `pylsl` is an optional extra — see
[docs/LSL.md](docs/LSL.md).

## Related documentation

📖 **[docs/DOCS_MAP.md](docs/DOCS_MAP.md) is the index to every doc in this repo.** Common next stops:

- **Coding agent working in or on top of this SDK?** Start at **[AGENTS.md](AGENTS.md)**.
- **Usage guide:** [docs/SDK_USAGE.md](docs/SDK_USAGE.md) — package layout, setup, a minimal
  end-to-end example — with dedicated pages for [connection](docs/CONNECTION.md),
  [sensors](docs/SENSORS.md), [callbacks](docs/CALLBACKS.md), and
  [Lab Streaming Layer](docs/LSL.md). Written to be usable by
  other coding agents/bots integrating against this SDK, not just humans.
- **Sign-in & licensing:** [docs/AUTH.md](docs/AUTH.md).
- **Examples:** two runnable reference apps under [`examples/`](examples/) — see the
  [docs site's examples page](https://kavana-tech.github.io/Indriya/examples.html).
- **What changed, release by release:** [CHANGELOG.md](CHANGELOG.md).
