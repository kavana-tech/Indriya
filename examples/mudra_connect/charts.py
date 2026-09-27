"""Matplotlib live sensor charts for the connect app."""

from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import TYPE_CHECKING, Deque, Dict, List, Optional

import tkinter as tk

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import matplotlib as _mpl

    _mpl.rcParams["path.simplify"] = True
    _mpl.rcParams["path.simplify_threshold"] = 1.0
    _mpl.rcParams["agg.path.chunksize"] = 10000
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "matplotlib is required for sensor charts.\n"
        "Install with: pip install matplotlib"
    ) from exc

if TYPE_CHECKING:
    from .state import AppState

# 1.0 => each panel's sample count is exactly its ODR (e.g. 3200 samples
# shown for a 3200 Hz sensor), not a multiple of it.
WINDOW_SECONDS = 1.0
CHART_REFRESH_MS = 50
PPG_AUTOSCALE_EVERY = 8
RATE_WINDOW_S = 1.0

# Peak-envelope display resolution per panel — matplotlib has no built-in
# equivalent of pyqtgraph's `setDownsampling(mode="peak")`, which is what the
# reference Pro_SDK signal_explorer.py uses. A plain Line2D through every raw
# sample (even with path.simplify) does NOT preserve the true min/max
# envelope of a fast, noisy signal once many samples map to the same pixel
# column — it can visually miss peaks a min/max decimation would keep. So at
# render time (not storage time — the underlying buffer still holds the full
# ODR-sized raw window) each channel is reduced to `DISPLAY_BINS` bins, each
# contributing its (min, max) as two same-x points, same technique pyqtgraph
# uses. Panels with fewer raw samples than 2x this just render raw untouched.
DISPLAY_BINS = 800

# ---- Group definitions -----------------------------------------------------
#
# A "group" is one native data series (EMG's N channels, IMU_H's 3-axis accel,
# a single PPG channel, ...). Groups are the unit of ingestion (SensorCharts
# always writes incoming samples into per-group buffers, e.g. self._buffers
# ["EMG"]) and of ODR/window sizing (set_odr() takes a group name) — both
# unaffected by how a group is currently drawn.
#
# A "panel" is one rendered chart (one matplotlib Axes). Today's panels are
# derived from groups at render time via _rebuild_panels(): a group renders
# as ONE combined panel (all its channels overlaid, e.g. today's single EMG
# chart with up to 8 lines) or as N single-channel panels (see set_split()) —
# the split state is per SENSOR (the Streams tab's EMG/IMU_H/IMU_F/PPG
# toggles), applied to every group that sensor owns (e.g. splitting IMU_H
# splits both IMU_H_ACC and IMU_H_GYRO).

SENSOR_ODR_HZ: Dict[str, int] = {
    "EMG": 200,
    "IMU_H_ACC": 100,
    "IMU_H_GYRO": 100,
    "IMU_F_ACC": 100,
    "IMU_F_GYRO": 100,
    "PPG1": 100,
    "PPG2": 100,
}

SENSOR_CHANNELS: Dict[str, List[str]] = {
    "EMG": ["ch1", "ch2", "ch3"],
    "IMU_H_ACC": ["ax", "ay", "az"],
    "IMU_H_GYRO": ["gx", "gy", "gz"],
    "IMU_F_ACC": ["ax", "ay", "az"],
    "IMU_F_GYRO": ["gx", "gy", "gz"],
    "PPG1": ["ch0"],
    "PPG2": ["ch1"],
}

SENSOR_PANELS: Dict[str, List[str]] = {
    "EMG": ["EMG"],
    "IMU_H": ["IMU_H_ACC", "IMU_H_GYRO"],
    "IMU_F": ["IMU_F_ACC", "IMU_F_GYRO"],
    "PPG": ["PPG1", "PPG2"],
}

# Display order: one full-width row per rendered panel, stacked top to
# bottom — no side-by-side pairing. GROUP_ORDER is the base (all-combined)
# ordering; _rebuild_panels() expands any currently-split group's entry into
# consecutive per-channel panel ids at the same position.
GROUP_ORDER: List[str] = [
    "EMG",
    "IMU_H_ACC",
    "IMU_H_GYRO",
    "IMU_F_ACC",
    "IMU_F_GYRO",
    "PPG1",
    "PPG2",
]

