"""Reusable Tk widgets for the connect app."""

from __future__ import annotations

import platform
from typing import Callable, Optional

import tkinter as tk
from tkinter import ttk

from .theme import BG_PANEL, BG_RAISED, FG, FG_MUTED, FONT_SMALL, FONT_UI_BOLD


def scrollable_tab(notebook: ttk.Notebook, title: str) -> tuple[tk.Frame, tk.Frame]:
    """Return (status_bar, form). Status stays pinned; form scrolls."""
    page = tk.Frame(notebook, bg=BG_PANEL)
    notebook.add(page, text=title)

    status_bar = tk.Frame(page, bg=BG_RAISED, padx=6, pady=5)
    status_bar.pack(fill=tk.X)

    body = tk.Frame(page, bg=BG_PANEL)
    body.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(body, highlightthickness=0, bg=BG_PANEL, height=240)
    scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    form = tk.Frame(canvas, bg=BG_PANEL, padx=6, pady=4)
    form_id = canvas.create_window((0, 0), window=form, anchor="nw")

    def _sync(_event=None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))
        if canvas.winfo_width() > 1:
            canvas.itemconfig(form_id, width=canvas.winfo_width())

    form.bind("<Configure>", _sync)
    canvas.bind(
        "<Configure>",
        lambda e: canvas.itemconfig(form_id, width=e.width) if e.width > 1 else None,
    )

    def _wheel(event) -> None:
        delta = (
            int(-1 * event.delta)
            if platform.system() == "Darwin"
            else int(-1 * (event.delta / 120))
        )
        canvas.yview_scroll(delta, "units")

    canvas.bind("<MouseWheel>", _wheel)
    form.bind("<MouseWheel>", _wheel)
    return status_bar, form


def pin_status(bar: tk.Frame, title: str, get_fn: Callable) -> tk.Label:
    tk.Label(
        bar,
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
    )
    summary.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
    ttk.Button(bar, text="Get Status", width=12, command=get_fn).pack(side=tk.RIGHT)
    return summary


def config_row(
    form: tk.Widget,
    label: str,
    *,
    set_fn: Optional[Callable] = None,
    get_fn: Optional[Callable] = None,
) -> tk.Frame:
    """label | mid(controls) | Set/Get — create combos/entries inside returned mid."""
    row = tk.Frame(form, bg=BG_PANEL)
    row.pack(fill=tk.X, pady=2)
    ttk.Label(row, text=label, width=12, anchor="w").pack(side=tk.LEFT)
    mid = tk.Frame(row, bg=BG_PANEL)
    mid.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
    btns = tk.Frame(row, bg=BG_PANEL)
    btns.pack(side=tk.RIGHT)
    if set_fn is not None:
        ttk.Button(btns, text="Set", width=5, command=set_fn).pack(side=tk.LEFT, padx=(0, 2))
    if get_fn is not None:
        ttk.Button(btns, text="Get", width=5, command=get_fn).pack(side=tk.LEFT)
    return mid


def combo(parent: tk.Widget, values: list, default, width: int = 8) -> ttk.Combobox:
    box = ttk.Combobox(parent, values=[str(v) for v in values], width=width, state="readonly")
    box.set(str(default))
    return box


def entry(parent: tk.Widget, default: str = "0", width: int = 6) -> ttk.Entry:
    e = ttk.Entry(parent, width=width)
    e.insert(0, default)
    return e
