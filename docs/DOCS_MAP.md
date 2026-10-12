# Documentation map — Indriya

> **The master index for every doc in this repo.** Every documentation file is a node
> below; where a doc already carries its own "Part of / See also" links (the
> `docs/*.md` pages do), use those to hop between neighbours once you're inside a
> topic — come back here to find the topic in the first place.

---

## Start here

| Doc | What it is |
| --- | --- |
| **[`README.md`](../README.md)** | Repo landing page: what this SDK is, quick start, pointer to the usage guide. |
| **[`AGENTS.md`](../AGENTS.md)** | Agent entry point: **Rule 0** (sign in *before* connecting — the SDK then provisions the device's license itself on every connect) and **Rule 1** (your app turns off the sensors it enables), plus a signpost to the rest. Auto-loaded by most coding agents, so it's the first thing a downstream project's agent reads. |
| **[`docs/SDK_USAGE.md`](SDK_USAGE.md)** | The main usage guide: package layout, setup, core architecture, a minimal end-to-end example. Links out to every page below. |
| **[`CHANGELOG.md`](../CHANGELOG.md)** | What changed, release by release. |
| **[`supported_firmware.json`](../supported_firmware.json)** | The one firmware version per model this SDK version supports. Single source for the "Firmware compatibility" statements in `README.md`, `AGENTS.md`, `docs/installation.md` and `docs/supported_devices.md` — generated blocks: never hand-edit between the `firmware-versions` markers. |
| **[Docs site](https://kavana-tech.github.io/Indriya/)** | The `docs/` guides below plus the site-only pages, published as a browsable Sphinx site (installation, quickstart, API reference). `README.md`, `AGENTS.md` and this map aren't on it. |

## SDK usage guide (`docs/`)

| Doc | What it is |
| --- | --- |
| **[`SDK_USAGE.md`](SDK_USAGE.md)** | Package layout, setup, `Mudra`/`MudraDevice`/`MudraDelegate` architecture, a minimal end-to-end example, the key-enums quick reference. |
| **[`AUTH.md`](AUTH.md)** | Account sign-in and device licensing — **read before building an app**, not just a script. Covers `mudra_sdk.auth`, device-level license query/apply, and `LicenseManager` auto-renewal. |
| **[`CONNECTION.md`](CONNECTION.md)** | Scanning, connecting/disconnecting over BLE and CDC, ping, licensing/account sign-in (short version — see `AUTH.md` for the full one), raw/advanced commands, firmware update (DFU). |
| **[`SENSORS.md`](SENSORS.md)** | Enabling/disabling sensor streams, querying/configuring status (ODR, resolution, ranges), packet-loss test mode, SD card recording. |
| **[`CALLBACKS.md`](CALLBACKS.md)** | Every callback in the SDK — the global `MudraDelegate` and all per-device `set_on_*` callbacks — with signatures and firing conditions. |
| **[`LSL.md`](LSL.md)** | Lab Streaming Layer integration (`mudra_sdk.lsl`): publish a connected Pro/Ultimate device's sensors as LSL streams via `MudraLslBridge` or the `examples/lsl_app.py` CLI — stream layout, device-clock timestamps, reconfiguring and reconnecting, multiple devices. |

## Site-only pages (`docs/`)

Written for the docs site, not duplicated elsewhere. Readable on GitHub too.

| Doc | What it is |
| --- | --- |
| **[`index.rst`](index.rst)** | Site landing page and master toctree. |
| **[`installation.md`](installation.md)** | Requirements, installing dependencies, the native library, which calls are `async`. |
| **[`getting_started.md`](getting_started.md)** | Quickstart: scan, connect and stream over BLE or USB-CDC with the same calls. |
| **[`supported_devices.md`](supported_devices.md)** | Mudra Pro vs. Mudra Ultimate (EMG channels/AFE, model-specific extras) and the firmware this SDK release supports. |
| **[`examples.md`](examples.md)** | The two runnable apps (Mudra Connect GUI, LSL streamer) and what each covers. |
| **[`data_format.md`](data_format.md)** | What's inside each sensor callback's `samples` list — layout, units, timestamps. |
| **[`api_reference.rst`](api_reference.rst)** | Autodoc API reference for the public `mudra_sdk` surface. |
| **[`native_library.md`](native_library.md)** | The C++ `MudraSDK` library: what it does, what needs it, how CI builds and commits the per-platform binaries. |
| **[`troubleshooting.md`](troubleshooting.md)** | Common integration problems and fixes. |
| **[`faq.md`](faq.md)** | Short answers to common questions (accounts, BLE vs. CDC, what `connect()` returning means, LSL, PyPI, …). |
| [`conf.py`](conf.py) / [`requirements.txt`](requirements.txt) / `Makefile` / `make.bat` | Sphinx build config and build dependencies (`_static/`, `_templates/` hold theme assets and the fuzzy-search page). |

## Native library (`mudra_sdk/core/`, `mudra_sdk/libs/`)

| Doc | What it is |
| --- | --- |
| **[`mudra_sdk/core/CMakeLists.txt`](../mudra_sdk/core/CMakeLists.txt)** | Builds `MudraSDK.{dll,so,dylib}` and resolves the `mudra_sdk/libs/<platform>/<arch>/` output layout that `library_loader.py` expects. |
| `.github/workflows/build-native.yml` *(internal repo only)* | CI: builds the native library for windows-x64, macos-arm64, macos-x86_64, linux-x86_64, and linux-aarch64 on every push touching `mudra_sdk/core/**`, then commits the rebuilt binaries into `mudra_sdk/libs/`. |

## Example apps (`examples/`)

| Doc | What it is |
| --- | --- |
| `examples/connect_app.py` / `examples/mudra_connect/` | The full reference app (scan, connect, sensors, recording, firmware update, auth) that the code snippets in `docs/SDK_USAGE.md`, `CONNECTION.md`, `SENSORS.md`, `CALLBACKS.md` and `AUTH.md` are taken from. No separate README — the module docstrings and `docs/SDK_USAGE.md` are the guide. |
| `examples/lsl_app.py` / `examples/mudra_lsl/` | Headless command-line streamer: scan, optionally sign in, connect, optionally change sensor ODRs, and publish the sensors to Lab Streaming Layer until stopped. Source of `docs/LSL.md`'s snippets; guide: [`docs/LSL.md`](LSL.md) §2. |

## Repo-internal (maintainers only)

Not on the docs site and not in the public release mirror — they exist only in
the internal repo, so they're described here without links.

| Doc | What it is |
| --- | --- |
| `CLAUDE.md` (repo root) | Claude Code project instructions: commands, architecture overview, the docs-site spec, firmware-version automation. |
| `docs/CLAUDE.md` | Docs-site gotchas: what may be published, `conf.py` notes, links outside `docs/`, page inventory. |
| `.github/workflows/` | CI: `build-native.yml` (native library), `docs.yml` (build + deploy the site), `firmware-versions.yml` / `firmware-sdk-record.yml` (firmware ↔ SDK version sync), `sync-indriya.yml` (release snapshot to the public repo). |
| `.github/scripts/firmware_versions.py` | Renders/checks/sets the generated firmware-version blocks from `supported_firmware.json`. |
| `.github/indriya-sync-exclude.txt` | Paths left out of the public release snapshot. |

---

## Maintaining this map

- **Adding a doc?** Add a row here in the right section. If it's one of the
  `docs/*.md` usage-guide pages, also add it to the doc table near the top of
  [`SDK_USAGE.md`](SDK_USAGE.md) so both indexes stay in sync.
- **Adding a published page?** Also add it to `docs/index.rst`'s toctree, the page
  inventory in `docs/CLAUDE.md`, and the docs-site layout list in the root `CLAUDE.md`.
- This repo has no dev/production branch split, so unlike some other SDKs in this
  org, there's no separate "shippable-only" index to keep in sync — this file is it.

## Related documentation

- Agent entry point: **[`AGENTS.md`](../AGENTS.md)**
- Usage guide: **[`SDK_USAGE.md`](SDK_USAGE.md)** · Repo landing: **[`README.md`](../README.md)**
