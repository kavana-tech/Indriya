# Mudra SDK — Connection Guide (Scan, BLE, CDC)

> Part of the [Mudra SDK usage guide](SDK_USAGE.md). See also:
> [SENSORS.md](SENSORS.md) · [CALLBACKS.md](CALLBACKS.md)

Covers finding a device (§1), connecting/disconnecting over either transport
(§2), the round-trip ping check (§3), sending raw commands (§4),
licensing/account sign-in (§5), firmware update (§6), connection-specific
pitfalls (§7), and connecting to more than one device at once (§8).

Assumes you already have a `Mudra()` singleton and a registered
`MudraDelegate` — see [SDK_USAGE.md](SDK_USAGE.md#3-core-architecture) for
setup and [CALLBACKS.md](CALLBACKS.md) for the full delegate reference.

## 1. Scanning

BLE and CDC scanning are started and stopped independently — call whichever
transport(s) you actually need:

```python
mudra = Mudra()
await mudra.scan_ble()        # BleService.scan(), non-blocking
await mudra.scan_cdc()        # CdcService.scan(), non-blocking
...
await mudra.stop_scan_ble()
await mudra.stop_scan_cdc()
```

- `Mudra.scan_ble()` fires `BleService.scan()` (continuous `BleakScanner`,
  keeps advertisements whose name contains `"Mudra Pro"` or
  `"Mudra Ultimate"` — that name also picks the model).
  `Mudra.scan_cdc()` fires `CdcService.scan()` (polls
  `serial.tools.list_ports` every 2s for USB VID/PID `0x2FE3`/`0x0001` —
  shared by both models — probing each candidate COM port with a `CDC?`
  handshake to tell the `CONFIG` and `DATA` ports apart, then a `TSYNC?`
  probe to tell Pro from Ultimate). A CDC device's `address` is its USB
  serial number (or a port name, if the device reports no serial number). Run both concurrently if you want devices from either
  transport — they report through the same delegate callback either way.
- Each discovered device — BLE or CDC — triggers one call to
  `MudraDelegate.on_device_discovered(device: MudraDevice)` per address per
  scan session; repeats within a session are de-duplicated internally. The
  same address can be reported again when you restart a scan, when a CDC
  device's port info changes (e.g. its `DATA` port finishes enumerating), or
  by `get_connected_devices()` — you get the **same** `MudraDevice` object
  each time, so de-duplicate on the object or `device.address` if that
  matters to you.
- The same physical device seen over BLE **and** USB is two separate
  `MudraDevice` objects (BLE address vs. USB serial number), each with its own
  connection. Firmware update needs the CDC one (§6).
- Each transport's scan keeps running until you call its own
  `stop_scan_ble()`/`stop_scan_cdc()`; it does not auto-stop after finding a
  device, and stopping one transport's scan has no effect on the other's.
- To find devices that are **already connected** (e.g. a previous process
  left a BLE connection open), use:

  ```python
  devices = await mudra.get_connected_devices()
  ```

  This also fires `on_device_discovered` for each one, same as scan. A BLE
  device found this way still needs `await device.connect()` in this process
  before you can use it (the CDC devices it returns are just the ones this
  process already has open).

## 2. Connecting / disconnecting (BLE and CDC)

Both directions work identically regardless of transport — call it either
on the device or through `Mudra()`; they're equivalent:

```python
await device.connect()      # == await Mudra().connect(device); never raises
await device.disconnect()   # == await Mudra().disconnect(device)
is_up = await Mudra().is_connected(device)
```

`connect()` doesn't raise on failure — the failure arrives via
`MudraDelegate.on_mudra_device_connection_failed`, so check
`await Mudra().is_connected(device)` after it returns. When it returns with
the device connected, the SDK's connect sequence (below) is done and you can
enable sensors.

**What "connect" does, per transport:**

| | BLE | CDC (USB serial) |
|---|---|---|
| Underlying call | `BleakClient.connect()` + GATT service/characteristic discovery, subscribes to notifications | Opens the `CONFIG` serial port, handshakes with `CDC?`, opens+handshakes the `DATA` port, starts a background reader thread |
| Setup before `connect()` returns | Once the COMMAND characteristic is found, the SDK sends the initial sensor-status, license and `user_id` queries/provisioning | `device.on_cdc_ready()` (queries EMG/H_IMU/F_IMU/PPG_H/PPG_F status and battery, starts license/`user_id` provisioning) **then** `device.start_streaming()` (sends `START`) — CDC's DATA port is silent until this |
| `on_mudra_device_connected` fires | As soon as the link is up — before notifications are subscribed | As soon as both ports are open — before the status queries and `START` |
| Data delivery | GATT notifications on the DATA characteristic | Background thread reading the DATA serial port |
| Disconnect | Unsubscribes/`BleakClient.disconnect()` | Sends `STOP`, closes both serial ports, joins reader thread |

You normally don't need to think about any of this — it's handled inside
`connect()`/`disconnect()`. It matters mainly for understanding *when*
sensor data starts flowing (CDC needs the explicit `START`, which the SDK
sends for you before `connect()` returns). Over BLE, the *replies* to the
initial queries arrive asynchronously after `connect()` returns; over CDC
they're read back before it returns — so register status callbacks before
calling `connect()` if you want to see them (see
[CALLBACKS.md §2](CALLBACKS.md#2-per-device-callbacks)).

**Unexpected disconnects** (BLE radio drop, USB unplug) are detected by the
transport and reported through the same
`MudraDelegate.on_mudra_device_disconnected` callback — you don't need a
separate error path for "lost connection" vs. "I called disconnect()". Over
CDC this also covers an unplug *while connecting*: after `connecting` fires,
a detach always ends in `on_mudra_device_disconnected` (preceded by
`on_mudra_device_connection_failed` if the ports hadn't finished opening). Note
that disconnecting (expected or not) clears most per-device callbacks on
that `MudraDevice` — see the "callbacks don't survive a disconnect" note in
[CALLBACKS.md](CALLBACKS.md#3-callbacks-dont-survive-a-disconnect).

**Transport differences to know about:**
- CDC has no PING firmware token; `device.ping()` substitutes the `CDC?`
  handshake as a round-trip probe and still fires the
  `set_on_ping_response` callback on success (§3 below).
- CDC has no SD-card storage/recording protocol at all — see
  [SENSORS.md](SENSORS.md#5-sd-card-recording-ble-only).
- Raw commands: BLE takes binary frames, CDC takes ASCII lines — see §4
  below.

## 3. Ping / round-trip check

```python
await device.set_on_ping_response(lambda: print("pong"))
await device.ping()
```

`ping()` sends a single request (`SYSTEM_PING` over BLE, the `CDC?`
handshake over CDC as a substitute) — timing/repetition is on you. Nothing
fires on failure or timeout: the callback only runs when a reply arrives, so
implement your own timeout (e.g. wait on an `asyncio.Event` set from the
callback with `asyncio.wait_for`). The
reference app's repeating ping-and-measure-latency loop lives entirely at
the app layer, not in the SDK — see
[`panels/ping.py`](../examples/mudra_connect/panels/ping.py).

## 4. Raw / advanced commands

For anything not covered by a typed wrapper method:

```python
await device.send_command(bytes([...]))            # BLE only — raw binary CONFIG frame
await Mudra().send_cdc_command(device, "EMG_ODR?")  # CDC only — raw ASCII CONFIG line
```

Both return `None` — there's no reply value. Over CDC, a reply that maps to
a typed event is routed to the matching callback (sensor status lines to the
status callbacks, `<TOKEN> ERROR ...` lines to the command-error callback,
plus device-info/firmware-version/battery replies); anything else (a plain
`<TOKEN> OK` ack or a parameter GET reply) is only written to the debug log.

The advanced/raw-command panel in the example app
([`panels/command.py`](../examples/mudra_connect/panels/command.py))
branches on `device.transport` for exactly this reason — pick the binary or
ASCII path depending on which transport `device` is on.

`device.CMD` is the device's own command table — `ProFirmwareCommand` on a
`MudraPro`, `UltimateFirmwareCommand` on a `MudraUltimate` (both in
`mudra_sdk.models.enums`; the two tables are independent). Each member has an
`.op_code`, a `.description`, and `.id` — the BLE byte template for that
command (e.g. `bytes(device.CMD.systemPing.id)`); useful for building your
own frames or logging.

## 5. Licensing & account sign-in

> **Building an app, not just a script?** See [AUTH.md](AUTH.md) for why
> sign-in matters (tier-gated features silently stay locked without it),
> the full API, and a practical checklist. This section is the short
> version.

The device enforces a capability tier (`FREE`/`PLUS`/`PRO`) via a signed
license token. The SDK has two independent, orthogonal pieces for this —
you can use either without the other:

```python
import asyncio
from mudra_sdk import auth

# Sign in BEFORE connecting: every later connect then provisions the device
# (license token + user_id) automatically, and LicenseManager renews it.
tier = await asyncio.to_thread(auth.sign_in_email, "user@example.com", "password")  # "FREE"/"PLUS"/"PRO"
await device.connect()

# Only if you signed in AFTER the device was already connected:
await auth.provision_device(device)    # fetches a token from the server, sends it
await auth.provision_user_id(device)

auth.logout()   # forgets the in-memory tier; stored cloud tokens stay on disk (see AUTH.md)
```

Connecting to a device never requires an account; signed out, it just uses
whatever tier is already on it, and `provision_device()`/`provision_user_id()`
are no-ops. The signed-in tier lives in memory for the current process only,
but the cloud client's access/refresh tokens are stored on disk and
`logout()` doesn't clear them — see [AUTH.md](AUTH.md).

Independent of sign-in, query what's actually on the device right now:

```python
await device.set_on_license_device_info_received(
    lambda info: print(f"tier={info.tier.name} valid={info.valid} serial={info.serial}")
)
await device.get_device_info()   # -> LicenseDeviceInfo via the callback above (BLE + CDC)

await device.apply_license("<88-byte token as hex>")   # set directly, bypassing auth.py
await device.clear_license()                            # drop to FREE
```

`LicenseDeviceInfo` fields: `tier` (a `LicenseTier` enum — `FREE`/`PLUS`/
`PRO`; use `.name` to print it), `valid` (bool), `now`/`floor`/`expires_at`
(unix seconds, anti-rollback bookkeeping), `serial` (str).
`get_device_info()`/`apply_license()`/`clear_license()` work on both BLE and
CDC, and the reply decodes into `LicenseDeviceInfo` on both. The last one
received is also cached in `device.get_license_device_info()`.

## 6. Firmware update (DFU, USB only)

```python
from mudra_sdk.service import DfuError, DfuStage

def on_stage(stage: str) -> None:
    print(stage)   # one of DfuStage.CONNECT / UPLOAD / MARK / RESET / DONE

def on_progress(offset: int, total: int) -> None:
    print(f"{offset}/{total} bytes")

try:
    version = await device.start_dfu(       # `device` must be the CDC (USB) MudraDevice
        "app_flpr.signed.bin", on_progress=on_progress, on_stage=on_stage
    )
    print(f"staged firmware v{version} — device is rebooting")
except DfuError as e:                        # failed after the SMP port was found
    print(f"failed at stage {e.stage}: {e.message}")
except RuntimeError as e:                    # no CDC identity, or no SMP port found
    print(f"can't start firmware update: {e}")
```

- **USB (CDC) only** — `device.start_dfu(...)` raises `RuntimeError` immediately
  if `device` has no CDC identity (`device.as_cdc_device()` is `None`), whether
  or not it's currently *connected* via CDC — there is no BLE DFU transport on
  either product yet. A device you found over BLE is a different `MudraDevice`
  object from the same device found over USB (§1); scan with `scan_cdc()` and
  use that one.
- **Requires DFU-enabled firmware already running on the device** — this
  updates firmware, it doesn't install DFU support onto a device that lacks
  it. The SDK finds the device's SMP port itself (a third USB-CDC-ACM port,
  separate from `CONFIG`/`DATA`, confirmed with an MCUmgr echo round-trip) —
  if no such port exists, `start_dfu()` raises `RuntimeError` with a message
  to that effect.
- **Flow**: connect to the SMP port → upload the signed image → mark it
  pending (test-swap, not confirmed) → reset. MCUboot swaps and boots the new
  image on its own after reset — there is no device-side "update complete"
  push, so reconnect afterward to confirm the new version actually landed.
  `start_dfu()` returns the *staged* image's version string, not a
  post-reboot confirmation.
- **`on_stage`/`on_progress` are both optional** and fire synchronously from
  inside the coroutine (not through the global `MudraDelegate` or a
  `set_on_*` callback) — `on_stage(stage: str)` with one of `DfuStage.CONNECT`
  / `.UPLOAD` / `.MARK` / `.RESET` / `.DONE`; `on_progress(offset: int, total:
  int)` fires repeatedly during `.UPLOAD` only.
- **Errors**: a missing CDC identity or missing SMP port raises plain
  `RuntimeError`; anything that fails after the SMP port is found (connect,
  upload, mark, reset) raises `DfuError` (from `mudra_sdk.service`), whose
  `.stage`/`.message` attributes identify which step failed. `DfuError` is a
  subclass of `RuntimeError`, so catch it first (as above). A bad firmware
  path raises `FileNotFoundError`/`OSError` before anything is sent.
- See [`panels/dfu.py`](../examples/mudra_connect/panels/dfu.py) for the
  reference app's firmware-update tab.

## 7. Connection pitfalls

- **Calling sensor/config/storage methods before the device is connected**
  — every method sends over the live transport; there's no queuing. Wait
  for `await device.connect()` to return, then confirm with
  `await Mudra().is_connected(device)`.
- **Treating `on_mudra_device_connected` as "ready"** — it fires as soon as
  the link is open, *before* the SDK's setup (BLE notifications, CDC status
  queries and `START`). The ready point is `await device.connect()`
  returning — see the note in
  [SDK_USAGE.md](SDK_USAGE.md#4-minimal-end-to-end-example).
- **Expecting `connect()` to raise** — it doesn't; failures arrive via
  `on_mudra_device_connection_failed`. Check `is_connected()` afterwards.
- **Expecting `ping()` to report a failure** — nothing fires on timeout;
  implement your own (§3).
- **CDC-only gaps** — no SD storage/recording, no PING token (use
  `ping()`, which substitutes `CDC?`), raw commands are ASCII text not
  binary bytes.
- **One global delegate** — `MudraDelegate` callbacks aren't scoped to a
  device; check `device.address`/`device is my_device` inside them if you
  manage more than one device at a time.

## 8. Multiple devices at once

Nothing about the SDK is single-device — `Mudra()` keeps every discovered
`MudraDevice` in an internal `{address: MudraDevice}` registry and dispatches
every transport event (data, status, storage, errors, ping, battery,
device info) by looking up the target device from that registry, so several
devices — BLE, CDC, or a mix — can be connected and streaming
simultaneously within one process:

```python
mudra = Mudra()
await mudra.scan_ble()
await mudra.scan_cdc()
# ... on_device_discovered fires once per address; connect to as many as you want ...
await device_a.connect()
await device_b.connect()

await device_a.set_on_emg_ready(lambda *args: handle(device_a, *args))
await device_b.set_on_emg_ready(lambda *args: handle(device_b, *args))
```

- Each `MudraDevice`'s per-device callbacks (§2.1–§2.5 in
  [CALLBACKS.md](CALLBACKS.md)) are independent — registering one doesn't
  affect any other device.
- The **global `MudraDelegate` is shared across every device** — its
  callbacks always receive the specific `device` the event is about, so
  dispatch on `device.address` (or `device is my_device`) inside them rather
  than assuming a single device's worth of state.
- There's no built-in cap on how many devices you can hold connected at
  once — the practical limit is your BLE adapter's own connection count and
  how many USB-CDC ports you have wired up, not anything in this SDK.

The Mudra Connect example app works this way: each connected device gets its
own window and state, opened and closed from the delegate's connection
callbacks — see [`device_window.py`](../examples/mudra_connect/device_window.py)
and [`delegate.py`](../examples/mudra_connect/delegate.py).
