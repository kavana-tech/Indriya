# Mudra SDK — Lab Streaming Layer (LSL) Guide

> Part of the [Mudra SDK usage guide](SDK_USAGE.md). See also:
> [SENSORS.md](SENSORS.md) · [CALLBACKS.md](CALLBACKS.md) · [data_format.md](data_format.md)

[Lab Streaming Layer](https://labstreaminglayer.org/) is the standard way
research labs record several devices on one timeline: each device publishes
its data as named streams on the local network, and a recorder such as
[LabRecorder](https://github.com/labstreaminglayer/App-LabRecorder) saves them
all — a Mudra band, an EEG cap, an eye tracker — into one `.xdf` file.

`mudra_sdk.lsl` publishes a connected Mudra Pro or Mudra Ultimate device's
sensors as LSL streams, one stream per sensor. It is a thin layer on top of the
SDK's per-sensor streaming callbacks
([SENSORS.md §1](SENSORS.md#1-enable--disable-a-sensors-data-stream)), with no
device I/O of its own, so BLE and USB-CDC, Mudra Pro and Mudra Ultimate all
work the same.

```
mudra_sdk/lsl/
  bridge.py      MudraLslBridge — the part you use
  clock.py       DeviceClockMapper — device timestamps -> LSL time
  metadata.py    stream names, channel labels and units
examples/
  lsl_app.py     command-line streamer: `python examples/lsl_app.py` (§2)
  mudra_lsl/     the CLI itself (cli.py)
```

## 1. Install

`pylsl` is an **optional** dependency — nothing else in the SDK needs it, and
`import mudra_sdk.lsl` works without it. Only `MudraLslBridge.start()` does:

```bash
pip install pylsl
```

`pylsl` includes the native `liblsl` library on Windows and macOS. On Linux,
install `liblsl` separately (your distro's package, or a release from
[sccn/liblsl](https://github.com/sccn/liblsl/releases)).

## 2. Quickstart

Connect as usual and wait for the device to be **ready**
(`on_mudra_device_connected`, not the `connect()` return — see
[SDK_USAGE.md §4](SDK_USAGE.md#4-minimal-end-to-end-example)). Then hand the
device to a `MudraLslBridge`:

```python
import asyncio
from mudra_sdk.lsl import MudraLslBridge

# `device` is a connected MudraDevice (MudraPro or MudraUltimate, BLE or CDC)
async with MudraLslBridge(device, device_id="band0") as bridge:
    print(bridge.streams)
    # {'emg': 'MudraPro-band0-EMG', 'imu_hand': 'MudraPro-band0-IMU_HAND',
    #  'imu_ring': 'MudraPro-band0-IMU_RING', 'ppg': 'MudraPro-band0-PPG'}
    await asyncio.sleep(60)          # the sensors are on and live on LSL
# leaving the block turns the sensors off and closes the streams

await device.disconnect()
```

Open LabRecorder on any machine on the same network, and the streams appear in
its list.

Without `async with`, call `start()` and `stop()` yourself — put `stop()` in a
`finally` block, so the sensors are turned off even on errors (§4):

```python
bridge = MudraLslBridge(device, sensors=["emg", "imu_hand"])
await bridge.start()
try:
    ...
finally:
    await bridge.stop()
    await device.disconnect()
```

| Argument | Default | Meaning |
|---|---|---|
| `device` | — | A connected `MudraDevice`. |
| `device_id` | device serial, else its name | Label in every stream name. Must differ per device when you stream several. |
| `sensors` | all four | Any of `"emg"`, `"imu_hand"`, `"imu_ring"`, `"ppg"` — which sensors to publish **and turn on**. |
| `status_timeout` | `3.0` | Seconds `start()` waits for each sensor's status reply. |

### From the command line

`examples/lsl_app.py` does all of the above with no code: it finds a device,
connects, and publishes its sensors until you press Ctrl-C (run it from the
repo root; the source is `examples/mudra_lsl/cli.py`):

```
python examples/lsl_app.py                                  # first device found, all sensors
python examples/lsl_app.py --transport ble --name 48-25     # a specific BLE device
python examples/lsl_app.py --transport cdc --sensors emg imu_hand --duration 60
python examples/lsl_app.py --emg-odr 3200 --emg-res 24 --device-id band0
python examples/lsl_app.py --list                           # list the devices found, then exit
```

Run `python examples/lsl_app.py --help` for every option. Worth knowing:

- **Devices already connected to the computer are found first.** A band paired
  to a Windows PC is connected by Windows automatically and stops advertising,
  so a scan alone never finds it; the CLI asks `Mudra.get_connected_devices()`
  ([CONNECTION.md §1](CONNECTION.md#1-scanning)) before scanning.
- **Signing in is optional, but it decides the tier**
  ([AUTH.md](AUTH.md)). Without an account the device streams at whatever tier
  it already holds. Pass `--email`/`--password` (or set `MUDRA_EMAIL` /
  `MUDRA_PASSWORD`) and the device gets the account's tier on connect — needed
  for higher ODRs and 24-bit EMG.
- `--emg-odr`, `--emg-res`, `--imu-odr` and `--ppg-odr` are applied after
  connecting and **before** any sensor is turned on, as
  [SENSORS.md §3](SENSORS.md#3-configure-a-sensor-odr-resolution-ranges-etc)
  requires. `--emg-odr` is checked against the connected model's rates.
- The CLI exits with status 1 if the device disconnects while streaming.

## 3. What it publishes

**One stream per sensor.** An LSL stream has one fixed sample rate and channel
count, so the sensors can't share one. Both are read from the device's status
when the bridge starts, never hard-coded:

| Sensor key | Stream name | LSL type | Channels | Units |
|---|---|---|---|---|
| `emg` | `MudraPro-<device_id>-EMG` | `EMG` | `ch0`…`chN` — **3 on Pro, 8 on Ultimate** | normalized (about −1…1) |
| `imu_hand` | `MudraPro-<device_id>-IMU_HAND` | `IMU` | `acc_x acc_y acc_z gyr_x gyr_y gyr_z` | g ×3, dps ×3 |
| `imu_ring` | `MudraPro-<device_id>-IMU_RING` | `IMU` | same as `imu_hand` | g / dps |
| `ppg` | `MudraPro-<device_id>-PPG` | `PPG` | `ch0`…`chN` — 1 to 4, as configured | microvolts |

On a Mudra Ultimate, names start with `MudraUltimate-` instead.

- `imu_hand` and `imu_ring` are what the rest of this SDK calls the hand IMU
  (`H_IMU`) and the finger IMU (`F_IMU`). The stream names match the Mudra Pro
  C++ SDK's LSL streams, so a lab set up for one finds the other's streams
  unchanged.
- **Sample rate** (`nominal_srate`) is the sensor's current ODR. Values are
  `float32`, in the physical units the SDK already delivers
  ([data_format.md](data_format.md)) — the bridge doesn't rescale anything.
- **`source_id`** is `mudra_pro:<serial>:<sensor>` (`mudra_ultimate:…` on
  Ultimate). It stays the same across restarts, which is how a recorder
  reconnects to a stream that went away and came back.
- **Stream description** (the XML LabRecorder saves into the file):
  manufacturer, model, `device_id`, serial, transport, and each channel's
  label, unit and type (`Accelerometer` / `Gyroscope` for the IMU channels).
- **`bridge.streams`** maps each published sensor to its stream name.

A sensor the device doesn't answer for within `status_timeout` is **skipped**
with a warning and listed in `bridge.skipped` — for example `imu_ring` on a band
without a finger IMU. `start()` raises `RuntimeError` only if *no* requested
sensor answers.

## 4. The bridge turns sensors on and off

In this SDK, registering a sensor's `set_on_*_ready` callback **is** what turns
the sensor on, and each sensor has exactly one callback slot
([SENSORS.md §1](SENSORS.md#1-enable--disable-a-sensors-data-stream)). So:

- **`start()` turns on** every sensor it publishes, by registering the
  bridge's own callback for it. Don't turn them on yourself first.
- **`stop()` turns them off.** Nothing else does — not `disconnect()`, and not
  your app exiting
  ([Turning sensors off is the app's job](SENSORS.md#turning-sensors-off-is-the-apps-job)).
  Call `stop()` before disconnecting, or use `async with`.
- **Don't register a published sensor's callback yourself.** It would replace
  the bridge's, and the stream would go silent. To also use the samples in
  your own code (a live chart, a local recorder), read them back from LSL
  with a `pylsl.StreamInlet`, like any other LSL consumer (§3).
- Sensors the bridge doesn't publish are left alone — register your own
  callbacks on those as usual.

The bridge publishes each package right inside its callback: it reorders the
samples into rows (the SDK delivers them channel by channel), timestamps them,
and calls `push_chunk`. That only copies the data into liblsl's send buffer,
so it doesn't hold up the device connection.

## 5. Timestamps — how devices get aligned

Every package the SDK delivers carries `timestamp`: the device's clock reading
(1 MHz, counting from boot) for the package's **first** sample
([data_format.md](data_format.md#timestamp-frequency-and-frequency_std)). It is
precise — taken on the sensor when the data was sampled, before any radio or
USB delay — but it isn't in the host's clock. The bridge converts it with a
`DeviceClockMapper`:

```
r        = arrival time - device time     # per package: clock offset + transport delay
offset   = smallest r of the last 20 s    # delay only adds, so the smallest r is closest to the truth
sample i = device time + offset + i/ODR   # the package's first sample, then 1/ODR apart
```

What that gives you:

- **Stamps follow the device's own sample timing.** BLE and USB deliver
  packages in bursts, with delays that vary by tens of milliseconds; none of
  that jitter reaches the timestamps.
- **A small constant lag.** Stamps are late by the smallest transport delay
  seen (about one BLE connection interval or USB transfer). Every sensor of a
  device shares one mapper, so the lag is the same for all of them and they
  stay aligned with each other.
- **Aligned with every other LSL device.** Stamps are in LSL's clock, so a
  recorder lines Mudra data up with everything else. Across machines, LSL's
  own clock synchronization takes care of the rest.
- **The first second after `start()` is not published.** The first packages
  arrive late, so the offset improves quickly at first; the bridge drops
  packages until it has settled. After that, the offset only changes slowly
  (at most 0.2 ms per second), so timestamps never jump backwards — EMG at
  3200 Hz has only 0.3 ms between samples.
- **After a reboot or reconnect, call `start()` again** (§6). It resets the
  clock conversion, so there's another second of warm-up.

## 6. Changing configuration, and reconnecting

**Changing a sensor's configuration.** A sensor must be off while its ODR,
resolution, or channel count changes
([SENSORS.md §3](SENSORS.md#3-configure-a-sensor-odr-resolution-ranges-etc)),
and a stream's sample rate and channel count are fixed when it's created. So
stop the bridge, change the configuration, and start it again:

```python
from mudra_sdk.models.enums import ProEMGODR

await bridge.stop()                               # turns the sensors off
await device.set_emg_odr(ProEMGODR.emgOdr3200)
await bridge.start()                              # new streams at the new rate
```

`start()` asks the device for each sensor's current status, so the new streams
always match the new configuration. The streams keep their `source_id`, so
LabRecorder picks them back up.

If the channel count changes while the bridge is running anyway, packages stop
fitting the stream: the bridge logs a warning and drops them until you call
`start()` again.

**After a disconnect.** A disconnect clears every per-device callback
([CALLBACKS.md §3](CALLBACKS.md#3-callbacks-dont-survive-a-disconnect)),
including the bridge's, so the streams go silent. Once the device is ready
again (`on_mudra_device_connected`), call `await bridge.start()` — it rebuilds
the streams and turns the sensors back on.

Calling `start()` on a running bridge is always safe: it stops it first, then
starts again.

## 7. Multiple devices

Use one bridge per device, each with its own `device_id` (the default, the
device serial, already differs from band to band). `Mudra` supports several
connected devices at once
([CONNECTION.md §8](CONNECTION.md#8-multiple-devices-at-once)):

```python
async with MudraLslBridge(left, "left"), MudraLslBridge(right, "right"):
    await asyncio.sleep(3600)       # MudraPro-left-EMG, MudraPro-right-EMG, ...
```

## 8. Troubleshooting

- **`ImportError` from `start()`** — `pylsl` isn't installed, or on Linux,
  `liblsl` is missing. See §1.
- **`RuntimeError` from `start()`** — no sensor answered. The device is
  probably not ready yet: start the bridge after `on_mudra_device_connected`.
- **A sensor is missing from `bridge.streams`** — the device didn't report
  that sensor's status; `bridge.skipped` says so. A band without a finger IMU
  never reports `imu_ring`.
- **A stream exists but carries no data** — look for the bridge's warning that
  the device didn't turn the sensor on. The device refused the "turn on"
  command, often because the configuration exceeds its license tier: sign in
  first ([AUTH.md](AUTH.md)), and register `set_on_command_error_received` to
  see the device's reason. Also check that nothing else in your app registered
  that sensor's callback (§4).
- **A "package … doesn't fit N channels" warning** — the channel count changed
  while the bridge was running. Use stop → configure → start (§6).
- **LabRecorder on another machine doesn't see the streams** — LSL finds
  streams by UDP multicast and sends data over TCP; both must get through the
  firewall, on the network interface that reaches the other machine. Try a
  recorder on the same machine first. See
  [troubleshooting.md](troubleshooting.md#lsl-consumers-cant-see-the-streams).

## Related documentation

- Sensor streams and configuration: [SENSORS.md](SENSORS.md) · sample layout
  and units: [data_format.md](data_format.md) · callbacks: [CALLBACKS.md](CALLBACKS.md)
- API reference: [api_reference](api_reference.rst) → "Lab Streaming Layer"
- Usage guide (package layout, architecture): [SDK_USAGE.md](SDK_USAGE.md)