# Which Streams-tab sensor's "Split" checkbox controls a group. PPG's groups
# already carry exactly one channel each, so splitting them is a no-op —
# omitted here, and sensors.py doesn't offer a PPG split control.
GROUP_SENSOR: Dict[str, str] = {
    "EMG": "EMG",
    "IMU_H_ACC": "IMU_H",
    "IMU_H_GYRO": "IMU_H",
    "IMU_F_ACC": "IMU_F",
    "IMU_F_GYRO": "IMU_F",
}
SPLITTABLE_SENSORS = ("EMG", "IMU_H", "IMU_F")

PANEL_HEIGHT_RATIOS: Dict[str, float] = {
    "EMG": 1.3,
    "IMU_H_ACC": 1.0,
    "IMU_H_GYRO": 1.0,
    "IMU_F_ACC": 1.0,
    "IMU_F_GYRO": 1.0,
    "PPG1": 0.9,
    "PPG2": 0.9,
}
# Height ratio for a single-channel panel produced by splitting a group —
# smaller than any combined panel's ratio above since there are many more
# of them on screen at once; the scrollable chart area (see sensors.py)
# is what makes that acceptable instead of squeezing everything unreadably
# thin.
SPLIT_HEIGHT_RATIO = 0.55

# Content inches (i.e. excluding margins/gaps) per unit of a panel's height
# ratio — chosen, together with the fixed-inch margins/gaps above, so the
# default all-combined layout (n=7, total ratio 7.1) reproduces this file's
# previous fixed 13.5" figure exactly: 13.5 = _MARGIN_TOP_INCHES +
# _MARGIN_BOTTOM_INCHES + _ROW_GAP_INCHES*(7-1) + 7.1*_INCHES_PER_RATIO_UNIT.
# Each panel's own height in inches is `ratio * _INCHES_PER_RATIO_UNIT` —
# a function of ONLY that panel's ratio, not of how many other panels
# exist — so splitting one sensor no longer shrinks every other panel's
# on-screen size; it only grows the figure (and hence the scrollable area)
# by exactly the new panels' own content, on top of a constant margin/gap
# overhead.
_INCHES_PER_RATIO_UNIT = 1.389
_FIGURE_WIDTH_INCHES = 8.5

# EMG carries 8 colors (Ultimate's channel count) even though Pro only uses
# the first 3 — Okabe-Ito colorblind-safe palette, extended with gray for
# the 8th slot (Okabe-Ito's black reads poorly on this chart's black bg).
SENSOR_COLORS = {
    "EMG": ["#f0e442", "#56b4e9", "#cc79a7", "#e69f00", "#009e73", "#0072b2", "#d55e00", "#999999"],
    "IMU_H_ACC": ["#e74c3c", "#2ecc71", "#3498db"],
    "IMU_H_GYRO": ["#e74c3c", "#2ecc71", "#3498db"],
    "IMU_F_ACC": ["#e74c3c", "#2ecc71", "#3498db"],
    "IMU_F_GYRO": ["#e74c3c", "#2ecc71", "#3498db"],
    "PPG1": ["#00bcd4"],
    "PPG2": ["#e91e63"],
}

SENSOR_TITLES = {
    "EMG": "EMG  (normalized ±1)",
    "IMU_H_ACC": "IMU hand accel (g)",
    "IMU_H_GYRO": "IMU hand gyro (dps)",
    "IMU_F_ACC": "IMU finger accel (g)",
    "IMU_F_GYRO": "IMU finger gyro (dps)",
    "PPG1": "PPG ch0 (µV)",
    "PPG2": "PPG ch1 (µV)",
}

SENSOR_YLIM: Dict[str, Optional[tuple[float, float]]] = {
    "EMG": (-1.0, 1.0),
    "IMU_H_ACC": (-4.0, 4.0),
    "IMU_H_GYRO": (-500.0, 500.0),
    "IMU_F_ACC": (-4.0, 4.0),
    "IMU_F_GYRO": (-500.0, 500.0),
    "PPG1": None,
    "PPG2": None,
}

