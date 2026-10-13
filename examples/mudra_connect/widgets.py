"""Reusable Tk widgets for the connect app."""

from __future__ import annotations

import platform
from typing import Callable, Dict, Optional

import tkinter as tk
from tkinter import ttk

from .theme import BG_PANEL, BG_RAISED, FG, FG_MUTED, FONT_SMALL, FONT_UI_BOLD, px

# Canvas path -> canvas, for every ScrollColumn. One app-wide wheel handler
# scrolls whichever of these is under the pointer (see _on_wheel).
_SCROLLERS: Dict[str, tk.Canvas] = {}
_WHEEL_INSTALLED = False


def _wheel_steps(event: tk.Event) -> int:
    """Normalize a wheel event to +/- scroll units across Tk builds:
    X11 Tk 8.6 sends Button-4/5, Windows sends MouseWheel in multiples of
    120, macOS sends MouseWheel with small raw deltas."""
    num = getattr(event, "num", None)
    if num == 4:
        return -1
    if num == 5:
        return 1
    delta = getattr(event, "delta", 0) or 0
    if delta == 0:
        return 0
    if platform.system() == "Darwin":
        return -delta
    steps = int(-delta / 120)
    if steps == 0:
        steps = -1 if delta > 0 else 1
    return steps


def _on_wheel(event: tk.Event) -> None:
    try:
        widget = event.widget.winfo_containing(event.x_root, event.y_root)
    except (KeyError, tk.TclError, AttributeError):
        return
    while widget is not None:
        canvas = _SCROLLERS.get(str(widget))
        if canvas is not None:
            if canvas.yview() != (0.0, 1.0):
                canvas.yview_scroll(_wheel_steps(event), "units")
            return
        widget = widget.master


def _install_wheel(widget: tk.Misc) -> None:
    global _WHEEL_INSTALLED
    if _WHEEL_INSTALLED:
        return
    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        widget.bind_all(seq, _on_wheel, add="+")
        # ttk's default wheel binding cycles a combobox's value (and fires
        # <<ComboboxSelected>>, which sends a device command). With the column
        # scrolling under the pointer that would happen by accident — let the
        # wheel scroll the column instead.
        widget.unbind_class("TCombobox", seq)
    _WHEEL_INSTALLED = True


class ScrollColumn:
    """A vertically scrolling frame. Build content into ``.inner``; pack/grid
    ``.outer``. The inner frame always spans the visible width, and the mouse
    wheel scrolls it when the pointer is anywhere over its content."""

    def __init__(self, parent: tk.Widget, *, bg: str = BG_PANEL, padx: int = 0, pady: int = 0):
        self.outer = tk.Frame(parent, bg=bg)
        self.canvas = tk.Canvas(self.outer, highlightthickness=0, bg=bg, width=1, height=1)
        self.scrollbar = ttk.Scrollbar(self.outer, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.inner = tk.Frame(self.canvas, bg=bg, padx=padx, pady=pady)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._sync)
        self.canvas.bind("<Configure>", self._sync)
        _SCROLLERS[str(self.canvas)] = self.canvas
        # Device windows come and go; drop the entry with the canvas.
        self.canvas.bind(
            "<Destroy>", lambda _e, key=str(self.canvas): _SCROLLERS.pop(key, None), add="+"
        )
        _install_wheel(self.canvas)

    def _sync(self, _event=None) -> None:
        width = self.canvas.winfo_width()
        if width > 1:
            self.canvas.itemconfigure(self._win, width=width)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def natural_width(self) -> int:
        """Width the column needs to show its content without clipping."""
        self.inner.update_idletasks()
        return self.inner.winfo_reqwidth() + self.scrollbar.winfo_reqwidth()


