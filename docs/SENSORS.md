# Mudra SDK — Sensors Guide (Enable / Disable / Status / Config)

> Part of the [Mudra SDK usage guide](SDK_USAGE.md). See also:
> [CONNECTION.md](CONNECTION.md) · [CALLBACKS.md](CALLBACKS.md)

Assumes the device is already connected — see
[CONNECTION.md](CONNECTION.md). All examples below run on a connected
`device: MudraDevice`.

The device has four sensors, each identified consistently across the API:

| Sensor | Description | `FirmwareDataType` | `SensorTypes` |
|---|---|---|---|
| EMG | Electromyography | `emg` | `EMG` |
| H_IMU | Hand IMU (accel + gyro) | `imuH` | `H_IMU` |
| F_IMU | Finger IMU (accel + gyro) | `imuF` | `F_IMU` |
| PPG | Photoplethysmography | `ppg` | `PPG` |

There are **two independent axes** for each sensor — don't conflate them:

1. **Streaming data** (`set_on_<sensor>_ready`) — registering a callback
   *is* the enable/disable action; the sensor is powered on the wire the
   moment you set a non-`None` callback, and powered off when you set
   `None`. There is no separate "enable" call.
2. **Status / configuration** (`get_<sensor>_status`,
   `set_on_<sensor>_status_received`) — a point-in-time or pushed report of
   whether the sensor is on, and at what ODR/resolution/range. Purely
   informational; doesn't turn anything on or off by itself.

## 1. Enable / disable a sensor's data stream

```python
def on_emg_data(timestamp: int, samples: list[float], frequency: int, frequency_std: float):
    ...  # samples is one decoded block of EMG values, already parsed by the native lib

await device.set_on_emg_ready(on_emg_data)   # ENABLE EMG — sends the firmware power-on command
await device.set_on_emg_ready(None)          # DISABLE EMG — sends power-off, drops the callback
```

Same shape for the other three sensors:

```python
await device.set_on_imu_h_ready(callback_or_none)
await device.set_on_imu_f_ready(callback_or_none)
await device.set_on_ppg_ready(callback_or_none)
```

