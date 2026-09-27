"""Minimal account auth + device licensing for mudra_sdk.

Flow: sign in -> get the account's Mudra Pro tier from the server. On
connect, if signed in, fetch a license token and send it to the firmware;
if signed out, leave the device's existing license alone.

The session lives in memory only, for this process — nothing is written to
disk. Signing out (or just quitting) forgets it.
"""

from __future__ import annotations

import base64
import json
from typing import Optional

from .cloud import MudraServerClient, SigninRequest
from .models import firmware_protocol as fp

APPLICATION = "MUDRA_LINK"
# /me only returns `mudraProTier` when queried under MUDRA_PRO — under
# MUDRA_LINK it returns this app's own profile fields instead (verified live
# against a real account: {"email": ..., "mudraProTier": "PRO"} vs. a
# completely different, tier-less response shape).
_TIER_APPLICATION = "MUDRA_PRO"

_session: Optional[str] = None  # cached tier ("FREE"/"PLUS"/"PRO"), in-memory only
_user_ref: Optional[str] = None  # cached `uref` claim (32 hex chars), in-memory only


def _decode_uref_claim(access_token: str) -> Optional[str]:
    """Pull the `uref` claim out of the signed access-token JWT.

    No signature verification: the client has no key to verify with, and
    doesn't need one here -- it's just being read back out of our own
    session token, not trusted as an assertion about anything else.
    """
    try:
        _, payload_b64, _ = access_token.split(".")
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        uref = payload.get("uref")
        return uref if isinstance(uref, str) else None
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def sign_in_email(email: str, password: str) -> str:
    """Sign in with email/password. Returns the account's Mudra Pro tier
    ("FREE"/"PLUS"/"PRO"); raises on failure."""
    global _session, _user_ref
    client = MudraServerClient()
    client.sign_in_api_call(SigninRequest(email.strip(), password, "Python", APPLICATION).to_json())
    me = client.get_user_info_api_call({"application": _TIER_APPLICATION})
    _session = (me.get("mudraProTier") or "FREE").upper()
    _user_ref = _decode_uref_claim(client.get_access_token() or "")
    return _session


def logout() -> None:
    global _session, _user_ref
    _session = None
    _user_ref = None


def get_user_ref() -> Optional[str]:
    """The signed-in account's `uref` claim, as 32 hex chars -- the value
    :meth:`MudraDevice.set_user_id` expects. Returns None if signed out, or
    if the current session token carries no `uref`.
    """
    return _user_ref


async def provision_device(device, set_status=print) -> None:
    """Connect-time hook: signed in -> fetch a license token from the
    server and send it to the device; signed out -> do nothing."""
    if _session is None:
        return
    token = MudraServerClient().get_pro_license(None)
    if not token:
        set_status("no license token from server")
        return
    await device.apply_license(token.hex())
    # On BLE, a successful BT_SYS_LICENSE_SET reuses BT_SYS_DEVICE_INFO's own
    # reply path (bt_command_manager.c), so LicenseDeviceInfo refreshes for
    # free right after apply_license() returns. CDC's LICENSE reply carries
    # no such push -- without this, a caller reading get_license_device_info()
    # (or a UI bound to on_license_device_info_received) right after
    # provisioning would still see the pre-provisioning snapshot until the
    # next unrelated poll. Re-query explicitly so both transports refresh
    # at the same point.
    await device.get_device_info()
    set_status(f"license sent to device (tier {_session})")


def _user_id_from_uref(uref: str) -> Optional[bytes]:
    try:
        user_id = bytes.fromhex(uref)
    except ValueError:
        return None
    return user_id if len(user_id) == fp.USER_ID_LEN else None


async def provision_user_id(device, set_status=print) -> None:
    """Connect-time hook: signed in -> send the account's `uref`
    (:func:`get_user_ref`) to the device as its user_id; signed out, or no
    `uref` on the current session, -> do nothing."""
    uref = _user_ref
    if not uref:
        return
    user_id = _user_id_from_uref(uref)
    if user_id is None:
        set_status(f"signed-in uref {uref!r} isn't valid user_id hex; not sending")
        return
    await device.set_user_id(user_id)
    set_status("user_id sent to device")


__all__ = ["sign_in_email", "logout", "provision_device", "provision_user_id", "get_user_ref"]
