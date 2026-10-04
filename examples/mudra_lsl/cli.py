"""Headless LSL streamer — stream a Mudra Pro / Ultimate device onto the LSL network.

Turnkey front door for :class:`mudra_sdk.lsl.MudraLslBridge`: picks up devices
the OS already holds a connection to (a band paired to a Windows PC stops
advertising, so a scan alone never finds it), otherwise scans (BLE and/or
USB-CDC), connects to one device, optionally signs in and reconfigures sensors,
attaches the bridge, and publishes until interrupted. Headless — safe for a lab
PC, a service, or a smoke test. Launch it via ``examples/lsl_app.py``, which
puts the repo root on ``sys.path`` like the other example apps (``mudra_sdk`` is
not an installed package — see ``docs/installation.md``).

Examples::

    # first Mudra device found on either transport, all four sensors
    python examples/lsl_app.py

    # a specific BLE device by name substring, EMG + hand IMU only, 60 s
    python examples/lsl_app.py --transport ble --name "48-25" --sensors emg imu_hand --duration 60

    # USB device, EMG at 3200 Hz / 24-bit, custom stream label
    python examples/lsl_app.py --transport cdc --emg-odr 3200 --emg-res 24 --device-id band0

    # sign in so the device gets its licensed tier (see AGENTS.md Rule 0)
    MUDRA_EMAIL=... MUDRA_PASSWORD=... python examples/lsl_app.py

    # just list what's discoverable and exit
    python examples/lsl_app.py --list

Connecting never requires an account (the device streams at whatever tier it
already holds); pass credentials via ``--email``/``--password`` or the
``MUDRA_EMAIL``/``MUDRA_PASSWORD`` environment variables to have the SDK
provision the device on connect.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from typing import Awaitable, Callable, Optional

from mudra_sdk import Mudra
from mudra_sdk.logging_config import configure_logging, get_logger
from mudra_sdk.models.callbacks import MudraDelegate
from mudra_sdk.models.enums import EmgRes, IMUODR, PPGODR
from mudra_sdk.models.mudra_device import MudraDevice

from mudra_sdk.lsl import MudraLslBridge, metadata

logger = get_logger(__name__)

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python examples/lsl_app.py",
        description="Publish a Mudra Pro / Mudra Ultimate device's sensors onto the "
                    "Lab Streaming Layer (LSL) network.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    # Discovery / connection.
    p.add_argument("--transport", choices=("any", "ble", "cdc"), default="any",
                   help="Which transport(s) to scan (default: any).")
    p.add_argument("--name", help="Connect to the first device whose name contains "
                                  "this substring (e.g. '48-25' or 'Ultimate').")
    p.add_argument("--address", help="Connect to this exact BLE address / CDC address.")
    p.add_argument("--scan-timeout", type=float, default=15.0,
                   help="Seconds to wait for a matching device (default: 15).")
    p.add_argument("--connect-timeout", type=float, default=30.0,
                   help="Seconds to wait for the device to become ready (default: 30).")
    # Auth (optional — see AGENTS.md Rule 0).
    p.add_argument("--email", default=os.environ.get("MUDRA_EMAIL"),
                   help="Sign in before connecting so the device is provisioned to "
                        "the account's tier (default: $MUDRA_EMAIL).")
    p.add_argument("--password", default=os.environ.get("MUDRA_PASSWORD"),
                   help="Password for --email (default: $MUDRA_PASSWORD).")
    # LSL / bridge.
    p.add_argument("--sensors", nargs="+", default=list(metadata.SENSOR_KEYS),
                   choices=metadata.SENSOR_KEYS, metavar="SENSOR",
                   help=f"Sensors to turn on + publish (default: all four: "
                        f"{' '.join(metadata.SENSOR_KEYS)}).")
    p.add_argument("--device-id",
                   help="Label for this device in every LSL stream name "
                        "(default: device serial, else its name).")
    # Optional device reconfiguration (applied after connect, before enabling).
    p.add_argument("--emg-odr", type=int, help="EMG ODR in Hz (per-model set; see "
                                                "ProEMGODR / UltimateEMGODR).")
    p.add_argument("--emg-res", type=int, choices=(16, 24), help="EMG resolution (bits).")
    p.add_argument("--imu-odr", type=int, choices=[m.value for m in IMUODR],
                   help="ODR for both IMUs (Hz).")
    p.add_argument("--ppg-odr", type=int, choices=[m.value for m in PPGODR],
                   help="PPG ODR (Hz).")
    p.add_argument("--duration", type=float, default=0.0,
                   help="Seconds to stream, then stop (0 = until Ctrl-C).")
    p.add_argument("--list", action="store_true",
                   help="Scan for --scan-timeout seconds, list devices, and exit.")
    p.add_argument("--log-level", default="WARNING",
                   choices=("DEBUG", "INFO", "WARNING", "ERROR"),
                   help="SDK log verbosity (default: WARNING).")
    return p


class _CliDelegate(MudraDelegate):
    """Collects discovered devices and turns connection lifecycle into events."""

    def __init__(self, loop: asyncio.AbstractEventLoop, name: Optional[str],
                 address: Optional[str], transport: str = "any") -> None:
        self._loop = loop
        self._name = (name or "").lower()
        self._address = (address or "").lower()
        self._transport = transport
        self.devices: list[MudraDevice] = []
        self.matched: Optional[MudraDevice] = None
        self.found = asyncio.Event()
        self.connected = asyncio.Event()
        self.disconnected = asyncio.Event()
        self.failed: Optional[str] = None

    def _set(self, event: asyncio.Event) -> None:
        self._loop.call_soon_threadsafe(event.set)

    def _matches(self, device: MudraDevice) -> bool:
        # get_connected_devices() reports both transports regardless of what
        # we were asked to scan, so honour --transport here too.
        if self._transport != "any" and device.transport != self._transport:
            return False
        if self._address:
            return (device.address or "").lower() == self._address
        if self._name:
            return self._name in (device.name or "").lower()
        return True

    def on_device_discovered(self, device: MudraDevice) -> None:
        if self._transport != "any" and device.transport != self._transport:
            return
        self.devices.append(device)
        print(f"[scan] {device.name} ({device.transport}) @ {device.address}")
        if self.matched is None and self._matches(device):
            self.matched = device
            self._set(self.found)

    def on_mudra_device_connecting(self, device: MudraDevice) -> None:
        print(f"[conn] connecting to {device.name} ...")

    def on_mudra_device_connected(self, device: MudraDevice) -> None:
        print(f"[conn] connected: {device.name} ({device.transport})")
        self._set(self.connected)

    def on_mudra_device_disconnecting(self, device: MudraDevice) -> None:
        pass

    def on_mudra_device_disconnected(self, device: MudraDevice) -> None:
        print(f"[conn] disconnected: {device.name}")
        self._set(self.disconnected)

    def on_mudra_device_connection_failed(self, device: MudraDevice, error: str) -> None:
        self.failed = error
        self._set(self.connected)

    def on_bluetooth_state_changed(self, state: bool) -> None:
        if not state:
            print("[conn] Bluetooth adapter is off", file=sys.stderr)


async def _scan(mudra: Mudra, transport: str, until: asyncio.Event, timeout: float) -> bool:
    # A device the OS already holds a connection to (e.g. a band paired to a
    # Windows PC auto-connects and then stops advertising) never shows up in a
    # scan, so ask for those first. Fires on_device_discovered like scan does
    # (docs/CONNECTION.md §1); the CDC half is a no-op unless we own the port.
    try:
        await mudra.get_connected_devices()
    except Exception as exc:  # noqa: BLE001 - discovery must fall through to scan
        logger.warning("get_connected_devices failed: %s", exc)
    await asyncio.sleep(0)          # let the delegate's call_soon_threadsafe(event.set) land
    if until.is_set():
        return True
    if transport in ("any", "ble"):
        await mudra.scan_ble()
    if transport in ("any", "cdc"):
        await mudra.scan_cdc()
    try:
        await asyncio.wait_for(until.wait(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        return False
    finally:
        if transport in ("any", "ble"):
            await mudra.stop_scan_ble()
        if transport in ("any", "cdc"):
            await mudra.stop_scan_cdc()


async def _set_emg_odr(device: MudraDevice, hz: int) -> str:
    member = device.EMG_ODR_ENUM.from_value(hz)
    if member is None:
        valid = ", ".join(str(m.value) for m in device.EMG_ODR_ENUM)
        raise ValueError(f"not valid on this model (valid: {valid})")
    await device.set_emg_odr(member)
    return f"{hz} Hz"


async def _set_emg_res(device: MudraDevice, bits: int) -> str:
    await device.set_emg_res(EmgRes.from_value(bits))
    return f"{bits} bits"


async def _has_finger_imu(device: MudraDevice, timeout: float = 1.5) -> bool:
    """A band without a finger IMU never reports F_IMU status (the firmware
    answers ``F_IMU ERROR -19``). Trust a cached status; otherwise ask once and
    wait, so a slow link isn't mistaken for a missing sensor."""
    if device.get_f_imu_status_info() is not None:
        return True
    await device.get_f_imu_status()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await asyncio.sleep(0.05)
        if device.get_f_imu_status_info() is not None:
            return True
    return False


