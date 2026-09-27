"""Layout-safe pop flash when label / indicator text or color changes."""

from __future__ import annotations

from typing import Any, Optional

import tkinter as tk

from .theme import ACCENT

# widget id -> list of after-ids to cancel
_pending: dict[int, list[str]] = {}

# Bright flash that doesn't change geometry (color only).
_FLASH = "#f2fffb"


def _root_of(widget: tk.Misc) -> Optional[tk.Misc]:
    try:
        return widget.winfo_toplevel()
    except tk.TclError:
        return None


def _fg_key(widget: tk.Misc) -> str:
    """tk.Label prefers fg; ttk.Label uses foreground."""
    if isinstance(widget, tk.Label):
        return "fg"
    return "foreground"


def _get_fg(widget: tk.Misc) -> str:
    key = _fg_key(widget)
    try:
        return str(widget.cget(key))
    except tk.TclError:
        try:
            return str(widget.cget("foreground"))
        except tk.TclError:
            return ACCENT


def _set_fg(widget: tk.Misc, color: str) -> None:
    key = _fg_key(widget)
    try:
        widget.configure(**{key: color})
    except tk.TclError:
        try:
            widget.configure(foreground=color)
        except tk.TclError:
            pass


def _cancel(widget: tk.Misc) -> None:
    root = _root_of(widget)
    wid = id(widget)
    jobs = _pending.pop(wid, [])
    if root is None:
        return
    for job in jobs:
        try:
            root.after_cancel(job)
        except tk.TclError:
            pass


def pop_label(widget: tk.Misc, *, settle: Optional[str] = None, flash: str = _FLASH) -> None:
    """Color pulse only — never changes font/size (avoids layout jump)."""
    root = _root_of(widget)
    if root is None:
        return

    _cancel(widget)
    target = settle if settle is not None else _get_fg(widget)
    mid = ACCENT if target.lower() != ACCENT.lower() else _FLASH

    try:
        _set_fg(widget, flash)
    except tk.TclError:
        return

    jobs: list[str] = []

    def _to_mid() -> None:
        _set_fg(widget, mid)

    def _to_settle() -> None:
        _pending.pop(id(widget), None)
        _set_fg(widget, target)

    jobs.append(root.after(70, _to_mid))
    jobs.append(root.after(180, _to_settle))
    _pending[id(widget)] = jobs


def set_text(
    widget: tk.Misc,
    text: str,
    *,
    pop: bool = True,
    flash: str = _FLASH,
    **cfg: Any,
) -> None:
    """Update label text; color-pop when the value actually changes."""
    try:
        current = str(widget.cget("text"))
    except tk.TclError:
        current = None

    changed = current != text
    settle = cfg.get("foreground", cfg.get("fg"))
    try:
        widget.configure(text=text, **cfg)
    except tk.TclError:
        return

    if pop and changed:
        pop_label(widget, settle=settle if settle is not None else _get_fg(widget), flash=flash)


def set_indicator(
    widget: tk.Misc,
    color: str,
    *,
    pop: bool = True,
    flash: str = _FLASH,
) -> None:
    """Update indicator color; pop when it changes.

    Always cancel an in-flight pop first. The pop's mid frame uses ACCENT, so
    a follow-up update to ACCENT can see ``current == target`` and skip
    re-arming — leaving the previous settle callback to restore the old
    (e.g. red) color after the text has already moved on.
    """
    _cancel(widget)
    try:
        current = _get_fg(widget)
    except tk.TclError:
        current = None

    changed = current is None or current.lower() != color.lower()
    _set_fg(widget, color)
    if pop and changed:
        pop_label(widget, settle=color, flash=flash)
