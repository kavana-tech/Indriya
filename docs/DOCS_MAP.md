# Documentation map — Indriya

> **The master index for every doc in this repo.** Every documentation file is a node
> below; where a doc already carries its own "Part of / See also" links (the
> `docs/*.md` pages do), use those to hop between neighbours once you're inside a
> topic — come back here to find the topic in the first place.

---

## Start here

| Doc | What it is |
| --- | --- |
| **[`README.md`](../README.md)** | Repo landing page: what this SDK is, pointer to the usage guide. |
| **[`AGENTS.md`](../AGENTS.md)** | Agent entry point: **Rule 0** (sign in → provision the device before assuming a tier) and a signpost to the rest. Auto-loaded by most coding agents, so it's the first thing a downstream project's agent reads. |
| **[`docs/SDK_USAGE.md`](SDK_USAGE.md)** | The main usage guide: package layout, setup, core architecture, a minimal end-to-end example. Links out to every page below. |
| **[`CHANGELOG.md`](../CHANGELOG.md)** | What changed, release by release. |
| **[`supported_firmware.json`](../supported_firmware.json)** | The one firmware version per model this SDK version supports. Single source for the "Firmware compatibility" statements in `README.md`, `AGENTS.md`, `docs/installation.md` and `docs/supported_devices.md` (generated blocks — see the root `CLAUDE.md`). |
| **[Docs site](https://kavana-tech.github.io/Indriya/)** | Everything below, published as a browsable Sphinx site (installation, quickstart, API reference). Built from these same files. |

## SDK usage guide (`docs/`)

| Doc | What it is |
| --- | --- |
| **[`SDK_USAGE.md`](SDK_USAGE.md)** | Package layout, setup, `Mudra`/`MudraDevice`/`MudraDelegate` architecture, a minimal end-to-end example, the key-enums quick reference. |
| **[`AUTH.md`](AUTH.md)** | Account sign-in and device licensing — **read before building an app**, not just a script. Covers `mudra_sdk.auth`, device-level license query/apply, and `LicenseManager` auto-renewal. |
| **[`CONNECTION.md`](CONNECTION.md)** | Scanning, connecting/disconnecting over BLE and CDC, ping, licensing/account sign-in (short version — see `AUTH.md` for the full one), raw/advanced commands, firmware update (DFU). |
| **[`SENSORS.md`](SENSORS.md)** | Enabling/disabling sensor streams, querying/configuring status (ODR, resolution, ranges), packet-loss test mode, SD card recording. |
| **[`CALLBACKS.md`](CALLBACKS.md)** | Every callback in the SDK — the global `MudraDelegate` and all per-device `set_on_*` callbacks — with signatures and firing conditions. |
| **[`LSL.md`](LSL.md)** | Lab Streaming Layer integration (`mudra_sdk.lsl`): publish a connected Pro/Ultimate device's sensors as LSL streams via `MudraLslBridge` or the `examples/lsl_app.py` CLI — stream layout, device-clock timestamps, reconfiguring and reconnecting, multiple devices. |

## Native library (`mudra_sdk/core/`, `mudra_sdk/libs/`)

| Doc | What it is |
| --- | --- |
| **[`mudra_sdk/core/CMakeLists.txt`](../mudra_sdk/core/CMakeLists.txt)** | Builds `MudraSDK.{dll,so,dylib}` and resolves the `mudra_sdk/libs/<platform>/<arch>/` output layout that `library_loader.py` expects. |
| **[`.github/workflows/build-native.yml`](../.github/workflows/build-native.yml)** | CI: builds the native library for windows-x64, macos-arm64, macos-x86_64, linux-x86_64, and linux-aarch64 on every push touching `mudra_sdk/core/**`, then commits the rebuilt binaries into `mudra_sdk/libs/`. |

## Example apps (`examples/`)

| Doc | What it is |
| --- | --- |
| `examples/connect_app.py` / `examples/mudra_connect/` | The full reference app (scan, connect, sensors, recording, auth) that every code snippet in `docs/SDK_USAGE.md` and its sub-pages is taken from. No separate README — the module docstrings and `docs/SDK_USAGE.md` are the guide. |
| `examples/lsl_app.py` / `examples/mudra_lsl/` | Headless command-line streamer: scan, optionally sign in, connect, optionally change sensor ODRs, and publish the sensors to Lab Streaming Layer until stopped. Guide: [`docs/LSL.md`](LSL.md) §2. |

---

## Maintaining this map

- **Adding a doc?** Add a row here in the right section. If it's one of the
  `docs/*.md` usage-guide pages, also add it to the doc table near the top of
  [`SDK_USAGE.md`](SDK_USAGE.md) so both indexes stay in sync.
- This repo has no dev/production branch split, so unlike some other SDKs in this
  org, there's no separate "shippable-only" index to keep in sync — this file is it.

## Related documentation

- Agent entry point: **[`AGENTS.md`](../AGENTS.md)**
- Usage guide: **[`SDK_USAGE.md`](SDK_USAGE.md)** · Repo landing: **[`README.md`](../README.md)**
