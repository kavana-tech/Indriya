# Installation

There is no PyPI package yet. The SDK is used by adding the repo root to
`sys.path` and importing `mudra_sdk` directly — exactly what the reference
apps under `examples/` do:

```python
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent  # the folder that contains mudra_sdk/
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from mudra_sdk import Mudra, MudraDevice
```

Requirements: **Python 3.10+** (the codebase uses `dict[str, ...]`-style
builtin generics and `X | None` unions) — **64-bit** Python on Windows (see
[The native library](#the-native-library) below). `git` must be on your
`PATH`, because `bleak` installs from a git URL. Everything the SDK needs is
pinned in `mudra_sdk/requirements.txt`:

```bash
pip install -r mudra_sdk/requirements.txt
```

What that installs, and why:

- **`bleak`** (the [wearable-devices fork](https://github.com/wearable-devices/bleak), `develop` branch) — the BLE transport.
- **`pyserial`** — the USB-CDC transport (scanning, opening `CONFIG`/`DATA` ports).
- **`requests`** / **`urllib3`** — the cloud client behind `mudra_sdk.auth` (sign-in, license token fetch).
- **`smpclient`** — firmware update (DFU) over USB-CDC via MCUmgr/SMP.

Your device also needs the firmware this SDK release supports:

<!-- firmware-versions:sentence -->

This SDK version (**0.5.2**) supports Mudra Pro firmware **2.0.2.6** and Mudra Ultimate firmware **1.0.3.9**.

<!-- /firmware-versions -->

See [Firmware compatibility](supported_devices.md#firmware-compatibility).

If you're also running the example apps, install their extra
dependencies too (this pulls in `mudra_sdk/requirements.txt` transitively):

```bash
pip install -r examples/requirements.txt   # adds matplotlib and pylsl
```

On Linux: BLE goes through BlueZ (the Bluetooth service must be running),
and opening the USB-CDC serial ports usually requires your user to be in the
`dialout` group (or equivalent udev rule).

To publish sensor streams onto the Lab Streaming Layer (`mudra_sdk.lsl`,
[LSL.md](LSL.md)), install the optional `pylsl` dependency — nothing else in
the SDK needs it:

```bash
pip install pylsl   # liblsl ships in the Windows/macOS wheels; examples/requirements.txt includes it
```

## The native library

`mudra_sdk/core/` is a C++ project that builds `MudraSDK.{dll,so,dylib}` into
`mudra_sdk/libs/<platform>/<arch>/`. Prebuilt binaries for
windows-x64/macos-arm64/macos-x86_64/linux-x86_64/linux-aarch64 are **checked
into the repo** — rebuilt by CI whenever `mudra_sdk/core/**` changes —
so you never need a C++ toolchain just to use the SDK. On Windows only the
`x64` binary is current, so use 64-bit Python; the `windows/x86` binary in
the tree is stale and unsupported. See
[native_library.md](native_library.md) if you need to build it yourself.

`Mudra()` loads this library lazily on first construction
(`mudra_sdk/libs/library_loader.py`, via `ctypes`). **The library is required
for any device work.** If it's missing for your platform, `Mudra()` still
constructs (it logs a warning instead of raising), but every `MudraDevice`
raises `RuntimeError("Native library is not loaded")` when it's created — so
scans find nothing and nothing can connect. The library also supplies
command encoding, sensor-data parsing, packet-loss stats and
`get_json_recording()`. Only cloud calls (`mudra_sdk.auth` and the cloud
client) work without it.

## Mostly `async`

Device and transport calls — scanning, `connect()`/`disconnect()`, the
`set_on_*` callback setters, and the `get_*`/`set_*` sensor commands — are
coroutines; call them from inside an asyncio event loop. A few calls are
plain synchronous functions:

- cached getters such as `get_*_status_info()`, `get_license_device_info()`,
  `get_firmware_version_info()`, and `get_json_recording()`;
- `mudra_sdk.auth.sign_in_email()` / `logout()` / `get_user_ref()`;
- every `MudraServerClient` call — these do blocking HTTP, so from async code run
  them via `asyncio.to_thread(...)` (or `loop.run_in_executor`).

Callbacks you register are plain functions too (use `def`, not `async def`).

A plain script can just use `asyncio.run(...)`; a GUI app that isn't
async-native (like the Tkinter connect app under `examples/`) needs to run
its own event loop on a background thread — see
[`examples/mudra_connect/async_bridge.py`](../examples/mudra_connect/async_bridge.py)
for that pattern.

## Next

- [Quickstart](getting_started.md) — scan, connect, and stream in a dozen lines.
- [Usage guide](SDK_USAGE.md) — package layout and core architecture.
- [Supported devices](supported_devices.md) — Mudra Pro vs. Mudra Ultimate.
