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
from .state import DeviceState
from .theme import ACCENT, BG_PANEL, FONT_UI_BOLD, px
from .widgets import ScrollColumn


def _section_header(parent: tk.Widget, text: str) -> None:
    tk.Label(
        parent,
        text=text,
        bg=BG_PANEL,
        fg=ACCENT,
        font=FONT_UI_BOLD,
        anchor="w",
    ).pack(fill=tk.X, pady=(0, 6))


def build_recording_tab(parent: tk.Widget, state: DeviceState) -> None:
    # Scrollable — SD Recording's help text can still run tall on a short
    # window even with two columns instead of one.
    column = ScrollColumn(parent, padx=px(12), pady=px(8))
    column.outer.pack(fill=tk.BOTH, expand=True)
    columns = column.inner

    sd_col = tk.Frame(columns, bg=BG_PANEL)
    sd_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, anchor="n", padx=(0, px(16)))
    _section_header(sd_col, "SD Recording")
    build_sd_recording_ui(sd_col, state)

    ttk.Separator(columns, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y)

    pc_col = tk.Frame(columns, bg=BG_PANEL)
    pc_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, anchor="n", padx=(px(16), 0))
    _section_header(pc_col, "PC Recording (JSON)")
    build_pc_recording_ui(pc_col, state)
