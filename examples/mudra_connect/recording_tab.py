"""Recording tab — SD card recording (firmware, onboard) and PC-side JSON
recording (DataRecorder), side by side.

Both used to live stacked in the Explorer tab's narrow left sidebar,
competing with Streams and Sensor Config for scroll space. They're
unrelated to signal exploration and each has enough controls/help text to
deserve real room, so they get their own top-level tab instead.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .panels.pc_recording import build_pc_recording_ui
from .panels.recording import build_sd_recording_ui
from .state import AppState
from .theme import ACCENT, BG_PANEL, FONT_UI_BOLD


def _section_header(parent: tk.Widget, text: str) -> None:
    tk.Label(
        parent,
        text=text,
        bg=BG_PANEL,
        fg=ACCENT,
        font=FONT_UI_BOLD,
        anchor="w",
    ).pack(fill=tk.X, pady=(0, 6))


def build_recording_tab(parent: tk.Widget, state: AppState) -> None:
    outer = tk.Frame(parent, bg=BG_PANEL)
    outer.pack(fill=tk.BOTH, expand=True)

    # Scrollable — same canvas+scrollbar+<Configure> pattern as sensors.py's
    # left column; SD Recording's help text can still run tall on a short
    # window even with two columns instead of one.
    canvas = tk.Canvas(outer, highlightthickness=0, bg=BG_PANEL)
    scroll = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    columns = tk.Frame(canvas, bg=BG_PANEL, padx=12, pady=8)
    win_id = canvas.create_window((0, 0), window=columns, anchor="nw")

    def _sync(_event=None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))
        if canvas.winfo_width() > 1:
            canvas.itemconfig(win_id, width=canvas.winfo_width())

    columns.bind("<Configure>", _sync)
    canvas.bind(
        "<Configure>",
        lambda e: canvas.itemconfig(win_id, width=e.width) if e.width > 1 else None,
    )

    def _wheel(event) -> None:
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind("<MouseWheel>", _wheel)
    columns.bind("<MouseWheel>", _wheel)

    sd_col = tk.Frame(columns, bg=BG_PANEL)
    sd_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, anchor="n", padx=(0, 16))
    _section_header(sd_col, "SD Recording")
    build_sd_recording_ui(sd_col, state)

    ttk.Separator(columns, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y)

    pc_col = tk.Frame(columns, bg=BG_PANEL)
    pc_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, anchor="n", padx=(16, 0))
    _section_header(pc_col, "PC Recording (JSON)")
    build_pc_recording_ui(pc_col, state)
