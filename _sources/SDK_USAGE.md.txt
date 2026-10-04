# Mudra SDK — Usage Guide

Python SDK for the **Mudra Pro** wearable device. It supports two transports —
**BLE** (Bluetooth Low Energy) and **CDC** (USB serial) — behind one unified,
`asyncio`-based API.

It is written to be usable both by humans and by other coding agents/bots
that need to integrate against this SDK — every code snippet in this guide
set is a real, runnable pattern taken from the SDK itself and from the
reference app at [`examples/connect_app.py`](../examples/connect_app.py) /
[`examples/mudra_connect/`](../examples/mudra_connect/).

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
  models/
    mudra.py             Mudra — top-level singleton: scan/connect/disconnect, delegate dispatch
    mudra_device.py      MudraDevice — per-device API: sensors, streaming, storage
    cdc_device.py         CdcDevice — CDC device identity (address/ports)
    callbacks.py          MudraDelegate / BleServiceDelegate / CdcServiceDelegate ABCs
    enums.py              FirmwareCommand, SensorTypes, ODR/range enums, status/error codes
    computation_wrapper.py Thin wrapper around the native MudraSDK library (parsing, packet loss)
    firmware_protocol.py  Binary CONFIG-frame builders used by the BLE transport
  service/
    ble_service.py        BLE transport (bleak) — scanning, GATT, notifications
    cdc_service.py         CDC transport (pyserial) — USB serial scanning, ASCII protocol
    dfu_service.py         Firmware update (MCUmgr/SMP over a third USB-CDC port) — USB only
  lsl/                    Optional Lab Streaming Layer publisher (MudraLslBridge) — see LSL.md
  libs/                   Native MudraSDK shared library (.dll/.so/.dylib), loaded via ctypes
```

The public surface is re-exported from the package root:

```python
from mudra_sdk import Mudra, MudraDevice, FirmwareCallbacks, FirmwareDetails
```

## 2. Setup

There is no PyPI package / `pip install` yet — the SDK is used by adding the
repo root to `sys.path`, exactly as the example app does:

```python
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent  # wherever mudra_sdk/ lives
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from mudra_sdk import Mudra, MudraDevice
```

Dependencies: `bleak` (BLE), `pyserial` (CDC), `smpclient` (firmware update
over CDC — see [CONNECTION.md §6](CONNECTION.md#6-firmware-update-dfu-usb-only)).
The native `MudraSDK`
shared library under `mudra_sdk/libs/<platform>/<arch>/` is loaded
automatically and does the binary sensor-data parsing; if it's missing for
your platform, `Mudra()` still constructs but logs a warning and native-side
features (data parsing, packet-loss stats) won't work.

Everything in the SDK is `async` — call it from inside an asyncio event
loop. The example app runs its own asyncio loop on a background thread (see
[`examples/mudra_connect/async_bridge.py`](../examples/mudra_connect/async_bridge.py))
because it's a Tkinter GUI; a plain script can just use `asyncio.run(...)`.

## 3. Core architecture

- **`Mudra`** — a process-wide singleton. Owns both transports
  (`BleService`, `CdcService`) and dispatches every device event to *your*
  delegate. You never construct more than one; `Mudra()` always returns the
  same instance.
- **`MudraDevice`** — one object per physical device, valid for either
  transport. Check `device.transport` (`"ble"` or `"cdc"`) if you need to
  branch — most callers don't need to, since every method already branches
  internally and picks the right wire format.
- **`MudraDelegate`** — an abstract base class you implement to receive
  connection lifecycle events and device-discovery events. Register it once
  via `Mudra().set_delegate(...)`. See [CALLBACKS.md](CALLBACKS.md).
- **Per-device callbacks** — sensor data, status replies, errors, etc. are
  delivered per-device via `await device.set_on_..._callback(fn)` setters,
  not through the global delegate. See [CALLBACKS.md](CALLBACKS.md).

```
Mudra()  ── scan_ble()/scan_cdc() ──► MudraDelegate.on_device_discovered(device)
        │                                     │
        │                          device.connect() (transport-aware)
        │                                     ▼
        │                    MudraDelegate.on_mudra_device_connected(device)
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

    def on_mudra_device_connected(self, device: MudraDevice): print("connected")
    def on_mudra_device_connecting(self, device: MudraDevice): print("connecting...")
    def on_mudra_device_disconnecting(self, device: MudraDevice): print("disconnecting...")
    def on_mudra_device_disconnected(self, device: MudraDevice): print("disconnected")
    def on_mudra_device_connection_failed(self, device: MudraDevice, error: str):
        print(f"connect failed: {error}")
    def on_bluetooth_state_changed(self, state: bool): print(f"BT on={state}")

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
    await device.connect()          # waits for the connect() coroutine, not the "connected" event

    def on_emg(timestamp, samples, frequency, frequency_std):
        print(f"EMG @ {frequency}Hz: {len(samples)} samples")

    await device.set_on_emg_ready(on_emg)   # enables the EMG sensor + starts streaming
    await asyncio.sleep(5)
    await device.set_on_emg_ready(None)     # disables it again

    await device.disconnect()