async def _set_imu_odr(device: MudraDevice, hz: int) -> str:
    odr = IMUODR.from_value(hz)
    await device.set_h_imu_odr(odr)
    if not await _has_finger_imu(device):     # don't send a config it will reject
        return f"{hz} Hz (hand IMU; no finger IMU on this device)"
    await device.set_f_imu_odr(odr)
    return f"{hz} Hz (both IMUs)"


async def _set_ppg_odr(device: MudraDevice, hz: int) -> str:
    await device.set_ppg_odr(PPGODR.from_value(hz))
    return f"{hz} Hz"


# (args attribute, label, setter) — the setter returns what to print.
_RECONFIG_STEPS: tuple[tuple[str, str, Callable[[MudraDevice, int], Awaitable[str]]], ...] = (
    ("emg_odr", "EMG ODR", _set_emg_odr),
    ("emg_res", "EMG resolution", _set_emg_res),
    ("imu_odr", "IMU ODR", _set_imu_odr),
    ("ppg_odr", "PPG ODR", _set_ppg_odr),
)


async def _apply_reconfig(device: MudraDevice, args) -> None:
    """Config changes before any sensor is turned on (docs/SENSORS.md §3).
    The bridge then reads each sensor's fresh status, so its streams match."""
    for attr, label, setter in _RECONFIG_STEPS:
        value = getattr(args, attr)
        if value is None:
            continue
        try:
            print(f"[cfg] {label} -> {await setter(device, value)}")
        except ValueError as exc:
            print(f"[cfg] {label} {value} {exc}; skipping", file=sys.stderr)


