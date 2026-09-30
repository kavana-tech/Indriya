"""``mudra_sdk.lsl`` — publish a Mudra device's sensors on the Lab Streaming Layer.

Lets LSL recorders (LabRecorder) and other LSL apps capture Mudra data on one
timeline with any other LSL device (EEG, eye trackers, other Mudra devices).
It is a thin layer on top of ``MudraDevice``'s public per-sensor callbacks,
with no device I/O of its own, so BLE and USB-CDC, Mudra Pro and Mudra
Ultimate all work the same.

Three modules:

- :mod:`~mudra_sdk.lsl.bridge` — :class:`MudraLslBridge`, the part you use.
- :mod:`~mudra_sdk.lsl.clock` — :class:`DeviceClockMapper`, device time → LSL time.
- :mod:`~mudra_sdk.lsl.metadata` — stream names, channel labels and units.

::

    from mudra_sdk.lsl import MudraLslBridge

    async with MudraLslBridge(device) as bridge:
        ...   # the sensors are on and live on the LSL network

``pylsl`` is optional: importing this package doesn't need it, only
``MudraLslBridge.start()`` does (``pip install pylsl``). Guide: ``docs/LSL.md``.
"""

from __future__ import annotations

from . import metadata
from .bridge import MudraLslBridge
from .clock import GRTC_CPS, DeviceClockMapper

__all__ = ["MudraLslBridge", "DeviceClockMapper", "GRTC_CPS", "metadata"]
