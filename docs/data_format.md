# Data format

What's actually inside the `samples: list[float]` argument delivered to
`set_on_emg_ready`/`set_on_imu_h_ready`/`set_on_imu_f_ready`/`set_on_ppg_ready`
callbacks ([SENSORS.md §1](SENSORS.md#1-enable--disable-a-sensors-data-stream)) —
sourced directly from the native parser
([`mudra_sdk/core/Computation/CommonTypes.h`](../mudra_sdk/core/Computation/CommonTypes.h),
[`computation_wrapper.cpp`](../mudra_sdk/core/computation_wrapper.cpp)).

## `samples` is channel-major, not interleaved

Each callback fires once per decoded package (one BLE notification / one CDC
DATA read), carrying **every channel's samples from that package back to
back** — channel 0's whole run, then channel 1's whole run, and so on. It is
**not** interleaved per-sample (`ch0, ch1, ch2, ch0, ch1, ch2, ...`).

```
samples = [ch0_s0, ch0_s1, ..., ch0_sN-1,   # channel 0's samples
           ch1_s0, ch1_s1, ..., ch1_sN-1,   # channel 1's samples
           ...]
```

`len(samples)` is always a multiple of the channel count for that sensor —
divide evenly to recover each channel's run:

```python
def split_channels(samples: list[float], channel_count: int) -> list[list[float]]:
    n = len(samples) // channel_count
    return [samples[ch * n:(ch + 1) * n] for ch in range(channel_count)]
```

## Channel count and order per sensor

| Sensor | Channel count | Order |
|---|---|---|
| EMG | 3 (Mudra Pro) / 8 (Mudra Ultimate) — `device.EMG_CHANNEL_COUNT` | `ch0, ch1, ..., chN-1` |
| Hand IMU / Finger IMU | Always 6 | `ax, ay, az, gx, gy, gz` (accel then gyro) |
| PPG | 1–4 — `PpgStatus.channel_count` | `ch0, ch1, ..., chN-1` |

## Units — already scaled, not raw ADC counts

The native parser scales every sample before it reaches the callback — you
never see raw ADC/register counts:

- **EMG** — scaled to **~[-1, 1]** using the active resolution's reported
  full-scale value (`emg_res_max` — see `get_emg_res_max()` in
  [SENSORS.md §3](SENSORS.md#3-configure-a-sensor-odr-resolution-ranges-etc)).
- **IMU (hand + finger)** — accelerometer channels in **g**, gyroscope
  channels in **dps**, scaled using the *currently configured* accel/gyro
  range (`IMUAccRange`/`IMUGyrRange` — see `ImuStatus`). Since range is
  runtime-configurable, read it back rather than assuming the boot default.
- **PPG** — scaled to **microvolts (µV)** via a fixed AFE4950 count→µV
  factor.

## Timestamp, frequency, and frequency_std

The other three callback arguments, per package (not per individual sample):

- **`timestamp`** — the package's last-sample device clock reading
  (`ts_cyc`, GRTC-backed, 64-bit, no rollover). A device clock value, not a
  host wall-clock time — don't compare it directly against
  `time.time()`/`time.perf_counter()`.
- **`frequency`** — **packages per second** observed over roughly the last
  1 second. This is **not the sensor's configured ODR**
  (`ProEMGODR`/`IMUODR`/`PPGODR`) — one package typically bundles multiple
  samples per channel, so package rate and per-channel sample rate are
  different numbers. Read the actual ODR from the sensor's status callback
  ([SENSORS.md §2](SENSORS.md#2-query--observe-sensor-status)) instead.
- **`frequency_std`** — standard deviation of that recent package-rate
  history; a rough jitter indicator, not a per-sample error bound.

## See also

- [SENSORS.md](SENSORS.md) — enabling streams, status/config, packet-loss test mode.
- [supported_devices.md](supported_devices.md) — per-model channel counts and config ranges.
