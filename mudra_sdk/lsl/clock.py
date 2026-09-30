"""Convert the device's sample timestamps into LSL time.

Every package the SDK delivers carries ``timestamp``: the device's GRTC
counter reading for the package's **first** sample (1 MHz, 64-bit, no
rollover; see ``docs/data_format.md``). It is precise — taken on the sensor
when the data was sampled, before any radio or USB delay — but it counts from
when the device booted, not in the host's clock. LSL needs host time
(``pylsl.local_clock()``), so :class:`DeviceClockMapper` estimates the offset
between the two clocks.

How: for every package, ``arrival − device time`` equals the true offset
**plus** that package's transport delay. Delay is never negative, so the
**smallest** value seen recently is the best estimate of the offset — the
same idea NTP uses. The mapper keeps the minimum over a sliding window
(default 20 s), which also lets it follow slow drift of the device's crystal.

Two details keep the published timestamps smooth:

- **Warm-up.** The first packages after start arrive late, so the estimate
  improves quickly during the first second. For ``warmup_s`` (default 1 s)
  :meth:`~DeviceClockMapper.observe` returns ``None`` and the caller drops
  the package, so nothing is published with an unsettled offset.
- **Slow corrections.** After warm-up, the offset moves toward a new minimum
  by at most ``max_slew_s_per_s`` (default 0.2 ms per second of device time)
  instead of jumping. A jump would make timestamps run backwards: EMG at
  3200 Hz has only 0.3 ms between samples.

A device reboot or reconnect needs no special handling here: a disconnect
clears the bridge's callbacks, so the bridge has to be started again, and
``MudraLslBridge.start()`` calls :meth:`~DeviceClockMapper.reset`.

Nothing here talks to hardware or imports ``pylsl``: it only does arithmetic
on ``(device timestamp, arrival time)`` pairs.
"""

from __future__ import annotations

from collections import deque
from typing import Optional

#: GRTC counter ticks per second (1 MHz, one tick per microsecond).
GRTC_CPS = 1_000_000


class DeviceClockMapper:
    """Maps device GRTC timestamps to LSL ``local_clock()`` seconds.

    One mapper is shared by every sensor of a device, so all its streams get
    the same offset and stay aligned with each other.

    Parameters
    ----------
    cps:
        Device counter ticks per second (GRTC: 1 MHz).
    window_s:
        How long (host seconds) a measurement can remain the minimum.
    warmup_s:
        How long after the first measurement (and after a reset)
        :meth:`observe` returns ``None``.
    max_slew_s_per_s:
        After warm-up, the most the offset may move per second of device time.
    """

    def __init__(self, cps: int = GRTC_CPS, *, window_s: float = 20.0,
                 warmup_s: float = 1.0, max_slew_s_per_s: float = 200e-6) -> None:
        if cps <= 0:
            raise ValueError("cps must be positive")
        self.cps = float(cps)
        self.window_s = float(window_s)
        self.warmup_s = float(warmup_s)
        self.max_slew = float(max_slew_s_per_s)
        self.reset()

    def reset(self) -> None:
        """Forget every measurement and start over (including warm-up)."""
        # (arrival time, arrival − device time) pairs, oldest first. The
        # values increase from left to right, so the first one is the minimum.
        self._window: deque[tuple[float, float]] = deque()
        self._offset: Optional[float] = None   # the offset currently applied
        self._first_arrival: Optional[float] = None
        self._newest_device_s: Optional[float] = None

    def observe(self, ts_cyc: int, t_arrival: float) -> Optional[float]:
        """Record one package and return the LSL time of its device timestamp.

        ``ts_cyc`` is the package's device timestamp, ``t_arrival`` the
        ``pylsl.local_clock()`` time it arrived. Returns ``None`` during
        warm-up — drop the package.
        """
        device_s = ts_cyc / self.cps
        residual = t_arrival - device_s          # true offset + this package's delay

        # 1. Sliding-window minimum. Drop measurements older than the window;
        #    drop newer ones that are larger than this one (they can never be
        #    the minimum again while this one is in the window).
        while self._window and self._window[0][0] < t_arrival - self.window_s:
            self._window.popleft()
        while self._window and self._window[-1][1] >= residual:
            self._window.pop()
        self._window.append((t_arrival, residual))
        best = self._window[0][1]

        # 2. Apply it: jump straight to it during warm-up (nothing is published
        #    yet), afterwards move toward it slowly.
        if self._first_arrival is None:
            self._first_arrival = t_arrival
        warming_up = t_arrival - self._first_arrival < self.warmup_s
        if self._offset is None or warming_up:
            self._offset = best
        else:
            # The budget grows with device time, not with the number of calls:
            # several sensors share this mapper and their packages interleave.
            limit = self.max_slew * max(0.0, device_s - self._newest_device_s)
            self._offset += min(max(best - self._offset, -limit), limit)
        if self._newest_device_s is None or device_s > self._newest_device_s:
            self._newest_device_s = device_s

        return None if warming_up else device_s + self._offset


__all__ = ["DeviceClockMapper", "GRTC_CPS"]
