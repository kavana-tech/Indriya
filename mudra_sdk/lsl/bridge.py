"""``MudraLslBridge`` — publish a connected device's sensors on Lab Streaming Layer.

How it works:

- **One LSL outlet per sensor.** Its sample rate and channel count are read
  from the device's status when the bridge starts (EMG has 3 channels on Mudra
  Pro and 8 on Mudra Ultimate; PPG has 1–4).
- **The bridge turns its sensors on and off.** In this SDK, registering a
  sensor's ``set_on_*_ready`` callback *is* what turns the sensor on, and
  clearing it turns the sensor off. :meth:`MudraLslBridge.start` registers
  the bridge's callbacks; :meth:`MudraLslBridge.stop` clears them. Each
  sensor has one callback slot, so while the bridge publishes a sensor, other
  code must not register its own callback for it — that would replace the
  bridge's. Code that wants the same samples reads them back from LSL.
- **Each package is published as soon as it arrives.** The SDK calls the
  bridge's callback on its I/O thread; the callback reorders the samples into
  rows, timestamps them, and pushes them to the outlet. ``push_chunk`` only
  copies the data into liblsl's send buffer, so this doesn't hold up the
  device connection.
- **Timestamps come from the device clock.** A shared
  :class:`~mudra_sdk.lsl.clock.DeviceClockMapper` converts each package's
  device timestamp (its first sample) into LSL time; the other samples follow
  at ``1/ODR``. Packages from the first second after start are dropped while
  the conversion settles.
- **Configuration changes and reconnects:** call :meth:`MudraLslBridge.start`
  again. It rebuilds every outlet from the device's current status.

Typical use::

    from mudra_sdk.lsl import MudraLslBridge

    # `device` is a connected MudraDevice — wait for on_mudra_device_connected
    async with MudraLslBridge(device, device_id="band0") as bridge:
        print(bridge.streams)          # {"emg": "MudraPro-band0-EMG", ...}
        await asyncio.sleep(60)        # the sensors are live on LSL
"""

from __future__ import annotations

import asyncio
import importlib
import re
import threading
from typing import Callable, Iterable, Optional

from mudra_sdk.logging_config import get_logger
from mudra_sdk.models.enums import MudraModel

from . import metadata
from .clock import DeviceClockMapper

logger = get_logger(__name__)

# The MudraDevice methods the bridge uses for each sensor:
# (register the data callback, read the cached status, ask for a fresh status).
# This SDK calls the two IMUs "hand" (imu_h / h_imu) and "finger" (imu_f / f_imu).
_DEVICE_API: dict[str, tuple[str, str, str]] = {
    metadata.EMG: ("set_on_emg_ready", "get_emg_status_info", "get_emg_status"),
    metadata.IMU_HAND: ("set_on_imu_h_ready", "get_h_imu_status_info", "get_h_imu_status"),
    metadata.IMU_RING: ("set_on_imu_f_ready", "get_f_imu_status_info", "get_f_imu_status"),
    metadata.PPG: ("set_on_ppg_ready", "get_ppg_status_info", "get_ppg_status"),
}


def _require_pylsl():
    """``pylsl`` (and ``numpy``, which it needs) are optional: only starting a
    bridge imports them."""
    try:
        return importlib.import_module("pylsl"), importlib.import_module("numpy")
    except Exception as exc:  # noqa: BLE001
        raise ImportError(
            "mudra_sdk.lsl needs pylsl: `pip install pylsl`. liblsl ships with "
            "the pylsl wheels on Windows/macOS; on Linux install it separately."
        ) from exc


def _odr_and_channels(device, sensor: str, status) -> tuple[int, int]:
    """Sample rate (Hz) and channel count, read from a sensor's status."""
    if sensor == metadata.EMG:
        return status.odr_sps.value_int, device.EMG_CHANNEL_COUNT
    if sensor == metadata.PPG:
        return status.odr_hz.value_int, status.channel_count.value_int
    return status.odr_hz.value_int, len(metadata.IMU_CHANNELS)


def _serial(device) -> str:
    info = device.get_license_device_info()      # None until BT_SYS_DEVICE_INFO
    if info and (info.serial or "").strip():
        return info.serial.strip()
    cdc = device.as_cdc_device()                 # None on BLE
    return (cdc.serial_number or "") if cdc else ""


