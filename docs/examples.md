# Examples

Two runnable apps live under `examples/`, both built entirely on the public
`mudra_sdk` API, never by touching BLE/serial wire formats directly:

- **Mudra Connect** ([`examples/connect_app.py`](../examples/connect_app.py),
  the `examples/mudra_connect` package) — a Tkinter GUI covering scan,
  connect, sensors, recording and auth. Most snippets in the
  [usage guide](SDK_USAGE.md) and its sub-pages follow patterns from it.
- **LSL streamer** ([`examples/lsl_app.py`](../examples/lsl_app.py), the
  `examples/mudra_lsl` package) — a headless command-line app that publishes
  a device's sensors to Lab Streaming Layer.

Both launchers put the repo root on `sys.path` themselves, so run them from
anywhere with `python examples/<app>.py`. Install their dependencies with
`pip install -r examples/requirements.txt` (the SDK's own requirements plus
`matplotlib` and `pylsl`).

The GUI needs Tkinter, which ships with the python.org installers on
Windows/macOS; on Linux install it from your distro (e.g. `python3-tk`). It
runs its own asyncio event loop on a background thread
([`examples/mudra_connect/async_bridge.py`](../examples/mudra_connect/async_bridge.py))
since Tkinter isn't async-native.

```{raw} html
<div class="ex-index">
  <a class="ex-index-item" href="#mudra-connect">
    <span class="ex-index-head"><span class="ex-index-name">Mudra Connect</span></span>
    <span class="ex-index-desc">The full reference app — scan, connect, live sensor charts, config, packet-loss, SD recording, firmware update, auth.</span>
  </a>
  <a class="ex-index-item" href="#headless-stream-to-lab-streaming-layer">
    <span class="ex-index-head"><span class="ex-index-name">LSL streamer</span></span>
    <span class="ex-index-desc">Headless command-line app — find a device, connect, and publish its sensors as Lab Streaming Layer streams.</span>
  </a>
</div>
```

## Mudra Connect

```
pip install -r examples/requirements.txt
python examples/connect_app.py
```

The primary reference app — [`examples/connect_app.py`](../examples/connect_app.py)
launches the `examples/mudra_connect` package, whose files are listed below
(paths relative to that package). Every panel maps to one guide page:

| Panel | Source | Covers |
|---|---|---|
| Devices | `devices.py` | BLE/CDC scan toggles, connect/disconnect — [CONNECTION.md §1–2](CONNECTION.md) |
| Sensor charts | `charts.py`, `sensors.py` | Live EMG/IMU/PPG_H/PPG_F plots, per-sensor enable — [SENSORS.md §1](SENSORS.md#1-enable--disable-a-sensors-data-stream) |
| Config | `panels/config.py` | ODR/resolution/range get/set per sensor — [SENSORS.md §3](SENSORS.md#3-configure-a-sensor-odr-resolution-ranges-etc) |
| Packet loss | `panels/packet_loss.py`, `packet_loss_chart.py` | Test-mode toggle + live loss chart — [SENSORS.md §4](SENSORS.md#4-packet-loss-test-mode) |
| Recording | `panels/recording.py` (SD) / `panels/pc_recording.py` (host-side JSON) | SD-card recording — [SENSORS.md §5](SENSORS.md#5-sd-card-recording-ble-only) |
| Ping | `panels/ping.py`, `ping_chart.py` | Round-trip latency — [CONNECTION.md §3](CONNECTION.md#3-ping--round-trip-check) |
| Command | `panels/command.py` | Raw/advanced commands, branching on `device.transport` — [CONNECTION.md §4](CONNECTION.md#4-raw--advanced-commands) |
| Auth | `panels/auth.py` | Sign-in bar — [AUTH.md](AUTH.md) |
| Device indicators | `status_ui.py` | Toolbar FW / battery / license-tier readouts, plus every status callback the app registers — [CALLBACKS.md](CALLBACKS.md) |
| Firmware update | `panels/dfu.py` | DFU over USB-CDC — [CONNECTION.md §6](CONNECTION.md#6-firmware-update-dfu-usb-only) |

The window looks the same on Windows, macOS and Linux: `theme.py` picks an
installed UI font and sizes text and spacing from the display's scale
(including Linux desktop scaling, which Tk doesn't detect on its own), and
side columns start at the width their content needs — drag a column's edge
to resize it. If the detected scale looks wrong, override it, e.g.
`MUDRA_UI_SCALE=1.5 python examples/connect_app.py`.

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