def fit_pane(paned: ttk.PanedWindow, width_fn: Callable[[], int]) -> None:
    """Put ``paned``'s first sash at ``width_fn()`` once it's on screen — the
    left pane then fits its content at whatever font/DPI this machine uses,
    instead of a hard-coded pixel width. The user can still drag the sash."""
    state = {"done": False}

    def _apply(_event=None) -> None:
        if state["done"] or paned.winfo_width() <= 1:
            return
        state["done"] = True
        limit = max(1, paned.winfo_width() - px(320))
        try:
            paned.sashpos(0, min(width_fn(), limit))
        except tk.TclError:
            state["done"] = False

    paned.bind("<Configure>", _apply, add="+")


def auto_wrap(label: tk.Label, margin: int = 4) -> tk.Label:
    """Re-wrap a label's text to its current width (no fixed wraplength)."""
    label.bind(
        "<Configure>",
        lambda e: label.configure(wraplength=max(1, e.width - margin)),
        add="+",
    )
    return label


def config_tab(notebook: ttk.Notebook, title: str) -> tuple[tk.Frame, tk.Frame]:
    """Return (status_bar, form) for one Sensor Config tab.

    No scrolling of its own: the tab is as tall as its content and the
    column hosting the notebook scrolls instead (a fixed-height inner
    scroller is what squashed the config form before)."""
    page = tk.Frame(notebook, bg=BG_PANEL)
    notebook.add(page, text=title)

    status_bar = tk.Frame(page, bg=BG_RAISED, padx=px(6), pady=px(4))
    status_bar.pack(fill=tk.X)

    form = tk.Frame(page, bg=BG_PANEL, padx=px(4), pady=px(4))
    form.pack(fill=tk.BOTH, expand=True)
    return status_bar, form


def pin_status(bar: tk.Frame, title: str, get_fn: Callable) -> tk.Label:
    """Title + Get Status on one line, the live summary on its own line below
    so a long summary never pushes the button out of view."""
    top = tk.Frame(bar, bg=BG_RAISED)
    top.pack(fill=tk.X)
    ttk.Button(top, text="Get Status", style="Small.TButton", command=get_fn).pack(side=tk.RIGHT)
    tk.Label(
        top,
        text=title,
        bg=BG_RAISED,
        fg=FG,
        font=FONT_UI_BOLD,
    ).pack(side=tk.LEFT)
    summary = tk.Label(
        bar,
        text="—",
        bg=BG_RAISED,
        fg=FG_MUTED,
        font=FONT_SMALL,
        anchor="w",
        justify=tk.LEFT,
    )
    summary.pack(fill=tk.X, pady=(px(2), 0))
    return auto_wrap(summary)


def config_row(
    form: tk.Widget,
    label: str,
    *,
    set_fn: Optional[Callable] = None,
    get_fn: Optional[Callable] = None,
) -> tk.Frame:
    """label | mid(controls) | Set/Get — create combos/entries inside returned mid."""
    row = tk.Frame(form, bg=BG_PANEL)
    row.pack(fill=tk.X, pady=px(2))
    # Buttons are packed first so they keep their space if the row is narrow.
    btns = tk.Frame(row, bg=BG_PANEL)
    btns.pack(side=tk.RIGHT)
    if set_fn is not None:
        ttk.Button(btns, text="Set", width=4, style="Small.TButton", command=set_fn).pack(
            side=tk.LEFT, padx=(0, px(2))
        )
    if get_fn is not None:
        ttk.Button(btns, text="Get", width=4, style="Small.TButton", command=get_fn).pack(side=tk.LEFT)
    ttk.Label(row, text=label, width=12, anchor="w").pack(side=tk.LEFT)
    mid = tk.Frame(row, bg=BG_PANEL)
    mid.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(4))
    return mid


def combo(parent: tk.Widget, values: list, default, width: int = 8) -> ttk.Combobox:
    box = ttk.Combobox(parent, values=[str(v) for v in values], width=width, state="readonly")
    box.set(str(default))
    return box


def entry(parent: tk.Widget, default: str = "0", width: int = 6) -> ttk.Entry:
    e = ttk.Entry(parent, width=width)
    e.insert(0, default)
    return e
