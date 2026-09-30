# Installation

There is no PyPI package yet. The SDK is used by adding the repo root to
`sys.path` and importing `mudra_sdk` directly — exactly what the reference
apps under `examples/` do:

```python
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent  # wherever mudra_sdk/ lives
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from mudra_sdk import Mudra, MudraDevice
```

Requirements: **Python 3.10+** (the codebase uses `dict[str, ...]`-style
builtin generics and `X | None` unions). Everything the SDK needs is pinned in
`mudra_sdk/requirements.txt`:

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

This SDK version (**0.4.8**) supports Mudra Pro firmware **2.0.2.5** and Mudra Ultimate firmware **1.0.3.7**.

<!-- /firmware-versions -->

See [Firmware compatibility](supported_devices.md#firmware-compatibility).

If you're also running the reference GUI app, install its extra
dependencies too (this pulls in `mudra_sdk/requirements.txt` transitively):

```bash
pip install -r examples/requirements.txt   # adds matplotlib
```

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
into the repo** — rebuilt by CI on every push touching `mudra_sdk/core/**` —
so you never need a C++ toolchain just to use the SDK. See
[native_library.md](native_library.md) if you need to build it yourself.

`Mudra()` loads this library lazily on first construction
(`mudra_sdk/libs/library_loader.py`, via `ctypes`). **If it's missing for
your platform, the SDK still works** — `Mudra()` logs a warning instead of
raising — but native-side binary sensor-data parsing and packet-loss stats
won't function. Everything else (scanning, connecting, sensor
enable/disable, status, licensing, recording, DFU) is unaffected.

## Everything is `async`

Every SDK call is a coroutine — call it from inside an asyncio event loop. A
plain script can just use `asyncio.run(...)`; a GUI app that isn't
async-native (like the Tkinter reference apps under `examples/`) needs to run
its own event loop on a background thread — see
[`examples/mudra_connect/async_bridge.py`](../examples/mudra_connect/async_bridge.py)
for that pattern.

## Next

- [Quickstart](getting_started.md) — scan, connect, and stream in a dozen lines.
- [Usage guide](SDK_USAGE.md) — package layout and core architecture.
- [Supported devices](supported_devices.md) — Mudra Pro vs. Mudra Ultimate.