asyncio.run(main())
```

Note the ordering subtlety: `device.connect()` *returns* once the transport
handshake is done, but `MudraDelegate.on_mudra_device_connected` may still
be about to fire (BLE: after GATT discovery; CDC: after the SDK's own
readiness queries + `START`). If your logic depends on the device being
fully ready (not just the socket open), drive it off the delegate callback
rather than the `await device.connect()` return, same as the reference app
does in [`delegate.py`](../examples/mudra_connect/delegate.py).

For everything beyond this minimal example, see:
[CONNECTION.md](CONNECTION.md) · [SENSORS.md](SENSORS.md) · [CALLBACKS.md](CALLBACKS.md)

## 5. Quick reference — key enums (`mudra_sdk.models.enums`)

| Enum | Values | Used for |
|---|---|---|
| `SensorTypes` | `EMG`, `H_IMU`, `F_IMU`, `PPG` | Identifying a sensor in status/error callbacks |
| `FirmwareDataType` | `emg`, `imuH`, `imuF`, `ppg` | Identifying a sensor when enabling/disabling streams |
| `ProEMGODR` | 200/400/800/1600/2133/3200/4267/6400 (Hz) | `set/get_emg_odr` on MudraPro |
| `UltimateEMGODR` | 500/1000/2000/4000 (Hz) | `set/get_emg_odr` on MudraUltimate |
| `EmgRes` | 16, 24 (bits) | `set/get_emg_res` |
| `IMUODR` | 25/50/100/200/400/800/1600 (Hz) | `set/get_{h,f}_imu_odr` |
| `IMUAccRange` | 2/4/8/16 (g) | `set/get_{h,f}_imu_acc` |
| `IMUGyrRange` | 125/250/500/1000/2000 (dps) | `set/get_{h,f}_imu_gyr` |
| `PPGODR` | 25/50/100/200/400 (Hz) | `set/get_ppg_odr` |
| `PPGChannelCount` | 1–4 | Reported in `PpgStatus.channel_count` |
| `BtCmdId` | `SYSTEM`, `EMG`, `H_IMU`, `F_IMU`, `PPG`, `BAT`, `LED`, `BT_CTRL`, `TAP`, `STORAGE` | Identifying which subsystem a command-error is about |
| `BtCmdStatus` | `OK`, `ERR_UNKNOWN`, `ERR_INVALID`, `ERR_BUSY`, `ERR_STATE`, `ERR_HARDWARE`, `ERR_INTERNAL`, `ERR_BT_NOT_READY`, `ERR_LICENSE`, `ERR_BLE_RATE`, `ERR_FILE_EXISTS`, `ERR_SD_WRITE` | Error codes on any failed command |

Every enum has `.value_int` and a static `.from_value(int)`; several also
have `.description` (human-readable name) — use those rather than the raw
`.value` for anything user-facing or logged.
