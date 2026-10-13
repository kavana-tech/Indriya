# Mudra SDK — Usage Guide

Indriya is the Python SDK (package `mudra_sdk`) for the **Mudra Pro** and
**Mudra Ultimate** wearables. It supports two transports — **BLE** (Bluetooth
Low Energy) and **CDC** (the USB connection: the device's USB CDC-ACM virtual
serial ports) — behind one unified, `asyncio`-based API.

It is written to be usable both by humans and by other coding agents/bots
that need to integrate against this SDK. The snippets follow patterns taken
from the SDK itself and from the reference app,
[`examples/connect_app.py`](../examples/connect_app.py) (the launcher for the
`examples/mudra_connect` package). §4 below is a complete script; snippets
elsewhere are excerpts that assume an already-connected `device` and omit
imports unless they're shown.

This guide is split into focused pages:

| Page | Covers |
|---|---|
| **This page** | Package layout, setup, core architecture, a minimal end-to-end example |
| **[CONNECTION.md](CONNECTION.md)** | Scanning, connecting/disconnecting over BLE and CDC, ping, licensing/account sign-in, raw/advanced commands, firmware update (DFU) |
| **[AUTH.md](AUTH.md)** | Account sign-in and device licensing — **read this before building an app**, not just a script |
| **[SENSORS.md](SENSORS.md)** | Enabling/disabling sensor streams, querying/configuring status (ODR, resolution, ranges), packet-loss test mode, SD card recording |
| **[CALLBACKS.md](CALLBACKS.md)** | Every callback in the SDK — the global `MudraDelegate` and all per-device `set_on_*` callbacks — with signatures and firing conditions |
| **[LSL.md](LSL.md)** | Lab Streaming Layer integration — publishing a device's sensors as LSL streams (`mudra_sdk.lsl.MudraLslBridge`, `examples/lsl_app.py`) |

---

## 1. Package layout

```
mudra_sdk/
  auth.py                 Account sign-in + license/user_id provisioning (see AUTH.md)
  models/
    mudra.py              Mudra — top-level singleton: scan/connect/disconnect, delegate dispatch
    mudra_device.py       MudraDevice — per-device API: sensors, streaming, storage
    mudra_pro.py          MudraPro — Mudra Pro subclass (3-ch EMG)
    mudra_ultimate.py     MudraUltimate — Mudra Ultimate subclass (8-ch EMG)
    cdc_device.py         CdcDevice — CDC device identity (address/ports)
    callbacks.py          MudraDelegate / BleServiceDelegate / CdcServiceDelegate ABCs
    enums.py              Pro/UltimateFirmwareCommand, SensorTypes, ODR/range enums, status/error codes
    license_manager.py    LicenseManager — renews a device's license before it expires (see AUTH.md)
    data_recorder.py      PC-side JSON recording (start_recording/get_json_recording)
    computation_wrapper.py Thin wrapper around the native MudraSDK library (parsing, packet loss)
    firmware_protocol.py  Binary CONFIG-frame builders used by the BLE transport
  service/
    ble_service.py        BLE transport (bleak) — scanning, GATT, notifications
    cdc_service.py         CDC transport (pyserial) — USB serial scanning, ASCII protocol
    dfu_service.py         Firmware update (MCUmgr/SMP over a third USB-CDC port) — USB only
  lsl/                    Optional Lab Streaming Layer publisher (MudraLslBridge) — see LSL.md
  libs/                   Native MudraSDK shared library (.dll/.so/.dylib), loaded via ctypes
```

The main entry points:

```python
from mudra_sdk import Mudra, MudraDevice, MudraPro, MudraUltimate, MudraModel
from mudra_sdk import auth                          # sign-in + provisioning (AUTH.md)
from mudra_sdk.service import DfuError, DfuStage    # firmware update (CONNECTION.md §6)
```

`FirmwareCallbacks` and `FirmwareDetails` are also exported from the package
root, but they're internal protocol/constant tables, not something an app
needs.

## 2. Setup

There is no PyPI package / `pip install` yet — the SDK is used by adding the
repo root to `sys.path`, exactly as the example app does:

```python
import sys
from pathlib import Path

# Must be the folder that CONTAINS mudra_sdk/ (the repo root), not mudra_sdk/ itself.
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from mudra_sdk import Mudra, MudraDevice
```

