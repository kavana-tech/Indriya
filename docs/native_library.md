# Native library

`mudra_sdk/core/` is a C++ CMake project that builds `MudraSDK.{dll,so,dylib}`
— the native library that parses raw sensor byte streams (BLE notifications /
CDC serial reads) into timestamped per-sensor sample buffers and tracks
packet-loss statistics. `mudra_sdk/libs/library_loader.py` loads it via
`ctypes` at runtime, from `mudra_sdk/libs/<platform>/<arch>/`.

## It's optional at runtime

`Mudra()` loads the native library lazily, inside `__init__`, and **degrades
gracefully if it's missing or fails to load** — it logs a warning rather than
raising:

```python
# mudra_sdk/models/mudra.py
try:
    self._native_lib = load_library('MudraSDK', 'MudraSDK')
except (FileNotFoundError, OSError) as e:
    logger.warning(f"Could not load native library: {e}")
    self._native_lib = None
```

Without it: scanning, connecting, sensor enable/disable, status/config,
licensing, and SD recording control all still work — only binary sensor-data
parsing and packet-loss statistics are affected. If you're extending this
loader, keep that degrade-gracefully behavior; don't turn a missing library
into a hard failure.

## CI builds and commits the binaries

You almost never need to build this yourself — prebuilt binaries for every
supported platform/arch are **checked into the repo** under `mudra_sdk/libs/`,
and [`.github/workflows/build-native.yml`](../.github/workflows/build-native.yml)
rebuilds and re-commits them automatically on every push that touches
`mudra_sdk/core/**`, across:

- windows-x64
- macos-arm64, macos-x86_64
- linux-x86_64, linux-aarch64

If you do change anything under `mudra_sdk/core/`, **don't hand-edit the
`.dll`/`.so`/`.dylib` files** — let CI rebuild them, or build locally:

```bash
cmake -S mudra_sdk/core -B mudra_sdk/core/build -DCMAKE_BUILD_TYPE=Release
cmake --build mudra_sdk/core/build --config Release --parallel
```

See [`mudra_sdk/core/CMakeLists.txt`](../mudra_sdk/core/CMakeLists.txt) for
the exact output layout `library_loader.py` expects.