class MudraLslBridge:
    """Publish a connected Mudra device's sensors as LSL streams.

    Parameters
    ----------
    device:
        A connected :class:`~mudra_sdk.models.mudra_device.MudraDevice`
        (Mudra Pro or Mudra Ultimate, BLE or USB-CDC). Wait for
        ``MudraDelegate.on_mudra_device_connected`` before :meth:`start`.
    device_id:
        Label used in every stream name (``MudraPro-<device_id>-EMG``).
        Default: the device serial, else its name. Use a different value for
        each device when streaming several.
    sensors:
        Which sensors to publish (and therefore turn on): any of ``"emg"``,
        ``"imu_hand"``, ``"imu_ring"``, ``"ppg"``. Default: all four.
    status_timeout:
        How long :meth:`start` waits for each sensor's status reply. A sensor
        that doesn't answer (e.g. ``imu_ring`` on a band without a finger IMU)
        is skipped with a warning.
    """

    def __init__(self, device, device_id: Optional[str] = None, *,
                 sensors: Optional[Iterable[str]] = None,
                 status_timeout: float = 3.0) -> None:
        self.device = device
        self.device_id = device_id
        self.sensors: list[str] = metadata.normalize_sensors(sensors)
        if not self.sensors:
            raise ValueError("no sensors to publish")
        self.status_timeout = float(status_timeout)
        #: ``{sensor: stream name}`` for the sensors currently published.
        self.streams: dict[str, str] = {}
        #: ``{sensor: reason}`` for requested sensors the last start() skipped.
        self.skipped: dict[str, str] = {}
        self._clock = DeviceClockMapper()
        # Every sensor's callback uses the one clock mapper; the lock keeps
        # its updates one at a time.
        self._clock_lock = threading.Lock()

    async def __aenter__(self) -> "MudraLslBridge":
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.stop()

    # -- start / stop ------------------------------------------------------ #

    async def start(self) -> None:
        """Create an outlet for each sensor and turn the sensors on.

        Calling it on a running bridge restarts it: use that after changing a
        sensor's configuration, or after the device reconnects (a disconnect
        clears every callback).

        Raises ``ImportError`` if ``pylsl`` is missing, and ``RuntimeError``
        if no requested sensor reports its status.
        """
        pylsl, np = _require_pylsl()
        if self.streams:
            await self.stop()

        # 1. Ask every sensor for its current status (all at once).
        statuses = await asyncio.gather(*(self._fresh_status(s) for s in self.sensors))
        configs = {}
        self.skipped = {}
        for sensor, status in zip(self.sensors, statuses):
            if status is None:
                self.skipped[sensor] = f"no status reply within {self.status_timeout:g}s"
                logger.warning(f"{sensor}: {self.skipped[sensor]}; not publishing it")
            else:
                configs[sensor] = _odr_and_channels(self.device, sensor, status)
        if not configs:
            raise RuntimeError(
                "none of the requested sensors reported status - is the device "
                "connected and ready (wait for on_mudra_device_connected)?")

        # 2. Build the outlets, then turn each sensor on by registering its
        #    callback — only once its outlet exists.
        serial = _serial(self.device)
        device_id = self.device_id or self._default_device_id(serial)
        self._clock.reset()
        for sensor, (odr, n_channels) in configs.items():
            outlet = self._make_outlet(pylsl, sensor, device_id, serial, odr, n_channels)
            self.streams[sensor] = outlet.get_info().name()
            callback = self._make_callback(pylsl, np, sensor, outlet, odr, n_channels)
            await getattr(self.device, _DEVICE_API[sensor][0])(callback)

        # 3. The device answers "turn on" with a status reply, or with an error
        #    and no change. Warn about any sensor it left off: its stream exists
        #    but would stay silent with nothing to say why.
        await self._warn_if_not_enabled()
        logger.info(f"LSL streams: {', '.join(self.streams.values())}")

    async def stop(self) -> None:
        """Turn the published sensors off and close their outlets. Safe to call
        on a device that has already disconnected."""
        for sensor in self.streams:
            try:
                await getattr(self.device, _DEVICE_API[sensor][0])(None)
            except Exception as exc:  # noqa: BLE001 — the device may be gone
                logger.debug(f"{sensor}: turning the sensor off failed: {exc}")
        # Each outlet was referenced only by its callback, which the SDK has
        # now dropped, so the outlets close and leave the network.
        self.streams = {}

    # -- helpers ----------------------------------------------------------- #

    async def _fresh_status(self, sensor: str):
        """Ask the device for the sensor's status and wait for the reply.

        The SDK only updates its cached status on connect and when asked, so
        the cache can be stale after a configuration change. It stores a new
        object for every reply, which is how a fresh reply is told apart from
        the old one. On timeout, falls back to the cached status (or ``None``).
        """
        _, status_info, request_status = _DEVICE_API[sensor]
        old = getattr(self.device, status_info)()
        try:
            await getattr(self.device, request_status)()
        except Exception as exc:  # noqa: BLE001 — treated like no reply
            logger.debug(f"{sensor}: status request failed: {exc}")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.status_timeout
        while loop.time() < deadline:
            await asyncio.sleep(0.05)
            status = getattr(self.device, status_info)()
            if status is not None and status is not old:
                return status
        return old

    async def _warn_if_not_enabled(self) -> None:
        def is_off(sensor):
            status = getattr(self.device, _DEVICE_API[sensor][1])()
            return status is None or not status.enabled

        off = [s for s in self.streams if is_off(s)]
        loop = asyncio.get_running_loop()
        deadline = loop.time() + min(1.0, self.status_timeout)
        while off and loop.time() < deadline:
            await asyncio.sleep(0.05)
            off = [s for s in off if is_off(s)]
        for sensor in off:
            logger.warning(
                f"{sensor}: the device didn't turn the sensor on (did it reject "
                "the command? check its license tier). Its stream is published "
                "but will carry no data.")

    def _default_device_id(self, serial: str) -> str:
        """The device serial, else its name made safe for a stream name."""
        name = self.device.name or self.device.address or ""
        return serial or re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-") or "device"

    def _make_outlet(self, pylsl, sensor: str, device_id: str, serial: str,
                     odr: int, n_channels: int):
        spec = metadata.SENSORS[sensor]
        model = "Ultimate" if self.device.MODEL == MudraModel.ULTIMATE else "Pro"
        info = pylsl.StreamInfo(
            name=f"Mudra{model}-{device_id}-{spec.suffix}",
            type=spec.lsl_type,
            channel_count=n_channels,
            nominal_srate=float(odr),
            channel_format=pylsl.cf_float32,
            # A stable source_id lets a recorder reconnect to a restarted stream.
            source_id=f"mudra_{model.lower()}:{serial or device_id}:{sensor}")

        desc = info.desc()
        desc.append_child_value("manufacturer", "Wearable Devices")
        desc.append_child_value("model", f"Mudra {model}")
        desc.append_child_value("device_id", device_id)
        desc.append_child_value("serial", serial)
        desc.append_child_value("transport", self.device.transport or "")
        channels = desc.append_child("channels")
        for label, unit, ctype in metadata.channels(sensor, n_channels):
            channel = channels.append_child("channel")
            channel.append_child_value("label", label)
            channel.append_child_value("unit", unit)
            channel.append_child_value("type", ctype)
        return pylsl.StreamOutlet(info)

    def _make_callback(self, pylsl, np, sensor: str, outlet,
                       odr: int, n_channels: int) -> Callable:
        """The ``set_on_*_ready`` callback for one sensor."""
        local_clock = pylsl.local_clock
        warned = False

        def on_ready(timestamp: int, samples: list, frequency: int,
                     frequency_std: float) -> None:
            nonlocal warned
            t_arrival = local_clock()      # first thing: the most accurate arrival time
            # This runs on the SDK's I/O thread: never let an exception escape.
            try:
                if samples and len(samples) % n_channels:
                    if not warned:
                        warned = True
                        logger.warning(
                            f"{sensor}: a package of {len(samples)} values doesn't "
                            f"fit {n_channels} channels - did the channel count "
                            "change? Call start() again. Dropping.")
                elif samples:
                    with self._clock_lock:
                        t_first = self._clock.observe(timestamp, t_arrival)
                    if t_first is not None:      # None: the clock is still warming up
                        # The SDK delivers channel by channel (all of ch0, then
                        # all of ch1, ...); LSL wants one row per sample. The
                        # transpose is only a view, and push_chunk needs a
                        # C-contiguous buffer: without the copy it rejects
                        # every package that has more than one channel and row.
                        rows = np.ascontiguousarray(
                            np.asarray(samples, dtype=np.float32).reshape(n_channels, -1).T)
                        # The device timestamp is the FIRST sample's; the rest
                        # follow at 1/ODR.
                        stamps = t_first + np.arange(len(rows)) / odr
                        outlet.push_chunk(rows, stamps.tolist())
            except Exception as exc:  # noqa: BLE001
                logger.error(f"{sensor}: LSL push failed: {exc}")

        return on_ready


__all__ = ["MudraLslBridge"]
