# Mudra SDK — Callbacks Reference

> Part of the [Mudra SDK usage guide](SDK_USAGE.md). See also:
> [CONNECTION.md](CONNECTION.md) · [SENSORS.md](SENSORS.md)

The SDK has exactly two kinds of callback:

1. **The global `MudraDelegate`** (§1) — one instance for the whole
   process, registered once via `Mudra().set_delegate(...)`. Reports device
   discovery and connection lifecycle for *every* device.
2. **Per-device `set_on_*` callbacks** (§2) — registered on a specific
   `MudraDevice` after it's connected. Reports sensor data, status,
   storage, errors, and ping for *that* device only.

Every per-device setter is `async` and fire-and-forget — `await
device.set_on_x(fn)` just stores `fn`; it doesn't itself trigger anything
(except the sensor-streaming setters in §2.1, where setting the callback
*is* the enable/disable action — see [SENSORS.md](SENSORS.md#1-enable--disable-a-sensors-data-stream)).
Pass `None` to unregister.

## 1. `MudraDelegate` (global, one per process)

```python
from mudra_sdk.models.callbacks import MudraDelegate
from mudra_sdk.models.mudra_device import MudraDevice

class MyDelegate(MudraDelegate):
    def on_device_discovered(self, device: MudraDevice): ...
    def on_mudra_device_connecting(self, device: MudraDevice): ...
    def on_mudra_device_connected(self, device: MudraDevice): ...
    def on_mudra_device_disconnecting(self, device: MudraDevice): ...
    def on_mudra_device_disconnected(self, device: MudraDevice): ...
    def on_mudra_device_connection_failed(self, device: MudraDevice, error: str): ...
    def on_bluetooth_state_changed(self, state: bool): ...

Mudra().set_delegate(MyDelegate())
```

All seven methods are abstract — you must implement every one (it's an
ABC). The example app's [`delegate.py`](../examples/mudra_connect/delegate.py)
is a good template.

| Method | Fires when |
|---|---|
| `on_device_discovered(device)` | A new device (BLE or CDC) is found by `scan_ble()`/`scan_cdc()` or returned by `get_connected_devices()`. Fires once per address. |
| `on_mudra_device_connecting(device)` | Right after `device.connect()` is called, before the transport handshake starts. |
| `on_mudra_device_connected(device)` | Transport connected **and** SDK-internal readiness steps finished (BLE: characteristics discovered; CDC: status queried + `START` sent). See the ordering note in [SDK_USAGE.md](SDK_USAGE.md#4-minimal-end-to-end-example). |
| `on_mudra_device_connecting` / `on_mudra_device_disconnecting(device)` | Right after `device.disconnect()` is called, before teardown. |
| `on_mudra_device_disconnected(device)` | Teardown complete — for either a caller-initiated disconnect **or** an unexpected drop (BLE radio loss, USB unplug). No separate callback for "lost connection" vs. "I disconnected it." |
| `on_mudra_device_connection_failed(device, error)` | `connect()` failed; `error` is a human-readable message. |
| `on_bluetooth_state_changed(state)` | The host's Bluetooth adapter turned on/off (`state: bool`). BLE-related only; unaffected by CDC devices. |

This is a **single global delegate for all devices** — every callback
receives the specific `device` it's about, so multi-device apps dispatch on
`device.address` (or `device is my_device`) inside these methods rather
than registering one delegate per device.

## 2. Per-device callbacks

Registered on a connected `device: MudraDevice` via `await
device.set_on_<name>(callback_or_none)`.

### 2.1 Sensor streaming callbacks

Enabling the sensor's data stream *is* setting one of these (see
[SENSORS.md §1](SENSORS.md#1-enable--disable-a-sensors-data-stream)):

| Setter | Callback signature |
|---|---|
| `set_on_emg_ready` | `(timestamp: int, samples: list[float], frequency: int, frequency_std: float) -> None` |
| `set_on_imu_h_ready` | same signature |
| `set_on_imu_f_ready` | same signature |
| `set_on_ppg_ready` | same signature |

### 2.2 Sensor status callbacks

Fired on reply to `get_<sensor>_status()` and on unsolicited firmware
pushes after a config change (see [SENSORS.md §2](SENSORS.md#2-query--observe-sensor-status)):

| Setter | Callback argument |
|---|---|
| `set_on_emg_status_received` | `EmgStatus` |
| `set_on_h_imu_status_received` | `ImuStatus` |
| `set_on_f_imu_status_received` | `ImuStatus` |
| `set_on_ppg_status_received` | `PpgStatus` |

### 2.3 Storage / SD recording callbacks (BLE only)

See [SENSORS.md §5](SENSORS.md#5-sd-card-recording-ble-only).

| Setter | Callback argument |
|---|---|
| `set_on_storage_record_state_received` | `RecordStatus` |
| `set_on_storage_record_error_received` | `BtCmdStatus` |
| `set_on_storage_next_file_num_received` | `int` (next free file number) |

### 2.3b Licensing (BLE + CDC)

See [CONNECTION.md §5](CONNECTION.md#5-licensing--account-sign-in).

| Setter | Callback argument |
|---|---|
| `set_on_license_device_info_received` | `LicenseDeviceInfo` |

### 2.4 Errors

| Setter | Callback argument | Fires on |
|---|---|---|
| `set_on_command_error_received` | `(cmd_id: BtCmdId, status: BtCmdStatus)` | Any non-OK status-only reply — failed enable/disable, failed SET, `RECORD_SET` rejected, etc. Also fires for async `STORAGE_RECORD_ERROR` pushes. |

### 2.5 Connectivity / device state

| Setter | Callback argument | Fires on |
|---|---|---|
| `set_on_ping_response` | *(no arguments)* | Reply to `device.ping()` — see [CONNECTION.md §3](CONNECTION.md#3-ping--round-trip-check). |
| `set_on_charging_state_changed` | `is_charging: bool` | BLE: GATT notification on the battery power-state characteristic. CDC: `MudraDevice` polls `BAT_CHG?` at connect and every 30 s (no push exists on that transport) and feeds the reply through this same callback. |
| `set_on_battery_level_changed` | `level: int` | BLE: GATT notification on the battery characteristic. CDC: polled via `BAT_SOC?` alongside `set_on_charging_state_changed` above. |

### 2.6 Checking whether a callback is currently registered

Every setter above has a matching `is_on_<name>_callback_set() -> bool`
getter, e.g.:

```python
device.is_on_emg_ready_callback_set()
device.is_on_ppg_status_received_callback_set()
device.is_on_command_error_received_callback_set()
```

Useful for UI code that needs to reflect current state (e.g. an
Enable/Disable toggle button) without keeping its own shadow copy of what
was registered.

## 3. Callbacks don't survive a disconnect

`device.disconnect()` (and an unexpected drop) clears **most** per-device
callbacks automatically — `handle_disconnection()` resets:

- All four streaming callbacks (§2.1)
- All four status callbacks (§2.2)
- All three storage callbacks (§2.3)
- The command-error callback (§2.4)
- The ping-response callback (§2.5)

**Not** cleared: `set_on_charging_state_changed` and
`set_on_battery_level_changed` — those two persist across a
disconnect/reconnect cycle.

Practical effect: if you reconnect the same `MudraDevice` object after a
disconnect, re-register every callback in §2.1–§2.4 and the ping callback
— don't assume they're still wired up from before. Charging/battery
callbacks are the one exception and don't need re-registering.
