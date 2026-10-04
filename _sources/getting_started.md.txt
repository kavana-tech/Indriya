# Quickstart

One API, two transports: scan over **BLE**, over **USB-CDC**, or both at
once — the same `Mudra`/`MudraDevice` calls work either way.

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

A few things worth knowing before you build on this:

- **Setting a sensor callback *is* the enable/disable action** — there's no
  separate "power on" call. `set_on_emg_ready(fn)` enables EMG and starts
  delivering samples to `fn`; `set_on_emg_ready(None)` disables it. Same
  shape for `set_on_imu_h_ready` / `set_on_imu_f_ready` / `set_on_ppg_ready`.
  See [SENSORS.md](SENSORS.md).
- **`device.connect()` returning isn't the same as "fully ready."** BLE is
  ready once its COMMAND characteristic is discovered; CDC needs the SDK to
  query sensor status and then send `START` before data flows. Drive
  readiness-dependent logic off `on_mudra_device_connected`, not the
  `connect()` return. See [SDK_USAGE.md §4](SDK_USAGE.md#4-minimal-end-to-end-example).
- **Connecting never requires an account.** The device streams at whatever
  license tier it already holds. See [AUTH.md](AUTH.md) before shipping an
  app that's meant to unlock `PLUS`/`PRO` features.

## Next

- [Usage guide](SDK_USAGE.md) — package layout, the `Mudra`/`MudraDevice`/`MudraDelegate` architecture.
- [Connection guide](CONNECTION.md) — scanning, connect/disconnect, ping, raw commands, firmware update.
- [Sensors guide](SENSORS.md) — enabling streams, status/config, packet-loss test mode, SD recording.
- [Callbacks reference](CALLBACKS.md) — every callback in the SDK.
- [Lab Streaming Layer guide](LSL.md) — publish a device's sensors to LSL for LabRecorder and other consumers.
- [Examples](examples.md) — two full runnable reference apps.
