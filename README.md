<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/_static/brand-logo-tagline-light.png">
  <img src="docs/_static/brand-logo-tagline-dark.png" alt="Kavana — Neural Intent Data" height="64">
</picture>

# Indriya

Python SDK for the **Mudra Pro** and **Mudra Ultimate** wrist-worn sensor devices —
one unified, `asyncio`-based API over two transports (**BLE** and **USB-CDC**) for
five sensor streams, SD-card recording, firmware update, and account sign-in/licensing.

📖 **Docs site: [kavana-tech.github.io/Indriya](https://kavana-tech.github.io/Indriya/)**
— installation, quickstart, guides, and the full API reference, built from the same
`docs/*.md` files linked below.

## Quick start

There's no PyPI package — clone this repo and use it in place. Python **3.10+**;
`git` must be on `PATH` (the `bleak` dependency installs from a git URL).

```bash
pip install -r examples/requirements.txt   # SDK deps + the example apps' (matplotlib, pylsl)
python examples/connect_app.py             # reference GUI: scan, connect, stream, record
```

Full steps: [Installation](https://kavana-tech.github.io/Indriya/installation.html) ·
[Quickstart](https://kavana-tech.github.io/Indriya/getting_started.html).

## Sensors

| Sensor | `FirmwareDataType` | Channels | Notes |
|---|---|---|---|
| EMG | `emg` | 3 (Mudra Pro) / 8 (Mudra Ultimate) | Different AFE per model, different ODR set — see [docs/supported_devices.md](docs/supported_devices.md) |
| Hand IMU | `imuH` | accel + gyro (6) | |
| Finger IMU | `imuF` | accel + gyro (6) | Mudra Ultimate only (Mudra Pro firmware has no finger IMU) |
| Hand PPG | `ppgH` | 2 | Shares one PPG chip (and its ODR) with finger PPG |
| Finger PPG | `ppgF` | 2 | The ring's optical channels — needs the ring connected |

ODR, EMG resolution, IMU ranges and PPG optics (LED/TIA/source) are all runtime-configurable —
see the [key enums quick reference](docs/SDK_USAGE.md#5-quick-reference--key-enums-mudra_sdkmodelsenums).

## Firmware compatibility

<!-- firmware-versions:sentence -->

This SDK version (**0.5.0**) supports Mudra Pro firmware **2.0.2.6** and Mudra Ultimate firmware **1.0.3.8**.

<!-- /firmware-versions -->

Other firmware versions aren't supported — see
[docs/supported_devices.md](docs/supported_devices.md#firmware-compatibility)
to check and update a device's firmware.

## Sign-in & licensing

**Connecting to a device never requires an account** — a signed-out app connects
and streams fine, at whatever license tier (`FREE`/`PLUS`/`PRO`) the device already
holds. If your app is meant to unlock higher tiers, sign in via `mudra_sdk.auth`
**before connecting** — while signed in, the SDK provisions the device's license
itself on every connect. See [`AGENTS.md`](AGENTS.md) Rule 0 and
[docs/AUTH.md](docs/AUTH.md).

## Recording

SD-card recording (**`PRO`** tier, BLE only) — see
[docs/SENSORS.md §5](docs/SENSORS.md#5-sd-card-recording-ble-only) for usage.

## Lab Streaming Layer

Publish any connected device (Pro or Ultimate, BLE or USB) as LSL streams for
LabRecorder and other LSL consumers, timestamped from the device's own clock:

```python
from mudra_sdk.lsl import MudraLslBridge
async with MudraLslBridge(device, device_id="band0") as bridge:
    ...            # e.g. MudraPro-band0-EMG / -IMU_HAND / -PPG_H; bridge.streams lists what's live
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
