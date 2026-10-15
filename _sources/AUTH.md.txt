# Mudra SDK — Account Sign-In & Licensing

**If you are building an app on top of this SDK, read this page before you
skip sign-in as "optional polish."** Connecting to a device never requires
an account — a signed-out app still connects and streams fine. But every
device enforces a capability tier (`FREE`/`PLUS`/`PRO`) via a signed license
token, and higher-tier features stay locked unless *something* provisions
that token onto the device — for example, on a Mudra Pro the highest EMG
ODR allowed is 200 SPS on `FREE`, 800 on `PLUS` and 6400 on `PRO` (a higher
`set_emg_odr` is rejected with `ERR_LICENSE`), and SD-card recording needs
`PRO`. If your app
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
import asyncio
from mudra_sdk import auth

# Sign in BEFORE connecting. sign_in_email is blocking HTTP, so run it off the loop.
tier = await asyncio.to_thread(auth.sign_in_email, "user@example.com", "password")  # "FREE"/"PLUS"/"PRO"

await device.connect()   # signed in -> the SDK provisions license + user_id itself

# Only if you signed in AFTER the device was already connected:
await auth.provision_device(device)    # fetches a token from the server, sends it
await auth.provision_user_id(device)

auth.logout()   # forgets the in-memory tier/user ref; stored cloud tokens stay (see below)
```

- `sign_in_email` is a synchronous, blocking HTTP call — from async code,
  run it via `await asyncio.to_thread(...)` so it doesn't stall the event
  loop. It raises `requests.HTTPError` on failure (bad credentials, no
  connectivity, unactivated account); a `try`/`except` around it is how you
  surface a sign-in error to a user.
- **Provisioning is automatic.** If you're signed in when a device
  connects, the SDK itself runs `auth.provision_device(device)` and
  `auth.provision_user_id(device)` on every connect, and `LicenseManager`
  (below) renews the license before it expires. So sign in *before*
  connecting. Call those two yourself only if you signed in after the device
  was already connected (or reconnect it instead). Both are no-ops when
  signed out, so calling them is always safe.
- **What's kept where.** The signed-in tier and user ref live in memory
  only, per process — after a restart, the SDK provisions nothing until you
  call `sign_in_email` again. But the cloud client stores the access token,
  refresh token and email on disk in `~/.mudra_sdk/auth_storage.json`, and
  `auth.logout()` doesn't clear that file — so `MudraServerClient` calls
  keep working after logout and in a new process. For a
  full sign-out, also clear the stored tokens:

  ```python
  from mudra_sdk.cloud import AuthStorage
  auth.logout()
  AuthStorage().clear()
  ```
- Reference implementation: the example app's sign-in bar is a thin Tkinter
  wrapper over `sign_in_email`/`logout` —
  [`examples/mudra_connect/panels/auth.py`](../examples/mudra_connect/panels/auth.py).

### 2. Device-level license query/apply

Independent of any account, you can always ask a connected device what
license it's currently carrying, or set one directly:

```python
await device.set_on_license_device_info_received(
    lambda info: print(f"tier={info.tier.name} valid={info.valid} serial={info.serial}")
)
await device.get_device_info()   # -> LicenseDeviceInfo via the callback above (BLE + CDC)

await device.apply_license("<88-byte token as hex>")   # set directly, bypassing auth.py
await device.clear_license()                            # drop to FREE
```

`LicenseDeviceInfo` fields: `tier` (a `LicenseTier` enum — `FREE`/`PLUS`/
`PRO`; print `.name`), `valid` (bool), `now`/`floor`/`expires_at` (unix
seconds, anti-rollback bookkeeping), `serial` (str).
`get_device_info()` / `apply_license()` / `clear_license()` work on both BLE
and CDC, including decoding the reply into `LicenseDeviceInfo`. The last
reply is cached in `device.get_license_device_info()`.

## Keeping a license alive: `LicenseManager`

A license token has an expiry window. For a long-running connection,
`MudraDevice` owns a [`LicenseManager`](../mudra_sdk/models/license_manager.py)
(one per device, started on connect, stopped on disconnect) that re-queries
the device's license every 5 minutes and, once a valid license has less than
7 minutes left, re-provisions it — so a session that outlives the token
doesn't silently drop back to a lower tier mid-use. It runs on its own; you
don't need to call anything for it.

Renewal fetches a fresh token from the server, so it only works **while
signed in** — signed out, it does nothing. A token you applied manually with
`apply_license()` isn't renewed on its own terms: if you're signed in, the
renewal replaces it with your account's token; if not, it simply expires.

## user_id provisioning (SD-card recording)

SD-card recording (see [SENSORS.md §5](SENSORS.md#5-sd-card-recording-ble-only))
needs a 16-byte `user_id` set on the device before it'll start — this is
handled automatically, the same way license provisioning is:

- During every connect, the SDK sends the signed-in account's identifier
  to the device as its `user_id` — no call needed on your part. Sign in
  *before* connecting for this to take effect; signing in after a device is
  already connected does **not** push it — reconnect the device (or call
  `await auth.provision_user_id(device)` yourself) instead.
- Signed out at connect time, nothing is sent — `set_storage_record()`
  then fails with `BtCmdStatus.ERR_STATE` until a `user_id` is set: sign in
  and reconnect (or call `auth.provision_user_id(device)`), or call
  `device.set_user_id(...)` yourself with exactly 16 bytes.
- `auth.get_user_ref()` returns the raw value if you need it for your own
  purposes (e.g. logging); most apps never need to call it.

## Practical checklist for an app built on this SDK

- Add a sign-in UI (email/password at minimum — see `panels/auth.py` for a
  minimal example) unless you specifically want to ship a tool that only
  ever uses whatever tier a device already has.
- Sign in **before** connecting — the SDK then provisions the license and
  `user_id` on every connect and keeps the license renewed. If the user
  signs in while a device is already connected, call
  `await auth.provision_device(device)` and
  `await auth.provision_user_id(device)` (or reconnect).
- Call `sign_in_email` off the event loop (`await asyncio.to_thread(...)`)
  — it's blocking HTTP.
- Surface the device's actual tier back to the user via
  `set_on_license_device_info_received`, rather than assuming sign-in
  succeeded means the device is licensed — the two are asynchronous and
  independent.
- After a restart, the user must sign in again before devices get
  provisioned (the tier is memory-only), even though the stored cloud
  tokens survive. If your app offers "sign out", clear those too
  (`auth.logout()` plus `AuthStorage().clear()`).

See also: [CONNECTION.md §5](CONNECTION.md#5-licensing--account-sign-in) for
this material in the context of the full connect/scan/ping flow.
