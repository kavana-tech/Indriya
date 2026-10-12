"""Dark lab-tool theme for the connect app — one look on Windows, macOS and Linux.

Three things made the same layout render differently per OS, and this module
owns the fix for all of them:

* **Fonts.** "Segoe UI"/"Consolas" exist only on Windows; elsewhere Tk fell
  back to whatever it found, with different metrics. Families are now picked
  from what's actually installed (``_UI_FAMILIES``/``_MONO_FAMILIES``) and
  every font is a *named* Tk font, so the ``FONT_*`` constants below are font
  names that resolve after :func:`apply_theme` has created them.
* **DPI.** On Linux, Xft enlarges text by the desktop's scale (``Xft.dpi``)
  while Tk lays out every pixel distance at 1x; on macOS Tk measures in
  72-dpi points. So the same font size came out at different sizes relative
  to the layout. :func:`apply_theme` computes one :data:`UI_SCALE` (1.0 = a
  96-dpi screen), sets ``tk scaling`` from it — which also makes matplotlib's
  TkAgg canvases render at the right density — and sizes fonts in pixels
  from it, correcting for Xft's own scaling (``_FONT_FIX``).
* **Fixed pixel geometry.** Anything that has to be a pixel count goes through
  :func:`px`; column widths are measured from their content instead (see
  ``widgets.ScrollColumn``/``widgets.fit_pane``).

Set ``MUDRA_UI_SCALE`` (e.g. ``1.5``) to override the detected scale.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tkinter as tk
import tkinter.font as tkfont
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
CHART_BG = "#101010"

# Named fonts, created by apply_theme(). Pass these anywhere Tk takes a font.
FONT_UI = "MudraUI"
FONT_UI_BOLD = "MudraUIBold"
FONT_TITLE = "MudraTitle"
FONT_HEADER = "MudraHeader"
FONT_MONO = "MudraMono"
FONT_SMALL = "MudraSmall"
FONT_DOT = "MudraDot"

# Font sizes in pixels on a 96-dpi screen (Windows' 9 pt UI font is 12 px);
# multiplied by UI_SCALE so text is the same physical size everywhere.
_FONT_PX = {
    FONT_UI: (12, "normal"),
    FONT_UI_BOLD: (12, "bold"),
    FONT_TITLE: (17, "bold"),
    FONT_HEADER: (13, "bold"),
    FONT_SMALL: (11, "normal"),
    FONT_DOT: (13, "normal"),
}
_MONO_PX = 12

# First installed family wins. Ordered so each OS gets its native UI face,
# then common Linux faces, then generic fallbacks.
_UI_FAMILIES = (
    "Segoe UI",
    "SF Pro Text",
    ".AppleSystemUIFont",
    "Helvetica Neue",
    "Ubuntu",
    "Noto Sans",
    "Cantarell",
    "Liberation Sans",
    "Arial",
    "DejaVu Sans",
)
_MONO_FAMILIES = (
    "Consolas",
    "Menlo",
    "SF Mono",
    "DejaVu Sans Mono",
    "Noto Sans Mono",
    "Liberation Mono",
    "Ubuntu Mono",
    "Courier New",
)

# 1.0 == a standard 96-dpi screen. Set by apply_theme(); read through px().
UI_SCALE = 1.0
# Multiplier applied to requested font pixel sizes so they come out at the
# intended size on X11, where Xft re-scales them by its own DPI (_xft_dpi).
_FONT_FIX = 1.0
# Tkinter deletes a named font when its Font object is garbage-collected, so
# the objects created in _make_fonts() are kept alive here.
_FONTS: dict[str, tkfont.Font] = {}


def enable_windows_dpi_awareness() -> None:
    """Opt out of Windows' bitmap stretching so Tk sees the real DPI.

    Must run before ``tk.Tk()`` is created. Without it, Windows renders the
    app at 96 dpi and blurrily upscales the whole window on scaled displays.
    """
    if platform.system() != "Windows":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # system-DPI aware
    except Exception:  # noqa: BLE001 — older Windows: fall back to the legacy call
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


def _xft_dpi() -> float | None:
    """The desktop's ``Xft.dpi`` (X11/XWayland), or None if unset/unreadable.

    Tk on X11 hands font sizes to Xft in points, and Xft converts them to
    pixels with *this* DPI rather than Tk's — so on a scaled desktop text
    grows while every pixel distance Tk lays out stays at 1x."""
    if shutil.which("xrdb") is None:
        return None
    try:
        out = subprocess.run(
            ["xrdb", "-query"], capture_output=True, text=True, timeout=1
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        if line.startswith("Xft.dpi:"):
            try:
                dpi = float(line.split(":", 1)[1])
            except ValueError:
                return None
            return dpi if dpi > 0 else None
    return None


def _linux_desktop_scale() -> float:
    """Desktop scale factor Tk itself doesn't pick up (Wayland/XWayland and
    most GNOME/KDE setups report 96 dpi to Tk regardless of the setting)."""
    xft = _xft_dpi()
    if xft is not None:
        return xft / 96.0
    for var in ("GDK_SCALE", "QT_SCALE_FACTOR"):
        try:
            value = float(os.environ.get(var, ""))
            if value > 0:
                return value
        except ValueError:
            pass
    return 1.0


def _detect_scale(root: tk.Tk) -> float:
    override = os.environ.get("MUDRA_UI_SCALE")
    if override:
        try:
            return max(0.5, min(4.0, float(override)))
        except ValueError:
            pass
    system = platform.system()
    if system == "Darwin":
        # Tk on macOS works in logical points; Retina is handled by the OS.
        return 1.0
    scale = root.winfo_fpixels("1i") / 96.0
    if system == "Linux" and scale < 1.05:
        scale = _linux_desktop_scale()
    return max(1.0, min(4.0, round(scale * 4) / 4))


def px(value: float) -> int:
    """Scale a 96-dpi pixel distance to this screen."""
    return int(round(value * UI_SCALE))


def _pick_family(root: tk.Tk, candidates: tuple, fallback: str) -> str:
    installed = set(tkfont.families(root))
    for family in candidates:
        if family in installed:
            return family
    return tkfont.nametofont(fallback, root=root).actual("family")


def _font_px(size_px: float) -> int:
    """Tk font size (negative = pixels) that renders at ``size_px`` 96-dpi
    pixels scaled by UI_SCALE."""
    return -max(1, int(round(size_px * UI_SCALE * _FONT_FIX)))


def _make_fonts(root: tk.Tk) -> None:
    ui_family = _pick_family(root, _UI_FAMILIES, "TkDefaultFont")
    mono_family = _pick_family(root, _MONO_FAMILIES, "TkFixedFont")

    # Negative size = pixels. On macOS a "pixel" is a logical point, so the
    # same number gives the same apparent size as a 96-dpi Windows screen.
    for name, (size_px, weight) in _FONT_PX.items():
        _FONTS[name] = tkfont.Font(
            root, name=name, family=ui_family, size=_font_px(size_px), weight=weight
        )
    _FONTS[FONT_MONO] = tkfont.Font(
        root, name=FONT_MONO, family=mono_family, size=_font_px(_MONO_PX)
    )

    # Widgets that never get an explicit font (entries, combobox lists,
    # dialogs) use Tk's own named fonts — align those too.
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
        try:
            tkfont.nametofont(name, root=root).configure(family=ui_family, size=_font_px(12))
        except tk.TclError:
            pass
    try:
        tkfont.nametofont("TkFixedFont", root=root).configure(family=mono_family, size=_font_px(_MONO_PX))
    except tk.TclError:
        pass


def apply_theme(root: tk.Tk) -> ttk.Style:
    global UI_SCALE, _FONT_FIX
    UI_SCALE = _detect_scale(root)
    if platform.system() != "Darwin":
        screen_dpi = float(root.tk.call("tk", "scaling")) * 72.0
        # Points -> pixels for anything still sized in points, and the value
        # matplotlib's TkAgg reads (winfo_fpixels) to pick its pixel ratio.
        tk_dpi = UI_SCALE * 96.0
        root.tk.call("tk", "scaling", tk_dpi / 72.0)
        if root.tk.call("tk", "windowingsystem") == "x11":
            # Tk turns a pixel size into points with tk_dpi; Xft turns those
            # points back into pixels with Xft.dpi (or the screen's DPI).
            _FONT_FIX = tk_dpi / (_xft_dpi() or screen_dpi)
    _make_fonts(root)

    root.configure(bg=BG)
    root.option_add("*TCombobox*Listbox.font", FONT_UI)
    root.option_add("*TCombobox*Listbox.background", BG_INPUT)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_DIM)
    root.option_add("*TCombobox*Listbox.selectForeground", FG)

    style = ttk.Style(root)
    # clam on every OS: aqua/vista/xpnative ignore most dark-color options.
    style.theme_use("clam")

    style.configure(".", background=BG_PANEL, foreground=FG, font=FONT_UI)
    style.configure("TFrame", background=BG_PANEL)
    style.configure("TLabel", background=BG_PANEL, foreground=FG, font=FONT_UI)
    style.configure("Muted.TLabel", background=BG_PANEL, foreground=FG_MUTED, font=FONT_SMALL)
    style.configure("Title.TLabel", background=BG, foreground=FG, font=FONT_TITLE)
    style.configure("Status.TLabel", background=BG, foreground=FG_MUTED, font=FONT_SMALL)
    style.configure("Bar.TLabel", background=BG, foreground=FG, font=FONT_UI)

    style.configure(
        "TButton",
        background=BG_RAISED,
        foreground=FG,
        borderwidth=0,
        padding=(px(10), px(4)),
        font=FONT_UI,
    )
    style.map(
        "TButton",
        background=[("active", ACCENT_DIM), ("disabled", BG_PANEL)],
        foreground=[("disabled", FG_DIM)],
    )
    style.configure(
        "Small.TButton",
        padding=(px(6), px(2)),
        font=FONT_SMALL,
    )
    style.configure(
        "Accent.TButton",
        background=ACCENT,
        foreground="#0a0c10",
        padding=(px(10), px(4)),
        font=FONT_UI_BOLD,
    )
    style.map("Accent.TButton", background=[("active", "#4db5a5")])

    style.configure(
        "TEntry",
        fieldbackground=BG_INPUT,
        foreground=FG,
        insertcolor=FG,
        borderwidth=1,
        padding=px(3),
    )
    style.configure(
        "TCombobox",
        fieldbackground=BG_INPUT,
        foreground=FG,
        arrowcolor=FG_MUTED,
        arrowsize=px(12),
        padding=px(2),
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
        indicatorsize=px(12),
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
        padding=(px(14), px(6)),
        font=FONT_UI,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", BG_PANEL)],
        foreground=[("selected", FG)],
    )
    # Compact tabs for notebooks nested inside a side column (Sensor Config).
    style.configure("Inner.TNotebook", background=BG_PANEL, borderwidth=0)
    style.configure(
        "Inner.TNotebook.Tab",
        background=BG_RAISED,
        foreground=FG_MUTED,
        padding=(px(7), px(3)),
        font=FONT_SMALL,
    )
    style.map(
        "Inner.TNotebook.Tab",
        background=[("selected", BG_PANEL)],
        foreground=[("selected", FG)],
    )

    for orient in ("Vertical", "Horizontal"):
        style.configure(
            f"{orient}.TScrollbar",
            background=BG_RAISED,
            troughcolor=BG,
            arrowcolor=FG_MUTED,
            borderwidth=0,
            arrowsize=px(12),
        )

    style.configure("TPanedwindow", background=BG)
    style.configure("Sash", sashthickness=px(6), background=BG, gripcount=0)

    style.configure(
        "Treeview",
        background=BG_INPUT,
        foreground=FG,
        fieldbackground=BG_INPUT,
        borderwidth=0,
        font=FONT_MONO,
        rowheight=px(22),
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