Requires Python 3.10+. Install the dependencies with
`pip install -r mudra_sdk/requirements.txt` — `bleak` (BLE; installed from a
git fork, so `git` must be on your `PATH`), `pyserial` (CDC), `requests`/
`urllib3` (cloud), and `smpclient` (firmware update over CDC — see
[CONNECTION.md §6](CONNECTION.md#6-firmware-update-dfu-usb-only)).

The native `MudraSDK` shared library under `mudra_sdk/libs/<platform>/<arch>/`
is loaded automatically and is **required for any device work**: it parses
sensor data and also supplies the BLE command bytes and CDC command tokens.
If it's missing for your platform, `Mudra()` still constructs (with a logged
warning), but no `MudraDevice` can be created — each one raises
`RuntimeError("Native library is not loaded")` — so scans find nothing. Only
the cloud calls (`mudra_sdk.auth`, `MudraServerClient`) work without it.

**Async vs. sync.** Everything that talks to a device or transport is a
coroutine — scanning, `connect()`/`disconnect()`, every `set_on_*` setter,
and every `get_*`/`set_*` sensor command — so call it from inside an asyncio
event loop. The plain synchronous calls include the cached getters
(`get_*_status_info()`, `get_license_device_info()`,
`get_firmware_version_info()`, the packet-loss getters), `get_json_recording()`,
`auth.sign_in_email()`/`auth.logout()`/`auth.get_user_ref()`, and every
`MudraServerClient` call. The cloud ones do blocking HTTP — from async code, run
them via `await asyncio.to_thread(...)` (or `run_in_executor`). The example
app runs its own asyncio loop on a background thread (see
[`examples/mudra_connect/async_bridge.py`](../examples/mudra_connect/async_bridge.py))
because it's a Tkinter GUI; a plain script can just use `asyncio.run(...)`.

**Callbacks are plain functions.** Delegate methods and per-device `set_on_*`
callbacks are called directly (not awaited) on the asyncio loop thread — write
them with `def`, not `async def` (an `async def` callback never runs). Keep
them fast, and schedule any async follow-up with `asyncio.create_task(...)`.

## 3. Core architecture

- **`Mudra`** — a process-wide singleton. Owns both transports
  (`BleService`, `CdcService`) and dispatches every device event to *your*
  delegate. You never construct more than one; `Mudra()` always returns the
  same instance.
- **`MudraDevice`** — one object per discovered device address, on either
  transport (in practice a `MudraPro` or `MudraUltimate` subclass, picked from
  the detected model). The same physical device seen over both BLE and USB is
  two separate objects. Check `device.transport` (`"ble"` or `"cdc"`) if you
  need to branch — most callers don't need to, since every method already
  branches internally and picks the right wire format.
- **`MudraDelegate`** — an abstract base class you implement to receive
  connection lifecycle events and device-discovery events. Register it once
  via `Mudra().set_delegate(...)`. See [CALLBACKS.md](CALLBACKS.md).
- **Per-device callbacks** — sensor data, status replies, errors, etc. are
  delivered per-device via `await device.set_on_*(fn)` setters,
  not through the global delegate. See [CALLBACKS.md](CALLBACKS.md).

```
Mudra()  ── scan_ble()/scan_cdc() ──► MudraDelegate.on_device_discovered(device)
        │                                     │
        │                     await device.connect() (transport-aware)
        │                       (fires on_mudra_device_connected along the way)
        │                                     ▼
        │                       connect() returns → device ready
        │                                     │
        │                device.set_on_emg_ready(cb) / set_on_emg_status_received(cb) / ...
        ▼                                     ▼
   device.disconnect()              cb(...) fires as data/status arrives
```

## 4. Minimal end-to-end example

```python
import asyncio
from mudra_sdk import Mudra
from mudra_sdk.models.callbacks import MudraDelegate
from mudra_sdk.models.mudra_device import MudraDevice

class MyDelegate(MudraDelegate):
    def __init__(self):
        self.found = asyncio.Event()
        self.device: MudraDevice | None = None

    def on_device_discovered(self, device: MudraDevice):
        print(f"Found {device.name} ({device.transport}) @ {device.address}")
        self.device = device
        self.found.set()

    # All delegate methods are plain `def` — the SDK calls them without awaiting.
    def on_mudra_device_connected(self, device: MudraDevice): print("link open")
    def on_mudra_device_connecting(self, device: MudraDevice): print("connecting...")
    def on_mudra_device_disconnecting(self, device: MudraDevice): print("disconnecting...")
    def on_mudra_device_disconnected(self, device: MudraDevice): print("disconnected")
    def on_mudra_device_connection_failed(self, device: MudraDevice, error: str):
        print(f"connect failed: {error}")
    def on_bluetooth_state_changed(self, state: bool): pass  # required, but never fired

async def main():
    mudra = Mudra()
    delegate = MyDelegate()
    mudra.set_delegate(delegate)

    await mudra.scan_ble()
    await mudra.scan_cdc()
    await asyncio.wait_for(delegate.found.wait(), timeout=15)
    await mudra.stop_scan_ble()
    await mudra.stop_scan_cdc()

    device = delegate.device
    await device.connect()          # returns once the SDK's connect sequence is done; never raises
    if not await mudra.is_connected(device):
        return                      # failure was reported via on_mudra_device_connection_failed

    def on_emg(timestamp, samples, frequency, frequency_std):
        print(f"EMG @ {frequency}Hz: {len(samples)} samples")

    try:
        await device.set_on_emg_ready(on_emg)   # enables the EMG sensor + starts streaming
        await asyncio.sleep(5)
    finally:
        await device.set_on_emg_ready(None)     # turns it off again — disconnecting doesn't
        await device.disconnect()

asyncio.run(main())
```

**When is the device ready?** When `await device.connect()` returns. By then
the SDK has finished its connect sequence — BLE: services discovered,
notifications subscribed, initial status/license/`user_id` queries sent; CDC:
both ports opened and handshaken, initial status queries and provisioning
sent, then `START`. That's the point to enable sensors. Over BLE the status
*replies* arrive asynchronously afterwards (over CDC they're read back before
`connect()` returns) — register status callbacks before `connect()` if you
want them (see [SENSORS.md §2](SENSORS.md#2-query--observe-sensor-status)).

`MudraDelegate.on_mudra_device_connected` fires **earlier**, as soon as the
link is open and before that setup (BLE: before notifications are subscribed;
CDC: before the status queries and `START`) — use it for UI state, not as the
signal to start sending commands. `connect()` never raises on failure: a
failure arrives via `on_mudra_device_connection_failed`, so check
`await mudra.is_connected(device)` after it returns.

For everything beyond this minimal example, see:
[CONNECTION.md](CONNECTION.md) · [SENSORS.md](SENSORS.md) · [CALLBACKS.md](CALLBACKS.md)

## 5. Quick reference — key enums (`mudra_sdk.models.enums`)

| Enum | Values | Used for |
|---|---|---|
| `SensorTypes` | `EMG`, `H_IMU`, `F_IMU`, `PPG_H`, `PPG_F` | Mostly internal (status-reply routing); you rarely need it |
| `FirmwareDataType` | `emg`, `imuH`, `imuF`, `ppgH`, `ppgF` | Mostly internal (which stream to power on/off); you enable streams via `set_on_*_ready` instead |
| `ProEMGODR` | 200/400/800/1600/2133/3200/4267/6400 (Hz) | `set/get_emg_odr` on MudraPro |
| `UltimateEMGODR` | 500/1000/2000/4000 (Hz) | `set/get_emg_odr` on MudraUltimate |
| `EmgRes` | 16, 24 (bits) | `set/get_emg_res` |
| `IMUODR` | 25/50/100/200/400/800/1600 (Hz) | `set/get_{h,f}_imu_odr` |
| `IMUAccRange` | 2/4/8/16 (g) | Reported in `ImuStatus.accel_range_g`. `set_{h,f}_imu_acc` takes the plain int (e.g. `4`), not the enum member |
| `IMUGyrRange` | 125/250/500/1000/2000 (dps) | Reported in `ImuStatus.gyro_range_dps`. `set_{h,f}_imu_gyr` takes the plain int (e.g. `500`), not the enum member |
| `PPGODR` | 25/50/100/200/400 (Hz) | `set/get_ppg_h_odr` / `set/get_ppg_f_odr` (one chip-wide value) |
| `BtCmdId` | `SYSTEM`, `EMG`, `H_IMU`, `F_IMU`, `PPG_H`, `BAT`, `LED`, `BT_CTRL`, `TAP`, `STORAGE`, `PPG_F` | Identifying which subsystem a command-error is about |
| `BtCmdStatus` | `OK`, `ERR_UNKNOWN`, `ERR_INVALID`, `ERR_BUSY`, `ERR_STATE`, `ERR_HARDWARE`, `ERR_INTERNAL`, `ERR_BT_NOT_READY`, `ERR_LICENSE`, `ERR_BLE_RATE`, `ERR_FILE_EXISTS`, `ERR_SD_WRITE` | Error codes on any failed command |

Every enum in this table has `.value_int` and a static `.from_value(int)`
(returns `None` for an unknown value) — not every enum in the module does; `BtCmdId`/`BtCmdStatus` also have
`.description` (human-readable name) — use that rather than the raw `.value`
for anything user-facing or logged.