Callback signature for all four is identical:
`(timestamp: int, samples: list[float], frequency: int, frequency_std: float) -> None`.
(Full callback catalog: [CALLBACKS.md](CALLBACKS.md#sensor-streaming-callbacks).)
**`samples` is channel-major (each channel's full run back to back, not
interleaved per-sample), and `frequency` is the package rate, not the
sensor's ODR** — see [data_format.md](data_format.md) before writing any
parsing code against it.

Internally, setting any of these callbacks recomputes "is this data type
needed" (native `is_data_needed`, which accounts for anyone else in-process
still wanting that stream) and only then sends the firmware enable/disable
command over BLE or the `<SENSOR>_ON`/`<SENSOR>_OFF` CDC token — you don't
send power commands directly.

## 2. Query / observe sensor status

**One-shot query** — fires the corresponding status callback (below) when
the reply arrives; it's async/fire-and-forget, not a return value:

```python
await device.get_emg_status()
await device.get_h_imu_status()
await device.get_f_imu_status()
await device.get_ppg_status()
```

**Register a status callback** to receive every status reply — both the
ones you triggered with a `get_*_status()` call and unsolicited pushes the
firmware sends after a config change:

```python
from mudra_sdk.models.mudra_device import EmgStatus, ImuStatus, PpgStatus

async def on_emg_status(status: EmgStatus):
    print(status.enabled, status.odr_sps, status.resolution_bits)

await device.set_on_emg_status_received(on_emg_status)
await device.set_on_h_imu_status_received(on_h_imu_status)   # ImuStatus
await device.set_on_f_imu_status_received(on_f_imu_status)   # ImuStatus
await device.set_on_ppg_status_received(on_ppg_status)       # PpgStatus
```

Status dataclasses (`mudra_sdk.models.mudra_device`):

```python
@dataclass
class EmgStatus:
    enabled: bool
    odr_sps: ProEMGODR       # or UltimateEMGODR on MudraUltimate (different AFE, different rates)
                             # e.g. ProEMGODR.emgOdr3200 -> .value_int == 3200
    resolution_bits: EmgRes  # EmgRes.emgRes16 / emgRes24 -> .bits

@dataclass
class ImuStatus:              # shared by H_IMU and F_IMU
    enabled: bool
    odr_hz: IMUODR
    accel_range_g: IMUAccRange
    gyro_range_dps: IMUGyrRange

@dataclass
class PpgStatus:
    enabled: bool
    odr_hz: PPGODR
    channel_count: PPGChannelCount
```

**Cached last-known status** (no round trip, may be `None` before the
first reply arrives):

```python
device.get_emg_status_info()    -> Optional[EmgStatus]
device.get_h_imu_status_info()  -> Optional[ImuStatus]
device.get_f_imu_status_info()  -> Optional[ImuStatus]
device.get_ppg_status_info()    -> Optional[PpgStatus]
```

The SDK auto-fires all four `get_*_status()` calls right after connecting
(BLE: from `on_characteristic_discovered`; CDC: from `on_cdc_ready()`), so
`get_*_status_info()` is usually already populated shortly after
`on_mudra_device_connected` fires — register your status callback *before*
that if you don't want to miss the first push.

## 3. Configure a sensor (ODR, resolution, ranges, etc.)

> **Important — disable the sensor before changing its configuration.**
> `set_emg_odr`/`set_emg_res`/`set_h_imu_odr`/`set_ppg_odr`/etc. just send the
> config command over the wire — they do **not** check whether the sensor is
> currently streaming, and the firmware does not stop it for you. If a
> sensor is enabled when you send an ODR/resolution/range change, do it
> yourself:
>
> ```python
> was_enabled = device.get_emg_status_info() and device.get_emg_status_info().enabled
> if was_enabled:
>     await device.set_on_emg_ready(None)          # 1. disable first
> await device.set_emg_odr(ProEMGODR.emgOdr3200)    # 2. change config
> if was_enabled:
>     await device.set_on_emg_ready(on_emg_data)    # 3. re-enable
> ```
>
> Same pattern for H_IMU/F_IMU/PPG. Skipping the disable step risks a
> rejected command, a corrupted/mismatched data stream, or firmware-side
> undefined behavior depending on sensor and transport.

Every config parameter follows the same `set_x` / `get_x` pair; `get_x` is
fire-and-forget the same way `get_*_status` is — read the reply via the
corresponding status callback or the command-error callback (on failure),
not a return value.

```python
from mudra_sdk.models.enums import ProEMGODR, EmgRes, IMUODR
# On a MudraUltimate, use UltimateEMGODR instead — different AFE (ADS1298 vs
# Pro's ADS1293), different discrete rate set (500/1000/2000/4000 Hz).

await device.set_emg_odr(ProEMGODR.emgOdr3200)   # samples/sec
await device.get_emg_odr()
await device.set_emg_res(EmgRes.emgRes24)     # bit depth
await device.get_emg_res()
await device.get_emg_res_max()                 # read-only, max post-process value

await device.set_h_imu_odr(IMUODR.imuHOdr200)
await device.set_h_imu_acc(4)                   # accel range, g — IMUAccRange values: 2/4/8/16
await device.set_h_imu_gyr(500)                 # gyro range, dps — IMUGyrRange: 125/250/500/1000/2000
await device.set_h_imu_acc_bw(2)                # bandwidth divisor
await device.set_h_imu_acc_avg(4)               # averaging samples
# ...get_h_imu_* mirrors each set_h_imu_*; f_imu_* is identical, just for the finger IMU

await device.set_ppg_odr(PPGODR.ppgOdr100)
await device.set_ppg_dec(4)                     # decimation factor
await device.set_ppg_led(ch=0, drv1=10, drv2=10)
await device.set_ppg_tia(ch=0, rf=1, cf=1)
await device.set_ppg_src(ch=0, led=1, pd=1)
await device.ppg_clear()
```

**Errors on any of the above** (a rejected SET, an invalid value, etc.)
arrive via one callback regardless of which sensor or transport:

```python
from mudra_sdk.models.enums import BtCmdId, BtCmdStatus

async def on_command_error(cmd_id: BtCmdId, status: BtCmdStatus):
    print(f"{cmd_id.description} failed: {status.description} (0x{status.value_int:02X})")

await device.set_on_command_error_received(on_command_error)
```

## 4. Packet-loss test mode

A firmware-side overlay, per sensor, that replaces one channel with an
incrementing counter so loss can be measured without inspecting real data:

```python
await device.set_emg_test_mode(True)    # also: set_h_imu_test_mode / set_f_imu_test_mode / set_ppg_test_mode
seen, lost = device.get_emg_packet_loss_stats()      # lifetime counters
pct = device.sample_emg_packet_loss()                 # windowed (~1s) loss %, call periodically
hz = device.get_emg_packet_loss_rate_hz()
device.reset_emg_packet_loss_window()
```

On CDC, test mode only arms the software counter-substitution — it does
**not** power the sensor on by itself (BLE combines both into one firmware
command). Make sure the sensor is separately enabled over CDC for the
counter to actually appear in the data stream.

## 5. SD card recording (**BLE only**)

Starts/stops the device's own on-board recording to a `/SD:/REC_<n>/`
session folder of size-capped binary part files, `MREC`-tagged, **not**
CSV. Not available over CDC — every call below on a CDC
device immediately reports `BtCmdStatus.ERR_UNKNOWN` via the command-error
callback instead of sending anything.

Requires the device's **PRO** license tier — on FREE/PLUS a start is
rejected with `BtCmdStatus.ERR_LICENSE` (via the command-error callback)
without touching any sensor. See [§5 of CONNECTION.md](CONNECTION.md#5-licensing--account-sign-in)
for provisioning a tier.

Before starting a recording, send a 16-byte `user_id`:

```python
await device.set_user_id(16_bytes)   # BT_SYS_USER_ID_SET -- required before recording
await device.set_storage_record(
    emg=True, ppg=False, imu_h=True, imu_f=False,
    file_num=3, duration_min=0, utc_ts=int(time.time()),
    description="session notes", is_test=False,
)
await device.get_storage_record_state()      # -> RecordStatus via callback
await device.get_storage_next_file_num()     # -> int via callback

await device.set_on_storage_record_state_received(lambda status: ...)   # RecordStatus
await device.set_on_storage_record_error_received(lambda status: ...)   # BtCmdStatus
await device.set_on_storage_next_file_num_received(lambda file_num: ...)  # int
```

`duration_min` (default 0) records until an explicit stop call; any other
value (1-65535) arms a one-shot firmware timer that automatically stops the
session after that many minutes — indistinguishable from calling
`set_storage_record(False, False, False, False, file_num)` yourself: same
sensor teardown, same `BT_STORAGE_RECORD_STATE` push with `active=False` via
the state callback above. Ignored when stopping. An earlier stop (manual,
disconnect, or a write-failure abort) cancels the pending timer — nothing
renews it mid-session.

`utc_ts` (default 0 = not supplied) is your wall-clock time in Unix epoch
seconds at session start (e.g. `int(time.time())`) — the device has no
independent RTC, so this is the only source of a real-world timestamp. When
non-zero, the firmware writes it into the recording's second (auto-generated
summary) text line as `UTC=<ts>`, ahead of the sensor/ODR summary, and uses
it for nothing else — it does not set the device's trusted clock (that's
`apply_license()`'s job, via the token's `issued_at`; see
[CONNECTION.md §5](CONNECTION.md#5-licensing--account-sign-in)). Ignored
when stopping.

`set_storage_record()` fails with `BtCmdStatus.ERR_STATE` (via the
command-error callback) if `set_user_id` was never called.

`is_test=True` arms packet-loss test mode on each newly-started sensor
before recording begins, so the recording captures the counter stream
instead of real data — inspect the counter
channel for gaps, for offline packet-loss analysis with no live link needed.

Unlike storage/SD commands, `set_user_id` also works over CDC (`USER_ID <hex>`).

## 6. Sensor pitfalls

- **Changing config on a live sensor** — `set_*_odr`/`set_*_res`/range calls
  don't disable the sensor for you; see §3 above. Disable
  (`set_on_*_ready(None)`), change config, then re-enable if it was running.
- **Expecting a return value from a `get_*`/`set_*` call** — nearly
  everything here is fire-and-forget; the reply comes back asynchronously
  through a registered callback, not the coroutine's return value.
  Register the callback *before* triggering the request if you need to be
  sure not to miss it.
- **Forgetting `None` disables streaming** — `set_on_emg_ready(None)` (and
  the IMU/PPG equivalents) is the disable call, not just "clear my
  callback"; it actually sends the power-off command.
- **CDC test mode doesn't power the sensor on** — see §4 above; enable the
  sensor separately.
- **SD recording is BLE-only** — see §5 above.
