# Mudra SDK — Account Sign-In & Licensing

**If you are building an app on top of this SDK, read this page before you
skip sign-in as "optional polish."** Connecting to a device never requires
an account — a signed-out app still connects and streams fine. But every
device enforces a capability tier (`FREE`/`PLUS`/`PRO`) via a signed license
token, and higher-tier sensor features (higher ODRs, extra ranges, etc.) stay
locked unless *something* provisions that token onto the device. If your app
never calls into `mudra_sdk.auth`, your users are silently capped at
whatever tier their device already happens to hold — usually `FREE` — even
if their account is entitled to more. A real app needs a sign-in flow; a
one-off script usually doesn't.

## Two independent pieces

The SDK splits this into two orthogonal halves — you can use either without
the other:

1. **`mudra_sdk.auth`** — account sign-in against the Mudra cloud, and
   pushing a tier-appropriate license token down to a connected device.
2. **Device-level license query/apply** (`MudraDevice` methods) — reads or
   sets whatever token is *already* on the device, with no account
   involved.

### 1. Account sign-in (`mudra_sdk.auth`)

```python
from mudra_sdk import auth

# Sign in once, then re-provision the tier on every future connect.
tier = auth.sign_in_email("user@example.com", "password")  # -> "FREE"/"PLUS"/"PRO"
await auth.provision_device(device)   # fetches a token from the server, sends it
auth.logout()                          # forgets the in-memory session
```

- `sign_in_email` raises on failure (bad credentials, no connectivity,
  unactivated account); a `try`/`except` around it is how you surface a
  sign-in error to a user.
- `provision_device(device)` is a no-op if nobody's signed in — call it
  unconditionally right after `device.connect()` and it'll do the right
  thing either way (see the ordering caveat in
  [SDK_USAGE.md §4](SDK_USAGE.md#4-minimal-end-to-end-example) about
  waiting for the device to be fully ready first).
- The session (cached tier string) lives **in memory only, for the current
  process** — nothing is written to disk. There's no "remember me": restart
  the app, sign in again.
- Reference implementation: the example app's sign-in bar is a thin Tkinter
  wrapper over exactly these three calls —
  [`examples/mudra_connect/panels/auth.py`](../examples/mudra_connect/panels/auth.py).

### 2. Device-level license query/apply

Independent of any account, you can always ask a connected device what
license it's currently carrying, or set one directly:

```python
await device.get_device_info()   # -> LicenseDeviceInfo via callback (BLE + CDC)
await device.set_on_license_device_info_received(
    lambda info: print(f"tier={info.tier} valid={info.valid} serial={info.serial}")
)

await device.apply_license("<88-byte token as hex>")   # set directly, bypassing auth.py
await device.clear_license()                            # drop to FREE
```

`LicenseDeviceInfo` fields: `tier` (int), `valid` (bool), `now`/`floor`/
`expires_at` (unix seconds, anti-rollback bookkeeping), `serial` (str).
`get_device_info()` / `apply_license()` / `clear_license()` work on both BLE
and CDC, including decoding the reply into `LicenseDeviceInfo`.

## Keeping a license alive: `LicenseManager`

A license token has an expiry window. For a long-running connection,
`MudraDevice` owns a [`LicenseManager`](../mudra_sdk/models/license_manager.py)
(one per device, started on connect, stopped on disconnect) that polls
`BT_SYS_DEVICE_INFO` periodically and re-provisions automatically once the
remaining time gets short — so a session that outlives the token doesn't
silently drop back to a lower tier mid-use. This runs on its own; you don't
need to call anything for it, but it only has something to renew if
`auth.provision_device()` (or a manual `apply_license`) put a token on the
device in the first place.

## user_id provisioning (SD-card recording)

SD-card recording (see [SENSORS.md §5](SENSORS.md#5-sd-card-recording-ble-only))
needs a 16-byte `user_id` set on the device before it'll start — this is
handled automatically, the same way license provisioning is:

- Right after a device finishes connecting, the SDK sends the signed-in
  account's identifier to the device as its `user_id` — no call needed on
  your part. Sign in *before* connecting for this to take effect; signing
  in after a device is already connected does **not** push it — reconnect
  the device (or call `auth.provision_user_id(device)` yourself) instead.
- Signed out at connect time, this is a no-op — `set_storage_record()`
  then fails with `BtCmdStatus.ERR_STATE` until the device reconnects
  while signed in.
- `auth.get_user_ref()` returns the raw value if you need it for your own
  purposes (e.g. logging); most apps never need to call it.

## Practical checklist for an app built on this SDK

- Add a sign-in UI (email/password at minimum — see `panels/auth.py` for a
  minimal example) unless you specifically want to ship a tool that only
  ever uses whatever tier a device already has.
- Call `auth.provision_device(device)` right after every successful
  `device.connect()`, signed in or not — it's always safe to call.
- Surface the device's actual tier back to the user via
  `set_on_license_device_info_received`, rather than assuming sign-in
  succeeded means the device is licensed — the two are asynchronous and
  independent.
- Don't try to persist the session yourself across process restarts unless
  you have a real reason to; it's an explicit design choice that sign-in is
  memory-only (see [`mudra_sdk/auth.py`](../mudra_sdk/auth.py)).

See also: [CONNECTION.md §5](CONNECTION.md#5-licensing--account-sign-in) for
this material in the context of the full connect/scan/ping flow.
