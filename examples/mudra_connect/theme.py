"""Dark lab-tool theme for the connect app."""

from __future__ import annotations

import platform
import tkinter as tk
from tkinter import ttk

# Palette — charcoal lab console, cool teal accent (not purple/cream defaults).
BG = "#12141a"
BG_PANEL = "#1a1d26"
BG_RAISED = "#222633"
BG_INPUT = "#0e1016"
FG = "#e6e8ee"
FG_MUTED = "#8b92a5"
FG_DIM = "#5c6378"
ACCENT = "#3d9e8f"
ACCENT_DIM = "#2a6b61"
OK = "#3dba7a"
WARN = "#d4a017"
ERR = "#e05555"
BORDER = "#2e3344"
SELECT = "#1e3a36"

FONT_UI = ("Segoe UI", 9)
FONT_UI_BOLD = ("Segoe UI", 9, "bold")
FONT_TITLE = ("Segoe UI Semibold", 13)
FONT_MONO = ("Consolas", 9)
FONT_SMALL = ("Segoe UI", 8)


def apply_theme(root: tk.Tk) -> ttk.Style:
    root.configure(bg=BG)
    style = ttk.Style()
    style.theme_use("clam")

    style.configure(".", background=BG_PANEL, foreground=FG, font=FONT_UI)
    style.configure("TFrame", background=BG_PANEL)
    style.configure("TLabel", background=BG_PANEL, foreground=FG, font=FONT_UI)
    style.configure("Muted.TLabel", background=BG_PANEL, foreground=FG_MUTED, font=FONT_SMALL)
    style.configure("Title.TLabel", background=BG, foreground=FG, font=FONT_TITLE)
    style.configure("Status.TLabel", background=BG, foreground=FG_MUTED, font=FONT_SMALL)

    style.configure(
        "TButton",
        background=BG_RAISED,
        foreground=FG,
        borderwidth=0,
        padding=(10, 5),
        font=FONT_UI,
    )
    style.map(
        "TButton",
        background=[("active", ACCENT_DIM), ("disabled", BG_PANEL)],
        foreground=[("disabled", FG_DIM)],
    )
    style.configure(
        "Accent.TButton",
        background=ACCENT,
        foreground="#0a0c10",
        padding=(10, 5),
        font=FONT_UI_BOLD,
    )
    style.map("Accent.TButton", background=[("active", "#4db5a5")])

    style.configure(
        "TEntry",
        fieldbackground=BG_INPUT,
        foreground=FG,
        insertcolor=FG,
        borderwidth=1,
        padding=4,
    )
    style.configure(
        "TCombobox",
        fieldbackground=BG_INPUT,
        foreground=FG,
        arrowcolor=FG_MUTED,
        padding=3,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", BG_INPUT)],
        foreground=[("readonly", FG)],
    )

    style.configure(
        "TCheckbutton",
        background=BG_PANEL,
        foreground=FG,
        indicatorcolor=BG_INPUT,
        font=FONT_UI,
    )
    style.map(
        "TCheckbutton",
        background=[("active", BG_PANEL)],
        indicatorcolor=[("selected", ACCENT)],
    )

    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        background=BG_RAISED,
        foreground=FG_MUTED,
        padding=(14, 8),
        font=FONT_UI,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", BG_PANEL)],
        foreground=[("selected", FG)],
    )

    style.configure(
        "Vertical.TScrollbar",
        background=BG_RAISED,
        troughcolor=BG,
        arrowcolor=FG_MUTED,
        borderwidth=0,
    )

    style.configure(
        "Treeview",
        background=BG_INPUT,
        foreground=FG,
        fieldbackground=BG_INPUT,
        borderwidth=0,
        font=FONT_MONO,
        rowheight=22,
    )
    style.map(
        "Treeview",
        background=[("selected", SELECT)],
        foreground=[("selected", FG)],
    )
    style.configure(
        "Treeview.Heading",
        background=BG_RAISED,
        foreground=FG,
        font=FONT_UI_BOLD,
        borderwidth=0,
    )
    style.map("Treeview.Heading", background=[("active", ACCENT_DIM)])

    style.configure("Toolbar.TFrame", background=BG)
    style.configure("Panel.TFrame", background=BG_PANEL)
    style.configure("Card.TLabelframe", background=BG_PANEL, foreground=FG_MUTED)
    style.configure("Card.TLabelframe.Label", background=BG_PANEL, foreground=ACCENT, font=FONT_UI_BOLD)

    # macOS aqua fights dark styling; clam is forced above for consistency.
    _ = platform.system()
    return style


def panel(parent: tk.Widget, **kw) -> tk.Frame:
    return tk.Frame(parent, bg=BG_PANEL, **kw)


def muted_label(parent: tk.Widget, text: str, **kw) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        bg=BG_PANEL,
        fg=FG_MUTED,
        font=FONT_SMALL,
        anchor="w",
        **kw,
    )
