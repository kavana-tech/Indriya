"""Periodic license-validity watchdog for a connected MudraDevice.

BT_SYS_DEVICE_INFO's reply (MudraDevice._on_license_device_info_received)
carries the device's own view of its license window -- LicenseDeviceInfo.
now/expires_at, both device-clock epoch seconds -- which narrows as the
applied token (see auth.provision_device) approaches expiry. Left alone,
a long-running connection would silently drop back to a lower tier the
moment that window closes. LicenseManager polls it periodically and
re-provisions (fetch a fresh token from the server, apply_license it) once
the remaining time gets short, so that never happens mid-session.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

from ..logging_config import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from .mudra_device import LicenseDeviceInfo, MudraDevice


class LicenseManager:
    """One per MudraDevice (see MudraDevice._license_manager) -- constructed
    once in __init__, started on connect (update_connection_properties for
    BLE, on_cdc_ready for CDC), stopped on disconnect (handle_disconnection).
    """

    #: How often to request a fresh BT_SYS_DEVICE_INFO reply, in seconds.
    DEFAULT_CHECK_INTERVAL_S: float = 5 * 60
    #: Renew as soon as the device reports less than this many seconds left
    #: (expires_at - now) on an otherwise-valid license.
    DEFAULT_RENEW_THRESHOLD_S: float = 7 * 60

    def __init__(
        self,
        device: "MudraDevice",
        check_interval_s: float = DEFAULT_CHECK_INTERVAL_S,
        renew_threshold_s: float = DEFAULT_RENEW_THRESHOLD_S,
    ) -> None:
        self._device = device
        self._check_interval_s = check_interval_s
        self._renew_threshold_s = renew_threshold_s
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Idempotent -- safe to call on every connect even if a previous
        task somehow wasn't stopped (e.g. a reconnect on the same instance).
        The connect flow already fires an initial get_device_info() of its
        own (update_connection_properties/on_cdc_ready), and on_device_info
        below reacts to that reply too, so this only needs to sleep before
        its OWN first check rather than firing one immediately."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._check_interval_s)
                await self._check_once()
        except asyncio.CancelledError:
            raise

    async def _check_once(self) -> None:
        """Request a fresh status. The actual renew decision happens in
        on_device_info() once the reply lands (delivered the same way as
        any other BT_SYS_DEVICE_INFO reply — see MudraDevice
        ._on_license_device_info_received), not here — this call can't
        synchronously return the parsed result."""
        try:
            await self._device.get_device_info()
        except Exception as exc:  # noqa: BLE001 -- a poll failure isn't fatal
            logger.error(f"periodic status check failed: {exc}")

    def on_device_info(self, info: "LicenseDeviceInfo") -> None:
        """Called by MudraDevice right after parsing ANY fresh
        BT_SYS_DEVICE_INFO reply — this manager's own periodic poll, the
        connect-time query, or a manual 'Get' — so a soon-to-expire license
        gets renewed as soon as it's noticed, not only on this class's own
        schedule.

        A device with no valid license (FREE tier, already expired) isn't
        this class's concern: _provision_license() is best-effort and
        already no-ops when signed out, and there's nothing to "renew" if
        there was never an applied token to begin with.
        """
        if not info.valid:
            return
        remaining = info.expires_at - info.now
        if remaining < self._renew_threshold_s:
            logger.info(
                f"expires in {remaining}s "
                f"(< {self._renew_threshold_s}s) — renewing"
            )
            asyncio.create_task(self._renew())

    async def _renew(self) -> None:
        await self._device._provision_license()