# Left/right margins are FIXED INCHES, same rationale as the vertical
# margins below: the figure's WIDTH now tracks the window (see
# _current_fig_width_inches/sensors.py's chart-canvas width sync), so a
# fraction here would give y-axis tick labels less and less absolute room
# as the window narrows (clipping "1.00" down to ".00" well before the
# app's declared minsize) while wasting an ever-growing strip of blank
# margin as it widens. Chosen to reproduce this file's original fixed-8.5"-
# wide figure's margins almost exactly (0.07*8.5=0.595", 0.01*8.5=0.085")
# — see _relayout(), which converts these to fractions of whatever the
# CURRENT figure width is, every time (construction, rebuild, and resize).
_MARGIN_LEFT_INCHES = 0.6
_MARGIN_RIGHT_INCHES = 0.1
# Vertical margins/gaps are FIXED INCHES, not figure-fractions — the figure's
# height varies a lot with panel count (see _rebuild_panels), and a
# fraction-based gap silently consumes a bigger and bigger SHARE of the
# available height as more panels are split out (each of the n-1 gaps eats
# a fixed fraction, so total gap overhead grows linearly with n while the
# panels' own share shrinks) even though the figure itself grows to
# compensate for the *split* panels — every OTHER panel (anything not just
# split) was getting squeezed too, which is why splitting EMG made PPG
# visibly shrink despite PPG's own config never changing. Fixed-inch
# margins/gaps make each panel's absolute pixel height a pure function of
# its own PANEL_HEIGHT_RATIOS/SPLIT_HEIGHT_RATIO entry, independent of how
# many other panels currently exist. Values below reproduce this file's
# original fixed-13.5"-figure, n=7, all-combined layout exactly (e.g. PPG1's
# height comes out to the same ~112.5px either way) — see _relayout().
_MARGIN_TOP_INCHES = 0.27
_MARGIN_BOTTOM_INCHES = 0.61
_ROW_GAP_INCHES = 0.46


def _calc_window_len(odr_hz: int) -> int:
    """Sample count spanning WINDOW_SECONDS at `odr_hz` — this IS the chart's
    point count / buffer capacity for that sensor, so a 3200 Hz EMG stream
    gets a much wider (16x) window than a 200 Hz one, instead of every
    sensor being squeezed/stretched to fit the same fixed point count."""
    return max(64, int(WINDOW_SECONDS * max(1, odr_hz)))


def scale_channel_blocked(sensor: str, flat: List[float]) -> List[float]:
    """Identity — native Parser already applies Pro_SDK physical-unit scaling."""
    return flat


def _bin_bounds(window_len: int, bins: int) -> Optional[List[tuple[int, int]]]:
    """(start, end) sample-index ranges for `bins` peak-envelope buckets
    spanning a `window_len`-sample buffer, or `None` if the window is
    already small enough that raw samples should just be shown directly."""
    if window_len <= bins * 2:
        return None
    bin_size = window_len / bins
    bounds = []
    for b in range(bins):
        start = int(b * bin_size)
        end = int((b + 1) * bin_size)
        if end <= start:
            end = start + 1
        bounds.append((start, min(end, window_len)))
    return bounds


def _envelope_xy(
    raw: List[float], bounds: Optional[List[tuple[int, int]]]
) -> List[float]:
    """Reduce `raw` to its (min, max)-per-bin envelope per `bounds` — same
    technique as pyqtgraph's `setDownsampling(mode="peak")`, which is what
    made EMG display correctly in the reference Pro_SDK signal_explorer.py.
    `bounds is None` means the buffer is already short enough — pass through
    unchanged. Each bin contributes two y-values at the SAME x (its start
    index), matching the fixed `_display_xs` computed alongside `bounds`."""
    if bounds is None:
        return raw
    out: List[float] = []
    for start, end in bounds:
        chunk = raw[start:end]
        out.append(min(chunk))
        out.append(max(chunk))
    return out


