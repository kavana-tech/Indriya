# Native library

`mudra_sdk/core/` is a C++ CMake project that builds `MudraSDK.{dll,so,dylib}`
— the native library that parses raw sensor byte streams (BLE notifications /
CDC serial reads) into timestamped per-sensor sample buffers and tracks
packet-loss statistics. `mudra_sdk/libs/library_loader.py` loads it via
`ctypes` at runtime, from `mudra_sdk/libs/<platform>/<arch>/`.

## What needs it

The library is **required for any device work**. `Mudra()` loads it lazily,
inside `__init__`, and only logs a warning if it's missing or fails to load:

```python
# mudra_sdk/models/mudra.py
try:
    self._native_lib = load_library('MudraSDK', 'MudraSDK')
except (FileNotFoundError, OSError) as e:
    logger.warning(f"Could not load native library: {e}")
    self._native_lib = None
```

But every `MudraDevice` creates a `ComputationWrapper` around it, which raises
`RuntimeError("Native library is not loaded")` when the library is absent —
so no device object can be created, and scans find nothing. Besides parsing
sensor data and tracking packet loss, the library also holds the per-model
command tables (the BLE command bytes and USB-CDC command tokens), and backs
the PC-side recording and `get_json_recording()`.

Without it, only the cloud side works: `mudra_sdk.auth` sign-in and the
cloud client.

## CI builds and commits the binaries

You almost never need to build this yourself — prebuilt binaries for every
supported platform/arch are **checked into the repo** under `mudra_sdk/libs/`,
rebuilt and re-committed by the maintainers' CI whenever `mudra_sdk/core/**`
changes, across:

- windows-x64 (64-bit Python only — the `windows/x86` binary in the tree is
  stale and unsupported)
- macos-arm64, macos-x86_64 (`mudra_sdk/libs/darwin/...`)
- linux-x86_64, linux-aarch64

If you do change anything under `mudra_sdk/core/`, **don't hand-edit the
`.dll`/`.so`/`.dylib` files** — build locally instead. Note that a local
build writes straight into `mudra_sdk/libs/<platform>/<arch>/`, **overwriting
the checked-in binary** for your platform:

```bash
cmake -S mudra_sdk/core -B mudra_sdk/core/build -DCMAKE_BUILD_TYPE=Release
cmake --build mudra_sdk/core/build --config Release --parallel
```

See [`mudra_sdk/core/CMakeLists.txt`](../mudra_sdk/core/CMakeLists.txt) for
the exact output layout `library_loader.py` expects.
