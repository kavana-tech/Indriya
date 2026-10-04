"""What each publishable sensor looks like as an LSL stream.

Static facts only — no device I/O, no ``pylsl``: the sensor keys, the suffix
that goes into each stream's name, the LSL content type, and each channel's
label and unit. The runtime facts (sample rate, and the channel count for EMG
and PPG) are read from the device by :mod:`mudra_sdk.lsl.bridge`.

Units are the physical units the native parser already delivers (see
``docs/data_format.md``): EMG normalized to about [-1, 1], accelerometer in g,
gyroscope in dps, PPG in microvolts.

Stream suffixes match the Mudra Pro C++ SDK's LSL streams
(``MudraPro-<id>-EMG`` / ``IMU_HAND`` / ``IMU_RING`` / ``PPG``), so consumers
set up against one SDK find streams from the other unchanged. This SDK calls
the same two IMUs "hand IMU" (``imu_h``) and "finger IMU" (``imu_f``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

EMG = "emg"
IMU_HAND = "imu_hand"
IMU_RING = "imu_ring"
PPG = "ppg"

#: Every publishable sensor, in the order streams are published.
SENSOR_KEYS: tuple[str, ...] = (EMG, IMU_HAND, IMU_RING, PPG)

#: The six IMU channels as ``(label, unit, type)``: accelerometer x/y/z, then
#: gyroscope x/y/z — the order the native parser delivers them in.
IMU_CHANNELS: tuple[tuple[str, str, str], ...] = (
    ("acc_x", "g", "Accelerometer"), ("acc_y", "g", "Accelerometer"),
    ("acc_z", "g", "Accelerometer"),
    ("gyr_x", "dps", "Gyroscope"), ("gyr_y", "dps", "Gyroscope"),
    ("gyr_z", "dps", "Gyroscope"),
)


@dataclass(frozen=True)
class SensorSpec:
    """Static identity of one publishable sensor."""

    suffix: str
    """Suffix of the stream name: ``MudraPro-<device_id>-<suffix>``."""
    lsl_type: str
    """LSL content type of the stream (``EMG`` / ``IMU`` / ``PPG``)."""
    unit: str
    """Unit of every channel, for sensors whose channel count comes from the device."""
    channels: Optional[tuple[tuple[str, str, str], ...]] = None
    """Fixed ``(label, unit, type)`` per channel, or ``None`` when the device
    decides how many channels there are (EMG: 3 on Pro / 8 on Ultimate;
    PPG: 1–4)."""


SENSORS: dict[str, SensorSpec] = {
    EMG: SensorSpec("EMG", "EMG", "normalized"),
    IMU_HAND: SensorSpec("IMU_HAND", "IMU", "g", IMU_CHANNELS),
    IMU_RING: SensorSpec("IMU_RING", "IMU", "g", IMU_CHANNELS),
    PPG: SensorSpec("PPG", "PPG", "microvolts"),
}


def normalize_sensors(names: Optional[Iterable[str]]) -> list[str]:
    """Check a list of sensor keys and return it in publishing order, without
    duplicates. ``None`` means all four. Raises :class:`ValueError` for an
    unknown key."""
    if names is None:
        return list(SENSOR_KEYS)
    wanted = set(names)
    unknown = wanted - set(SENSOR_KEYS)
    if unknown:
        raise ValueError(f"unknown sensor(s) {sorted(unknown)}; "
                         f"expected any of {', '.join(SENSOR_KEYS)}")
    return [key for key in SENSOR_KEYS if key in wanted]


def channels(sensor: str, n_channels: int) -> list[tuple[str, str, str]]:
    """``(label, unit, type)`` for each of the sensor's ``n_channels`` channels.

    Fixed-layout sensors (the IMUs) return their table. The others get labels
    ``ch0, ch1, …`` with the sensor's unit, and the stream type as each
    channel's type.
    """
    spec = SENSORS[sensor]
    if spec.channels is not None:
        return list(spec.channels[:n_channels])
    return [(f"ch{i}", spec.unit, spec.lsl_type) for i in range(n_channels)]


__all__ = ["EMG", "IMU_HAND", "IMU_RING", "PPG", "SENSOR_KEYS", "IMU_CHANNELS",
           "SensorSpec", "SENSORS", "normalize_sensors", "channels"]