class SensorCharts:
    """Rolling live charts — one full-width row per rendered panel, stacked
    top to bottom, blit redraw.

    Each GROUP's buffer length (point count) is sized directly from that
    group's actual ODR via `_calc_window_len` — no decimation, no shared
    fixed point count. The deque's `maxlen` alone keeps exactly one
    WINDOW_SECONDS-wide window of raw samples; incoming data is appended
    as-is regardless of chunk size. Buffers are always GROUP-keyed and are
    unaffected by split state — only the panel (Axes/Line2D) layer changes
    when a sensor is split, via `_rebuild_panels()`.
    """

    def __init__(self, parent: tk.Widget, state: Optional["AppState"] = None):
        self._state = state
        self._lock = Lock()
        self._pending: Dict[str, List[List[float]]] = {s: [] for s in SENSOR_PANELS}
        self._buffers: Dict[str, List[Deque[float]]] = {}
        self._channel_names: Dict[str, List[str]] = {}
        self._split: Dict[str, bool] = {s: False for s in SPLITTABLE_SENSORS}
        self._lines: Dict[str, list] = {}
        self._axes: Dict[str, object] = {}
        self._bgs: Dict[str, object] = {}
        self._dirty: set[str] = set()
        self._ppg_frame = 0
        self._blit_ready = False
        self._resize_after = None
        self._rate_counts: Dict[str, int] = {s: 0 for s in SENSOR_PANELS}
        self._rate_hz: Dict[str, float] = {s: 0.0 for s in SENSOR_PANELS}
        self._rate_t0 = time.perf_counter()
        self._odr_hz = dict(SENSOR_ODR_HZ)
        self._window_len: Dict[str, int] = {
            group: _calc_window_len(hz) for group, hz in SENSOR_ODR_HZ.items()
        }
        self._bin_bounds: Dict[str, Optional[List[tuple[int, int]]]] = {}
        self._display_xs: Dict[str, List[int]] = {}
        for group, n in self._window_len.items():
            self._recompute_display_xs(group, n)

        for group, names in SENSOR_CHANNELS.items():
            self._channel_names[group] = list(names)
            n = self._window_len[group]
            self._buffers[group] = [deque([0.0] * n, maxlen=n) for _ in names]

        # Rendered-panel bookkeeping — populated by _rebuild_panels().
        self._panel_order: List[str] = []
        self._panel_group: Dict[str, str] = {}
        self._panel_channel_indices: Dict[str, List[int]] = {}
        self._panel_height: Dict[str, float] = {}

        self.figure = Figure(figsize=(_FIGURE_WIDTH_INCHES, 13.5), dpi=90, facecolor="#101010")
        self._rebuild_panels()

        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        widget = self.canvas.get_tk_widget()
        widget.configure(bg="#101010", highlightthickness=0)
        widget.pack(fill=tk.BOTH, expand=True)
        self.canvas.draw()
        self._capture_backgrounds()
        self._blit_ready = True
        # add="+": FigureCanvasTkAgg.__init__() already bound its own
        # <Configure> handler on this same widget (backend_tk's
        # FigureCanvasTk.resize -> _resize_figure_for_canvas_size, which is
        # what keeps figure.set_size_inches in sync with the widget's actual
        # on-screen size). A plain widget.bind(..., self._on_resize) here
        # REPLACES that binding instead of adding to it — the widget would
        # then visibly resize (e.g. via sensors.py's chart-canvas width
        # sync) while the figure's logical inches silently never updated,
        # leaving every chart stuck at its construction-time width forever.
        widget.bind("<Configure>", self._on_resize, add="+")

    def _current_fig_width_inches(self) -> float:
        """The figure's current on-screen width in inches, read straight off
        the live Tk widget so a rebuild (split toggle, EMG channel-count
        change) preserves whatever width the window is actually at instead
        of resetting to _FIGURE_WIDTH_INCHES. Falls back to that constant
        before the widget exists yet (first call, from __init__) or before
        it's been mapped on screen (winfo_width() still reports 1)."""
        canvas = getattr(self, "canvas", None)
        if canvas is not None:
            w = canvas.get_tk_widget().winfo_width()
            if w > 1:
                return w / self.figure.dpi
        return _FIGURE_WIDTH_INCHES

    def _rebuild_panels(self) -> None:
        """(Re)build every rendered panel (Axes/Line2D/legend) from the
        current split state (self._split) and each group's current channel
        count (only EMG's varies, 3 vs 8 — see set_emg_channel_count).
        Called at construction and whenever either changes: both change how
        many Axes exist, not just their data, so a partial in-place update
        (like set_odr's, which only touches an existing panel's x-range/
        data) isn't enough — the whole figure is cleared and rebuilt.
        Must run on the Tk main thread."""
        self.figure.clf()
        self._axes = {}
        self._lines = {}
        self._panel_order = []
        self._panel_group = {}
        self._panel_channel_indices = {}
        self._panel_height = {}
        self._bgs = {}

        for group in GROUP_ORDER:
            names = self._channel_names[group]
            sensor = GROUP_SENSOR.get(group)
            split = bool(sensor) and self._split.get(sensor, False) and len(names) > 1
            if split:
                for idx in range(len(names)):
                    panel_id = f"{group}::{names[idx]}"
                    self._panel_order.append(panel_id)
                    self._panel_group[panel_id] = group
                    self._panel_channel_indices[panel_id] = [idx]
                    self._panel_height[panel_id] = SPLIT_HEIGHT_RATIO
            else:
                self._panel_order.append(group)
                self._panel_group[group] = group
                self._panel_channel_indices[group] = list(range(len(names)))
                self._panel_height[group] = PANEL_HEIGHT_RATIOS[group]

        n = len(self._panel_order)
        content_inches = sum(self._panel_height.values()) * _INCHES_PER_RATIO_UNIT
        fig_height_inches = (
            _MARGIN_TOP_INCHES + _MARGIN_BOTTOM_INCHES + _ROW_GAP_INCHES * max(0, n - 1) + content_inches
        )
        fig_width_inches = self._current_fig_width_inches()
        self.figure.set_size_inches(fig_width_inches, fig_height_inches)

        # Figure.set_size_inches() only changes the figure's LOGICAL size.
        # matplotlib's TkAgg backend ties widget size to figure size in the
        # opposite direction only — FigureCanvasTk binds the Tk widget's own
        # <Configure> to resize the FIGURE to match the WIDGET (see
        # backend_tk.py's FigureCanvasTk.resize/_resize_figure_for_canvas_
        # size) — so growing the figure here does nothing to the on-screen
        # widget by itself: it stays whatever size it was originally packed
        # at, the taller content just renders into (and gets clipped by) the
        # same old viewport, and the outer scrollable canvas (sensors.py)
        # never sees a size change to extend its scrollregion to. Not
        # present on the very first call (during __init__, before
        # self.canvas exists) — that initial size is already correct
        # because FigureCanvasTkAgg reads it fresh from the figure when
        # constructed, right after this method returns.
        canvas = getattr(self, "canvas", None)
        if canvas is not None:
            w = max(1, int(self.figure.bbox.width))
            h = max(1, int(self.figure.bbox.height))
            canvas.get_tk_widget().configure(width=w, height=h)
            # The .configure() above only changes the WIDGET's requested
            # size (which is what the outer scrollable canvas in sensors.py
            # reads to grow its scrollregion — that part already worked).
            # It does NOT resize matplotlib's own render target: FigureCanvasTk
            # draws into a fixed-size tk.PhotoImage (self.canvas._tkphoto)
            # that's only reallocated by the backend's OWN internal
            # <Configure> handler (_resize_figure_for_canvas_size), and that
            # handler is driven by Tk's geometry manager actually reflowing
            # the widget — which doesn't reliably happen synchronously from a
            # bare .configure() call here (e.g. when the widget is under
            # pack(fill=BOTH, expand=True) inside a canvas window). Net
            # effect: the scrollable area grew correctly, but newly-exposed
            # rows were rendering into a PhotoImage still sized for the OLD
            # (shorter) figure, so anything past the old boundary — commonly
            # PPG, being last — showed blank/clipped. Call the backend's own
            # resize logic directly so the PhotoImage buffer and the figure
            # size change atomically, instead of depending on an async Tk
            # event that may not fire before the next draw().
            resize_fn = getattr(canvas, "_resize_figure_for_canvas_size", None)
            if resize_fn is not None:
                resize_fn(w, h)

        for panel_id in self._panel_order:
            group = self._panel_group[panel_id]
            names = self._channel_names[group]
            colors = SENSOR_COLORS[group]
            indices = self._panel_channel_indices[panel_id]
            title = SENSOR_TITLES[group]
            if len(indices) == 1 and len(names) > 1:
                title = f"{title} — {names[indices[0]]}"

            ax = self.figure.add_axes([0.0, 0.0, 0.1, 0.1])  # real position set by _relayout
            ax.set_facecolor("#000000")
            ax.set_title(title, fontsize=9, color="#dddddd", pad=3)
            ax.grid(True, color="#222222", linewidth=0.6)
            ax.tick_params(labelsize=7, colors="#888888")
            for spine in ax.spines.values():
                spine.set_color("#333333")
            ax.set_xlim(0, self._window_len[group] - 1)
            ylim = SENSOR_YLIM[group]
            if ylim is not None:
                ax.set_ylim(*ylim)

            zeros = [0.0] * len(self._display_xs[group])
            lines = []
            for ch_idx in indices:
                (line,) = ax.plot(
                    self._display_xs[group],
                    zeros,
                    lw=0.8,
                    color=colors[ch_idx % len(colors)],
                    label=names[ch_idx],
                    animated=True,
                )
                lines.append(line)
            if len(lines) > 1:
                leg = ax.legend(loc="upper right", fontsize=6, framealpha=0.35)
                leg.get_frame().set_facecolor("#111111")
                for t in leg.get_texts():
                    t.set_color("#cccccc")
            self._axes[panel_id] = ax
            self._lines[panel_id] = lines

        self._relayout()
        self._dirty |= set(GROUP_ORDER)
        self._blit_ready = False

    def set_split(self, sensor: str, enabled: bool) -> None:
        """Toggle whether `sensor`'s groups render as one combined panel (N
        overlaid lines) or N separate single-channel panels. `sensor` is a
        Streams-tab name (EMG, IMU_H, IMU_F) — PPG's groups already carry
        one channel each, so this is a no-op for it (and sensors.py doesn't
        offer a PPG split control). Must run on the Tk main thread."""
        if sensor not in self._split or self._split[sensor] == enabled:
            return
        self._split[sensor] = enabled
        self._rebuild_panels()

    def set_emg_channel_count(self, count: int) -> None:
        """Resize EMG's buffers/channel names for `count` channels (3 on
        Pro, 8 on Ultimate — see MudraDevice.EMG_CHANNEL_COUNT), then
        rebuild every panel — cheap relative to a connection's lifetime
        (only runs on connect), and necessary since a channel-count change
        also changes how many single-channel panels exist if EMG is
        currently split. Must run on the Tk main thread."""
        group = "EMG"
        if count <= 0 or count == len(self._channel_names.get(group, [])):
            return
        with self._lock:
            self._channel_names[group] = [f"ch{i + 1}" for i in range(count)]
            n = self._window_len[group]
            self._buffers[group] = [deque([0.0] * n, maxlen=n) for _ in range(count)]
        self._rebuild_panels()

    def _relayout(self) -> None:
        """Recompute every panel's [left, bottom, width, height] position:
        stacked top-to-bottom, each panel's height in ABSOLUTE INCHES (its
        own ratio × _INCHES_PER_RATIO_UNIT — see that constant's comment for
        why fixed inches, not a shared figure-fraction, is what keeps one
        panel's size independent of how many others currently exist), only
        converted to the figure-fraction set_position() needs at the end.
        Every panel gets the SAME width (the full available width, minus the
        fixed-inch left/right margins converted to a fraction of whatever
        the CURRENT figure width is — see _MARGIN_LEFT_INCHES/_RIGHT_INCHES)
        — only each panel's internal x-axis point count (set in `set_odr`)
        and its height ratio (combined vs. split — see
        PANEL_HEIGHT_RATIOS/SPLIT_HEIGHT_RATIO) vary. Called at construction,
        on every rebuild, and on every resize (_finish_resize) — cheap
        (only .set_position() calls, no Axes/Line2D rebuild), and necessary
        since the figure's WIDTH itself can change independently of any of
        those triggers now."""
        fig_width_inches, fig_height_inches = self.figure.get_size_inches()
        left_frac = _MARGIN_LEFT_INCHES / fig_width_inches
        avail_width = (fig_width_inches - _MARGIN_LEFT_INCHES - _MARGIN_RIGHT_INCHES) / fig_width_inches

        y_inches = fig_height_inches - _MARGIN_TOP_INCHES
        for panel_id in self._panel_order:
            h_inches = self._panel_height[panel_id] * _INCHES_PER_RATIO_UNIT
            y_inches -= h_inches
            self._axes[panel_id].set_position([
                left_frac,
                y_inches / fig_height_inches,
                avail_width,
                h_inches / fig_height_inches,
            ])
            y_inches -= _ROW_GAP_INCHES

    def _recompute_display_xs(self, group: str, window_len: int) -> None:
        """(Re)compute `group`'s peak-envelope bin bounds + matching fixed
        x-coordinates for its current `window_len`. Called at construction
        and whenever `set_odr` actually resizes a group."""
        bounds = _bin_bounds(window_len, DISPLAY_BINS)
        self._bin_bounds[group] = bounds
        if bounds is None:
            self._display_xs[group] = list(range(window_len))
        else:
            xs: List[int] = []
            for start, _end in bounds:
                xs.append(start)
                xs.append(start)
            self._display_xs[group] = xs

    def _capture_backgrounds(self) -> None:
        for panel_id, ax in self._axes.items():
            self._bgs[panel_id] = self.canvas.copy_from_bbox(ax.bbox)

    def _on_resize(self, _event=None) -> None:
        widget = self.canvas.get_tk_widget()
        if self._resize_after is not None:
            try:
                widget.after_cancel(self._resize_after)
            except Exception:
                pass
        self._resize_after = widget.after(120, self._finish_resize)

    def _finish_resize(self) -> None:
        self._resize_after = None
        self._blit_ready = False
        # By this point matplotlib's own <Configure> handler (see the
        # add="+" comment in __init__) has already updated figure.set_size_
        # inches to match the widget's new on-screen size — but the axes'
        # [left, bottom, width, height] positions are fractions computed
        # against the OLD width at the last _relayout() call, so the
        # fixed-inch margins (_MARGIN_LEFT_INCHES/_RIGHT_INCHES) need
        # recomputing against the new width too.
        self._relayout()
        self.canvas.draw()
        self._capture_backgrounds()
        self._blit_ready = True

    def set_odr(self, group: str, hz: int) -> None:
        """Update `group`'s assumed ODR and, if it actually changed, resize
        its buffer/x-axis to match (`_calc_window_len`) so the displayed
        window keeps spanning ~WINDOW_SECONDS of real time at the new rate.
        Applies to every panel currently showing `group` — one if combined,
        N if split. Panel width is unaffected (every panel is always
        full-width; see `_relayout`) — only point count changes.
        Must run on the Tk main thread (matplotlib objects aren't otherwise
        touched off it) — true for both call sites (button handlers and
        status-callback `post_ui` dispatch).
        """
        if group not in self._odr_hz or hz <= 0 or hz == self._odr_hz[group]:
            return
        self._odr_hz[group] = hz
        new_len = _calc_window_len(hz)
        if new_len == self._window_len.get(group):
            return

        with self._lock:
            self._window_len[group] = new_len
            self._recompute_display_xs(group, new_len)
            self._buffers[group] = [
                deque([0.0] * new_len, maxlen=new_len) for _ in self._channel_names[group]
            ]

        zeros = [0.0] * len(self._display_xs[group])
        for panel_id in self._panel_order:
            if self._panel_group.get(panel_id) != group:
                continue
            ax = self._axes[panel_id]
            ax.set_xlim(0, new_len - 1)
            for line in self._lines[panel_id]:
                line.set_xdata(self._display_xs[group])
                line.set_ydata(zeros)
        self._dirty.add(group)
        # Axis range changed — a partial blit against the old background
        # would be wrong; force a full redraw + fresh background capture.
        self._blit_ready = False

    def clear(self, sensor: Optional[str] = None) -> None:
        with self._lock:
            if sensor is None:
                for key in self._pending:
                    self._pending[key].clear()
                targets = list(self._buffers)
            else:
                self._pending.get(sensor, []).clear()
                targets = SENSOR_PANELS.get(sensor, [sensor])
            for group in targets:
                if group not in self._buffers:
                    continue
                n = self._window_len[group]
                self._buffers[group] = [
                    deque([0.0] * n, maxlen=n) for _ in self._channel_names[group]
                ]
                self._dirty.add(group)

    def _emg_channel_count(self) -> int:
        """3 on Pro, 8 on Ultimate — read from the connected device rather
        than hardcoded, since the two products differ here. Falls back to 3
        (matches SENSOR_CHANNELS["EMG"]'s static 3-slot buffer allocation
        below) when no device is connected yet."""
        device = self._state.connected_device() if self._state is not None else None
        return device.EMG_CHANNEL_COUNT if device is not None else 3

    def enqueue(self, sensor: str, flat_raw: List[float]) -> None:
        """Stage one incoming chunk for the next `drain_and_redraw` tick.

        Unbounded by design — Pro_SDK's reference implementation drains its
        (much larger) native ring buffer completely every tick and never
        drops data; a fixed cap here previously silently truncated the
        OLDEST un-rendered chunks whenever the redraw loop fell behind even
        briefly (e.g. during a window resize), creating real gaps in the
        displayed signal. `_buffers[...]`'s own `deque(maxlen=window_len)`
        is what actually bounds memory — this staging list only exists to
        hand data across the reader-thread/Tk-main-thread boundary and is
        cleared every `drain_and_redraw` tick under normal operation.
        """
        if sensor not in self._pending or not flat_raw:
            return
        with self._lock:
            ch = self._emg_channel_count() if sensor == "EMG" else (6 if sensor in ("IMU_H", "IMU_F") else 2)
            self._rate_counts[sensor] += max(1, len(flat_raw) // max(1, ch))
            self._pending[sensor].append(flat_raw)

    @staticmethod
    def _infer_ppg_channels(flat_len: int) -> Optional[int]:
        if flat_len <= 0:
            return None
        if flat_len % 2 == 0:
            return 2
        if flat_len % 4 == 0:
            return 4
        return None

    def _extend_strided(self, group: str, flat_data: List[float], channel_count: int) -> None:
        if channel_count <= 0 or len(flat_data) % channel_count != 0:
            return
        samples_per_channel = len(flat_data) // channel_count
        for ch in range(min(channel_count, len(self._buffers[group]))):
            start = ch * samples_per_channel
            end = start + samples_per_channel
            self._buffers[group][ch].extend(flat_data[start:end])
        self._dirty.add(group)

    def _ingest_scaled(self, sensor: str, flat: List[float]) -> None:
        if sensor in ("IMU_H", "IMU_F"):
            if len(flat) % 6 != 0:
                return
            samples_per = len(flat) // 6
            for panel_suffix, ch_offset in (("ACC", 0), ("GYRO", 3)):
                group = f"{sensor}_{panel_suffix}"
                for i in range(3):
                    ch = ch_offset + i
                    chunk = flat[ch * samples_per : (ch + 1) * samples_per]
                    self._buffers[group][i].extend(chunk)
                self._dirty.add(group)
            return
        if sensor == "PPG":
            channel_count = self._infer_ppg_channels(len(flat))
            if channel_count is None:
                return
            samples_per = len(flat) // channel_count
            for ch, group in enumerate(("PPG1", "PPG2")):
                if ch >= channel_count:
                    break
                chunk = flat[ch * samples_per : (ch + 1) * samples_per]
                self._buffers[group][0].extend(chunk)
                self._dirty.add(group)
            return
        if sensor == "EMG":
            # channel_count is the REAL count (3 or 8) from the connected
            # device, not a fixed module-level constant — required so the
            # divisibility guard in _extend_strided validates against
            # Ultimate's actual 8-channel stride instead of intermittently
            # rejecting chunks whose length isn't coincidentally divisible
            # by 3. set_emg_channel_count() (called on every connect, see
            # status_ui.register_status_callbacks) keeps len(self._buffers)
            # in sync with this same count, so every channel gets plotted.
            self._extend_strided("EMG", flat, self._emg_channel_count())

    def _update_rates(self) -> Optional[str]:
        now = time.perf_counter()
        elapsed = now - self._rate_t0
        if elapsed < RATE_WINDOW_S:
            return None
        with self._lock:
            for sensor, count in self._rate_counts.items():
                self._rate_hz[sensor] = count / elapsed
                self._rate_counts[sensor] = 0
            self._rate_t0 = now
            parts = [
                f"EMG: {self._rate_hz['EMG']:.1f} Hz",
                f"IMU_H: {self._rate_hz['IMU_H']:.1f} Hz",
                f"IMU_F: {self._rate_hz['IMU_F']:.1f} Hz",
                f"PPG: {self._rate_hz['PPG']:.1f} Hz",
            ]
        return "Rates — " + " · ".join(parts)

    def drain_and_redraw(self) -> None:
        rate_text = self._update_rates()
        rate_label = self._state.rate_label if self._state is not None else None
        if rate_text is not None and rate_label is not None:
            # Continuous rate ticks — update without pop (status/sensor labels pop).
            from .anim import set_text

            set_text(rate_label, rate_text, pop=False)

        with self._lock:
            pending_copy = {k: v for k, v in self._pending.items() if v}
            for k in pending_copy:
                self._pending[k] = []

        if pending_copy:
            with self._lock:
                for sensor, chunks in pending_copy.items():
                    for raw in chunks:
                        scaled = scale_channel_blocked(sensor, raw)
                        self._ingest_scaled(sensor, scaled)

        with self._lock:
            dirty = self._dirty
            if not dirty:
                return
            self._dirty = set()
            snapshots = {
                group: [list(buf) for buf in self._buffers[group]] for group in dirty
            }

        self._ppg_frame += 1
        need_full = not self._blit_ready
        touched_panels: List[str] = []
        for panel_id in self._panel_order:
            group = self._panel_group[panel_id]
            if group not in snapshots:
                continue
            touched_panels.append(panel_id)
            channels = snapshots[group]
            lines = self._lines[panel_id]
            indices = self._panel_channel_indices[panel_id]
            ax = self._axes[panel_id]
            bounds = self._bin_bounds.get(group)
            for line_idx, ch_idx in enumerate(indices):
                if ch_idx >= len(channels) or line_idx >= len(lines):
                    continue
                lines[line_idx].set_ydata(_envelope_xy(channels[ch_idx], bounds))
            ylim = SENSOR_YLIM[group]
            if ylim is None:
                if self._ppg_frame % PPG_AUTOSCALE_EVERY == 0:
                    ys = channels[indices[0]] if indices else channels[0]
                    lo = min(ys)
                    hi = max(ys)
                    if hi > lo:
                        pad = 0.05 * (hi - lo)
                        ax.set_ylim(lo - pad, hi + pad)
                        need_full = True

        if need_full or not self._blit_ready:
            self.canvas.draw()
            self._capture_backgrounds()
            self._blit_ready = True
            return

        for panel_id in touched_panels:
            ax = self._axes[panel_id]
            bg = self._bgs.get(panel_id)
            if bg is None:
                continue
            self.canvas.restore_region(bg)
            for line in self._lines[panel_id]:
                ax.draw_artist(line)
            self.canvas.blit(ax.bbox)
        self.canvas.flush_events()
