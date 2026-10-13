# Mudra SDK — Sensors Guide (Enable / Disable / Status / Config)

> Part of the [Mudra SDK usage guide](SDK_USAGE.md). See also:
> [CONNECTION.md](CONNECTION.md) · [CALLBACKS.md](CALLBACKS.md)

Assumes the device is already connected — see
[CONNECTION.md](CONNECTION.md). All examples below run on a connected
`device: MudraDevice`.

All callbacks on this page are plain `def` functions — the SDK calls them
directly without awaiting, so an `async def` callback never runs (see
[CALLBACKS.md](CALLBACKS.md)).

The device has five sensors, each identified consistently across the API:

| Sensor | Description | `FirmwareDataType` | `SensorTypes` |
|---|---|---|---|
| EMG | Electromyography | `emg` | `EMG` |
| H_IMU | Hand IMU (accel + gyro) | `imuH` | `H_IMU` |
| F_IMU | Finger IMU (accel + gyro) | `imuF` | `F_IMU` |
| PPG_H | Hand photoplethysmography (2 channels) | `ppgH` | `PPG_H` |
| PPG_F | Finger (ring) photoplethysmography (2 channels) | `ppgF` | `PPG_F` |

PPG_H and PPG_F are two sensors on **one** PPG chip, split the same way the
hand and finger IMUs are: PPG_H carries the band's two optical channels,
PPG_F the ring's two. Each has its own stream, status, enable/disable and
per-channel settings, but some settings belong to the chip and are shared —
see [§3](#ppg_h-and-ppg_f-share-one-chip). PPG_F needs the ring connected,
like F_IMU.

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

Same shape for the other four sensors:

```python
await device.set_on_imu_h_ready(callback_or_none)
await device.set_on_imu_f_ready(callback_or_none)
await device.set_on_ppg_h_ready(callback_or_none)
await device.set_on_ppg_f_ready(callback_or_none)
```

Callback signature for all five is identical:
`(timestamp: int, samples: list[float], frequency: int, frequency_std: float) -> None`.
(Full callback catalog: [CALLBACKS.md](CALLBACKS.md#21-sensor-streaming-callbacks).)
Register these only after `await device.connect()` has returned — they send
the power command over the live connection.
**`samples` is channel-major (each channel's full run back to back, not
interleaved per-sample), and `frequency` is the package rate, not the
sensor's ODR** — see [data_format.md](data_format.md) before writing any
parsing code against it.

Internally, setting any of these callbacks recomputes "is this data type
needed" (native `is_data_needed`: a ready-callback is registered, **or** an
active PC-side recording — `start_recording(...)`, §6 — includes that
sensor) and only sends the firmware enable/disable command over BLE or the
`<SENSOR>_ON`/`<SENSOR>_OFF` CDC token when that answer changes. So
`set_on_<sensor>_ready(None)` powers the sensor off unless something else
in-process still needs it (e.g. a running `start_recording`), in which case
it stays on until that stops too. You don't send power commands directly.

Each sensor has exactly **one** callback slot — a second `set_on_<sensor>_ready`
call replaces the first, it doesn't add a listener. If a
[`MudraLslBridge`](LSL.md) is publishing a sensor, it already uses that slot:
registering your own callback would replace the bridge's and silence its
stream — read the samples back from LSL instead
([LSL.md §4](LSL.md#4-the-bridge-turns-sensors-on-and-off)).

### Turning sensors off is the app's job

Enabling a sensor powers it on **on the device**, not just in your process.
It keeps running until your app disables it (`set_on_<sensor>_ready(None)`)
or the device is powered off. Nothing else turns it off:

- `device.disconnect()` doesn't turn sensors off. Over CDC it pauses the
  data stream (`STOP`), but the sensors themselves stay on.
- Your app exiting or crashing doesn't turn them off either. For example:
  enable EMG, close the app without disabling it, and EMG keeps running on
  the device, draining its battery with nobody reading the data.
- The next session to connect will find the sensor still on
  (`get_emg_status()` reports `enabled=True`).

So disable every sensor you enabled before you disconnect or exit — in a
`finally` block or shutdown handler, so it also runs on errors:

```python
try:
    await device.set_on_emg_ready(on_emg_data)
    ...  # use the stream
finally:
    await device.set_on_emg_ready(None)   # turn off what you turned on
    await device.disconnect()
```

If the connection drops unexpectedly (out of range, USB unplugged), the
power-off command can't be sent — the sensor stays on until you reconnect
and disable it, or the device is powered off. Note that the SDK starts every
connection assuming all sensors are off, so after reconnecting,
`set_on_emg_ready(None)` on its own sends nothing. To turn off a sensor left
running, toggle it: register a callback (sends power-on), then set `None`
(sends power-off).

## 2. Query / observe sensor status

**One-shot query** — fires the corresponding status callback (below) when
the reply arrives; it's async/fire-and-forget, not a return value:

```python
await device.get_emg_status()
await device.get_h_imu_status()
await device.get_f_imu_status()
await device.get_ppg_h_status()
await device.get_ppg_f_status()
```

**Register a status callback** to receive every status reply — both the
ones you triggered with a `get_*_status()` call and unsolicited pushes the
firmware sends after a config change:

```python
from mudra_sdk.models.mudra_device import EmgStatus, ImuStatus, PpgStatus

def on_emg_status(status: EmgStatus):        # plain def, not async def
    print(status.enabled, status.odr_sps, status.resolution_bits)

await device.set_on_emg_status_received(on_emg_status)
# on_h_imu_status / on_f_imu_status / on_ppg_h_status / on_ppg_f_status are
# your own functions, same shape:
await device.set_on_h_imu_status_received(on_h_imu_status)   # receives ImuStatus
await device.set_on_f_imu_status_received(on_f_imu_status)   # receives ImuStatus
await device.set_on_ppg_h_status_received(on_ppg_h_status)   # receives PpgStatus
await device.set_on_ppg_f_status_received(on_ppg_f_status)   # receives PpgStatus
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
class PpgStatus:              # shared by PPG_H and PPG_F
    enabled: bool             # this sensor's own on/off state
    odr_hz: PPGODR            # chip-wide: PPG_H and PPG_F always report the same ODR
```

**Cached last-known status** (no round trip, may be `None` before the
first reply arrives):

```python
device.get_emg_status_info()    -> Optional[EmgStatus]
device.get_h_imu_status_info()  -> Optional[ImuStatus]
device.get_f_imu_status_info()  -> Optional[ImuStatus]
device.get_ppg_h_status_info()  -> Optional[PpgStatus]
device.get_ppg_f_status_info()  -> Optional[PpgStatus]
```

The SDK sends all five `get_*_status()` queries itself during
`connect()` (BLE: once the COMMAND characteristic is discovered; CDC: from
`on_cdc_ready()`). Over BLE the replies arrive shortly after `connect()`
returns; over CDC they're read back before it returns. Either way
`get_*_status_info()` is usually populated soon after. To see those first
replies in your status callback, register it **before** calling
`connect()` (status callbacks don't need a live connection, and stay
registered until the next disconnect) or from `on_mudra_device_connected`.
The streaming setters (`set_on_*_ready`, §1) are different — call those only
after `connect()` returns.

## 3. Configure a sensor (ODR, resolution, ranges, etc.)

> **Important — disable the sensor before changing its configuration.**
> `set_emg_odr`/`set_emg_res`/`set_h_imu_odr`/`set_ppg_h_odr`/etc. just send the
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
> Same pattern for H_IMU/F_IMU/PPG_H/PPG_F — for PPG, disable **both** PPG
> sensors first (see below). Skipping the disable step risks a
> rejected command, a corrupted/mismatched data stream, or firmware-side
> undefined behavior depending on sensor and transport.

Every config parameter follows the same `set_x` / `get_x` pair, and both
return `None`. **Replies to the individual parameter GETs (`get_emg_odr()`,
`get_h_imu_acc()`, `get_ppg_h_dec()`, …) currently reach no callback** — they
only show up in the SDK's debug log. To read the current configuration, call
`get_<sensor>_status()` and use the status callback or the cached
`get_<sensor>_status_info()` (§2), which report ODR, resolution and ranges.
A rejected SET or GET still arrives via the command-error callback (below).

```python
from mudra_sdk.models.enums import ProEMGODR, EmgRes, IMUODR, PPGODR
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

await device.set_ppg_h_odr(PPGODR.ppgOdr100)     # chip-wide: PPG_F follows
await device.set_ppg_h_dec(4)                     # decimation factor, chip-wide
await device.set_ppg_h_prpct(1280)                # pulse-repetition period code, chip-wide
await device.set_ppg_h_led(ch=0, drv1=10, drv2=10)
await device.set_ppg_h_tia(ch=0, rf=1, cf=1)
await device.set_ppg_h_src(ch=0, led=1, pd=1)
await device.ppg_h_clear()
# ...set_ppg_f_* / get_ppg_f_* / ppg_f_clear are identical, for the ring's channels
```

### PPG_H and PPG_F share one chip

- **ODR, decimation (`dec`) and PRPCT are chip-wide.** Setting one through
  either sensor (`set_ppg_h_odr` or `set_ppg_f_odr`) changes it for both,
  and both sensors' status reports the new ODR.
- **LED, TIA and SRC are per channel** and take the sensor's own channel
  number, `ch=0` or `ch=1`, on both sensors — not the chip's 0–3. Anything
  else raises `ValueError` before anything is sent.
- **`ppg_h_clear()` / `ppg_f_clear()`** drop that sensor's two channels'
  LED/TIA/SRC overrides, plus the shared PRPCT override.
- **Config changes are rejected while either PPG sensor is streaming** —
  disable both before changing any PPG setting, on either sensor.
- **PPG_F needs the ring.** Without it, enabling PPG_F or changing a PPG_F
  per-channel setting is rejected with `BtCmdStatus.ERR_STATE` (via the
  command-error callback below), and so is `get_ppg_f_status()` — no
  `PpgStatus` arrives. That is exactly how F_IMU reports a missing ring (the
  device checks the same ring for both). If the ring is unplugged while PPG_F
  is on, PPG_F stays enabled but its callback stops firing until the ring is
  back.

**Errors on any of the above** (a rejected SET, an invalid value, etc.)
arrive via one callback regardless of which sensor or transport:

```python
from mudra_sdk.models.enums import BtCmdId, BtCmdStatus

def on_command_error(cmd_id: BtCmdId, status: BtCmdStatus):   # plain def
    print(f"{cmd_id.description} failed: {status.description} (0x{status.value_int:02X})")

await device.set_on_command_error_received(on_command_error)
```

Over CDC, the firmware itself rejects a config change on a running sensor;
that arrives here as `BtCmdStatus.ERR_BUSY` (see
[CALLBACKS.md §2.4](CALLBACKS.md#24-errors) for how CDC error replies map to
status codes).

## 4. Packet-loss test mode

Both models. A firmware-side overlay, per sensor, that replaces one channel
with an incrementing counter so loss can be measured without inspecting real
data. On Mudra Ultimate it needs firmware newer than 1.0.3.8, which doesn't
have these commands and rejects them:

```python
await device.set_emg_test_mode(True)    # also: set_h_imu_test_mode / set_f_imu_test_mode /
                                        #       set_ppg_h_test_mode / set_ppg_f_test_mode
seen, lost = device.get_emg_packet_loss_stats()      # lifetime counters (also *_h_imu_*, *_ppg_h_*, ...)
pct = device.sample_emg_packet_loss()                 # windowed (~1s) loss %, call periodically
hz = device.get_emg_packet_loss_rate_hz()
device.reset_emg_packet_loss_window()
await device.set_emg_test_mode(False)   # turn it off again
```

Test mode is one combined firmware command on both BLE and CDC: turning it
on also starts the sensor, and `set_emg_test_mode(False)` stops the sensor
again.

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

The device needs a 16-byte `user_id` before it will start a recording. If
you were signed in when the device connected, the SDK already sent it (see
[AUTH.md](AUTH.md#user_id-provisioning-sd-card-recording)); otherwise call
`set_user_id(...)` yourself with exactly 16 bytes:

```python
import time

# Register callbacks first, so no reply is missed.
await device.set_on_storage_record_state_received(lambda status: ...)   # RecordStatus
await device.set_on_storage_record_error_received(lambda status: ...)   # BtCmdStatus
await device.set_on_storage_next_file_num_received(lambda file_num: ...)  # int

await device.get_storage_record_state()      # -> RecordStatus via callback
await device.get_storage_next_file_num()     # -> int via callback

# Only needed if the SDK didn't already send it at connect (signed out):
await device.set_user_id(user_id)            # `user_id`: bytes, exactly 16 (else ValueError)
await device.set_storage_record(
    emg=True, ppg_h=False, imu_h=True, imu_f=False, ppg_f=False,
    file_num=3, duration_min=0, utc_ts=int(time.time()),
    description="session notes", is_test=False,
)
```

The five sensor flags may be passed positionally, in this order (`emg`,
`ppg_h`, `imu_h`, `imu_f`, `ppg_f`); everything after them is keyword-only,
and a flag that isn't a bool (or 0/1) raises `TypeError`.

`duration_min` (default 0) records until an explicit stop call; any other
value (1-65535) arms a one-shot firmware timer that automatically stops the
session after that many minutes — indistinguishable from calling
`set_storage_record(False, False, False, False, False, file_num=file_num)` yourself: same
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
- **Expecting a return value from a `get_*`/`set_*` call** — they all
  return `None`. Status, storage and device-info replies come back
  asynchronously through a registered callback (register it *before*
  triggering the request so you don't miss it); replies to individual
  parameter GETs (`get_emg_odr()`, `get_h_imu_acc()`, …) reach no callback at
  all — read config from the status callback / `get_*_status_info()` instead
  (§3).
- **Writing callbacks as `async def`** — the SDK calls callbacks without
  awaiting them, so an `async def` callback never runs. Use plain `def`.
- **Forgetting `None` disables streaming** — `set_on_emg_ready(None)` (and
  the IMU/PPG equivalents) is the disable call, not just "clear my
  callback"; it actually sends the power-off command (unless an active
  `start_recording` still needs that sensor).
- **Leaving a sensor on when the app closes** — neither `disconnect()` nor
  exiting the app turns sensors off; they keep running until you disable
  them or the device is powered off. See
  [Turning sensors off is the app's job](#turning-sensors-off-is-the-apps-job).
- **SD recording is BLE-only** — see §5 above.
- **Treating PPG settings as per-sensor** — ODR, decimation and PRPCT are
  shared by PPG_H and PPG_F, and PPG channel numbers are each sensor's own
  0–1 (PPG_F's `ch=0` is the ring's first channel). See
  [§3](#ppg_h-and-ppg_f-share-one-chip).
