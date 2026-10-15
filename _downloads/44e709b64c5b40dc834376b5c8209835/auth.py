"""Account sign-in bar: email/password fields + Login/Logout buttons.

Thin Tkinter wrapper over :mod:`mudra_sdk.auth` — sign-in is network I/O so it
runs on the app's background asyncio loop (:class:`AsyncBridge`, same as
device connect/disconnect) rather than blocking the UI thread.

Signing in is optional: connecting to a device never requires it (a
signed-out device still connects and streams at whatever tier it already
holds). It only affects whether ``ConnectAppDelegate`` can license a newly
connected device to a higher tier — a signed-out connect just leaves the
device at its current tier (see ``mudra_sdk.auth.provision_device``).
"""

from __future__ import annotations

import asyncio
from typing import Callable, Optional

import tkinter as tk
from tkinter import ttk

from ..state import AppState
from ..theme import px


def _set_auth_status(state: AppState, text: str) -> None:
    if state.auth_status_label is not None and state.root is not None and state.root.winfo_exists():
        state.auth_status_label.configure(text=text)


def _do_login(state: AppState, on_change: Optional[Callable[[bool], None]]) -> None:
    email = (state.auth_email_var.get() if state.auth_email_var else "").strip()
    password = state.auth_password_var.get() if state.auth_password_var else ""
    if not email or not password:
        _set_auth_status(state, "Enter email and password")
        return

    assert state.bridge is not None
    state.bridge.ensure_running()
    _set_auth_status(state, "Signing in...")

    async def _run() -> None:
        from mudra_sdk import auth

        loop = asyncio.get_running_loop()
        tier = await loop.run_in_executor(None, auth.sign_in_email, email, password)

        def _on_success() -> None:
            _set_auth_status(state, f"Signed in as {email} (tier {tier})")
            if state.auth_password_var is not None:
                state.auth_password_var.set("")
            if on_change is not None:
                on_change(True)

        if state.post_ui is not None:
            state.post_ui(_on_success)

    def _on_error(msg: str) -> None:
        if state.post_ui is not None:
            state.post_ui(lambda: _set_auth_status(state, f"Sign-in failed: {msg}"))

    state.bridge.run("Sign in", _run, on_error=_on_error)


def _do_logout(state: AppState, on_change: Optional[Callable[[bool], None]]) -> None:
    from mudra_sdk import auth

    auth.logout()
    _set_auth_status(state, "Not signed in")
    if on_change is not None:
        on_change(False)


def build_auth_bar(
    parent: tk.Widget,
    state: AppState,
    on_change: Optional[Callable[[bool], None]] = None,
) -> ttk.Frame:
    """Build the email/password + Login/Logout bar.

    ``on_change(signed_in)``, if given, fires once after a successful login
    (``True``) and once after logout (``False``) -- not on a failed sign-in
    attempt. Optional and backward-compatible: omitting it (the default)
    reproduces the original behavior exactly.
    """
    bar = ttk.Frame(parent, style="Toolbar.TFrame")

    ttk.Label(bar, text="Email", style="Bar.TLabel").pack(side=tk.LEFT, padx=(0, px(4)))
    state.auth_email_var = tk.StringVar()
    email_entry = ttk.Entry(bar, textvariable=state.auth_email_var, width=22)
    email_entry.pack(side=tk.LEFT, padx=(0, px(8)))

    ttk.Label(bar, text="Password", style="Bar.TLabel").pack(side=tk.LEFT, padx=(0, px(4)))
    state.auth_password_var = tk.StringVar()
    password_entry = ttk.Entry(bar, textvariable=state.auth_password_var, width=16, show="*")
    password_entry.pack(side=tk.LEFT, padx=(0, px(8)))

    email_entry.bind("<Return>", lambda _e: _do_login(state, on_change))
    password_entry.bind("<Return>", lambda _e: _do_login(state, on_change))

    ttk.Button(
        bar, text="Login", style="Accent.TButton", command=lambda: _do_login(state, on_change)
    ).pack(side=tk.LEFT, padx=(0, px(4)))
    ttk.Button(bar, text="Logout", command=lambda: _do_logout(state, on_change)).pack(side=tk.LEFT)

    state.auth_status_label = ttk.Label(bar, text="Not signed in", style="Status.TLabel")
    state.auth_status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(px(12), 0))

    return bar