async def _run(args) -> int:
    if args.email:
        if not args.password:
            print("--email given without --password / $MUDRA_PASSWORD", file=sys.stderr)
            return 2
        from mudra_sdk import auth
        try:
            tier = auth.sign_in_email(args.email, args.password)
        except Exception as exc:  # noqa: BLE001
            print(f"[auth] sign-in failed: {exc}", file=sys.stderr)
            return 2
        print(f"[auth] signed in ({tier}); the device will be provisioned on connect")

    loop = asyncio.get_running_loop()
    mudra = Mudra()
    delegate = _CliDelegate(loop, args.name, args.address, args.transport)
    mudra.set_delegate(delegate)

    if args.list:
        print(f"[scan] scanning ({args.transport}) for {args.scan_timeout:g}s ...")
        await _scan(mudra, args.transport, asyncio.Event(), args.scan_timeout)
        if not delegate.devices:
            print("No Mudra devices found.")
            return 1
        print(f"{len(delegate.devices)} device(s) found.")
        return 0

    print(f"[scan] scanning ({args.transport}) for a device"
          + (f" named *{args.name}*" if args.name else "")
          + (f" at {args.address}" if args.address else "") + " ...")
    if not await _scan(mudra, args.transport, delegate.found, args.scan_timeout):
        print("No matching Mudra device found.", file=sys.stderr)
        return 1
    device = delegate.matched
    assert device is not None

    await device.connect()
    try:
        await asyncio.wait_for(delegate.connected.wait(), timeout=args.connect_timeout)
    except asyncio.TimeoutError:
        print("Device did not become ready in time.", file=sys.stderr)
        await device.disconnect()
        return 1
    if delegate.failed:
        print(f"Connection failed: {delegate.failed}", file=sys.stderr)
        return 1
    # AGENTS.md Rule 0 (provision on every connect) is satisfied inside the SDK:
    # MudraDevice.connect() schedules auth.provision_device(self) itself once
    # the device is ready, so calling it again here would only repeat the
    # server round-trip and the license write.
    # CDC readiness (status queries + START) completes right after the
    # connected callback; give the first status replies a moment to land.
    await asyncio.sleep(0.5)

    rc = 0
    bridge: Optional[MudraLslBridge] = None
    try:
        await _apply_reconfig(device, args)
        bridge = MudraLslBridge(device, args.device_id, sensors=args.sensors)
        # start() asks every sensor for its current status, so the streams
        # match any configuration change made just above.
        await bridge.start()
        print(f"[lsl] publishing {len(bridge.streams)} stream(s):")
        for key, name in bridge.streams.items():
            print(f"        {key:9s} -> {name}")
        for key, why in bridge.skipped.items():
            print(f"        {key:9s} -- skipped, not available on this device ({why})")
        print("[lsl] streaming - Ctrl-C to stop." if not args.duration
              else f"[lsl] streaming for {args.duration:g}s.")

        end = time.monotonic() + args.duration if args.duration > 0 else None
        while end is None or time.monotonic() < end:
            if delegate.disconnected.is_set():
                print("[lsl] device disconnected; stopping.", file=sys.stderr)
                rc = 1
                break
            await asyncio.sleep(0.25)
    except ImportError as exc:
        print(str(exc), file=sys.stderr)
        rc = 2
    except Exception as exc:  # noqa: BLE001
        print(f"[lsl] error: {exc}", file=sys.stderr)
        rc = 1
    finally:
        if bridge is not None:
            try:
                await bridge.stop()
            except Exception:  # noqa: BLE001
                pass
        if not delegate.disconnected.is_set():
            try:
                await device.disconnect()
            except Exception:  # noqa: BLE001
                pass
    print("[lsl] stopped.")
    return rc


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    configure_logging(getattr(logging, args.log_level))
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        print("\n[lsl] interrupted.")
        return 0

