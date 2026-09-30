# Examples

A full, runnable Tkinter GUI app lives under `examples/` — a small
application built entirely on the public `mudra_sdk` API (scan, connect,
sensors, recording, auth), never by touching BLE/serial wire formats
directly. Every code snippet in the [usage guide](SDK_USAGE.md) and its
sub-pages is taken from it.

It runs its own asyncio event loop on a background thread
([`examples/mudra_connect/async_bridge.py`](../examples/mudra_connect/async_bridge.py))
since Tkinter isn't async-native.

```{raw} html
<div class="ex-index">
  <a class="ex-index-item" href="#mudra-connect">
    <span class="ex-index-head"><span class="ex-index-name">Mudra Connect</span></span>
    <span class="ex-index-desc">The full reference app — scan, connect, live sensor charts, config, packet-loss, SD recording, firmware update, auth.</span>
  </a>
</div>
```

## Mudra Connect

```
pip install -r examples/requirements.txt
python examples/connect_app.py
```

The primary reference app ([`examples/mudra_connect/`](../examples/mudra_connect/)) —
every panel maps to one guide page:

| Panel | Source | Covers |
|---|---|---|
| Devices | `devices.py` | BLE/CDC scan toggles, connect/disconnect — [CONNECTION.md §1–2](CONNECTION.md) |
| Sensor charts | `charts.py`, `sensors.py` | Live EMG/IMU/PPG plots, per-sensor enable — [SENSORS.md §1](SENSORS.md#1-enable--disable-a-sensors-data-stream) |
| Config | `panels/config.py` | ODR/resolution/range get/set per sensor — [SENSORS.md §3](SENSORS.md#3-configure-a-sensor-odr-resolution-ranges-etc) |
| Packet loss | `panels/packet_loss.py`, `packet_loss_chart.py` | Test-mode toggle + live loss chart — [SENSORS.md §4](SENSORS.md#4-packet-loss-test-mode) |
| Recording | `panels/recording.py` (SD) / `panels/pc_recording.py` (host-side JSON) | SD-card recording — [SENSORS.md §5](SENSORS.md#5-sd-card-recording-ble-only) |
| Ping | `panels/ping.py`, `ping_chart.py` | Round-trip latency — [CONNECTION.md §3](CONNECTION.md#3-ping--round-trip-check) |
| Command | `panels/command.py` | Raw/advanced commands, branching on `device.transport` — [CONNECTION.md §4](CONNECTION.md#4-raw--advanced-commands) |
| Auth | `panels/auth.py` | Sign-in bar + device license indicator — [AUTH.md](AUTH.md) |
| Firmware update | `panels/dfu.py` | DFU over USB-CDC — [CONNECTION.md §6](CONNECTION.md#6-firmware-update-dfu-usb-only) |

`delegate.py` is the reference `MudraDelegate` implementation — a good
template for your own ([CALLBACKS.md §1](CALLBACKS.md#1-mudradelegate-global-one-per-process)).

## Headless: stream to Lab Streaming Layer

Not a GUI, but the second runnable entry point — `python examples/lsl_app.py`
(a launcher over the `examples/mudra_lsl/` package, same shape as the app
above) finds a device, connects, and publishes its sensors as LSL streams until
stopped, so LabRecorder or any `pylsl` consumer can record them time-aligned
with other instruments:

```
pip install -r examples/requirements.txt      # includes pylsl
python examples/lsl_app.py --name 48-25 --sensors emg imu_hand --duration 60
```

See [LSL.md](LSL.md) for the options and for the library API
(`MudraLslBridge`) behind it.
