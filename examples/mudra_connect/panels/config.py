"""Sensor configuration panel (EMG / IMU / PPG_H / PPG_F)."""

from __future__ import annotations

from typing import List

import tkinter as tk
from tkinter import ttk

from mudra_sdk.models.enums import ProEMGODR, EmgRes, IMUODR, PPGODR
from mudra_sdk.models.mudra_device import MudraDevice

from ..state import DeviceState
from ..theme import BG_PANEL, FG_MUTED, FONT_SMALL, px
from ..widgets import auto_wrap, combo, config_row, config_tab, entry, pin_status

# Initial/fallback EMG ODR options — Pro's set, matching MudraDevice's own
# Pro-defaulted EMG_ODR_ENUM. Re-populated per-device in
# status_ui.register_status_callbacks() once a device (Pro or Ultimate,
# different AFEs with different discrete rates) actually connects.
EMG_ODR_VALUES = [e.value_int for e in ProEMGODR]
EMG_RES_VALUES = [e.bits for e in EmgRes]
IMU_ODR_VALUES = [e.value_int for e in IMUODR]
PPG_ODR_VALUES = [e.value_int for e in PPGODR]
IMU_ACC_VALUES = [2, 4, 8, 16]
IMU_GYR_VALUES = [125, 250, 500, 1000, 2000]
IMU_BW_VALUES = [2, 4]
IMU_AVG_VALUES = [1, 2, 4, 8, 16, 32, 64]
PPG_DEC_VALUES = [1, 2, 4, 8, 16]
PPG_LOCAL_CHANNELS = [0, 1]  # each PPG sensor's own channels (PPG_H: AFE 0-1, PPG_F: 2-3)


def _set_chart_odr(state: DeviceState, panels: List[str], hz: int) -> None:
    if state.charts is None or hz <= 0:
        return
    for panel in panels:
        state.charts.set_odr(panel, hz)


def _apply_on_enter(entries: List[ttk.Entry], callback) -> None:
    """Fire callback on Enter in any of these entries -- the free-text
    equivalent of a combobox's <<ComboboxSelected>> apply-on-change. There's
    no discrete 'value settled' event for a text field, so Enter is it
    (deliberately not FocusOut too -- tabbing between a row's fields would
    fire once per field with the others still at their stale/default value)."""
    for e in entries:
        e.bind("<Return>", lambda _evt: callback())


def build_sensor_config_ui(parent: tk.Widget, state: DeviceState) -> None:
    """EMG / H_IMU / F_IMU / PPG_H / PPG_F — Get Status pinned on every tab."""
    notebook = ttk.Notebook(parent, style="Inner.TNotebook")
    notebook.pack(fill=tk.BOTH, expand=True)

    # ---- EMG ----
    emg_bar, emg = config_tab(notebook, "EMG")
    state.config_status_labels.setdefault("EMG", []).append(
        pin_status(
            emg_bar, "EMG", lambda: state.run_device("EMG_STATUS?", lambda d: d.get_emg_status())
        )
    )

    # ODR/RES are covered by the pinned status above (EmgStatus carries both,
    # and register_status_callbacks() re-seeds it on every change) -- no
    # Set/Get here, just apply on selection.
    mid = config_row(emg, "ODR Hz")
    emg_odr = combo(mid, EMG_ODR_VALUES, ProEMGODR.emgOdr200.value_int)
    emg_odr.pack(side=tk.LEFT)
    # build_sensor_config_ui() runs once per host tab (Explorer, Ping) —
    # append, don't overwrite, so status_ui's refresh reaches every instance.
    state.emg_odr_combos.append(emg_odr)

    def _set_emg_odr(_evt=None) -> None:
        device = state.connected_device()
        odr_enum = device.EMG_ODR_ENUM if device is not None else ProEMGODR
        odr = odr_enum.from_value(int(emg_odr.get()))
        if odr is None:
            return
        _set_chart_odr(state, ["EMG"], odr.value_int)
        state.run_device("EMG_ODR", lambda d: d.set_emg_odr(odr))

    emg_odr.bind("<<ComboboxSelected>>", _set_emg_odr)

    mid = config_row(emg, "RES bits")
    emg_res = combo(mid, EMG_RES_VALUES, EmgRes.emgRes16.bits)
    emg_res.pack(side=tk.LEFT)

    def _set_emg_res(_evt=None) -> None:
        res = EmgRes.from_bits(int(emg_res.get()))
        if res is None:
            return
        state.run_device("EMG_RES", lambda d: d.set_emg_res(res))

    emg_res.bind("<<ComboboxSelected>>", _set_emg_res)

    config_row(
        emg,
        "RES_MAX",
        get_fn=lambda: state.run_device("EMG_RES_MAX?", lambda d: d.get_emg_res_max()),
    )

    # ---- IMU tabs ----
    def _imu_tab(title: str, prefix: str) -> None:
        bar, form = config_tab(notebook, title)
        status_fn = (
            MudraDevice.get_h_imu_status
            if prefix == "h_imu"
            else MudraDevice.get_f_imu_status
        )
        pin = pin_status(
            bar,
            title,
            lambda sf=status_fn, t=title: state.run_device(f"{t}_STATUS?", sf),
        )
        state.config_status_labels.setdefault(title, []).append(pin)

        set_odr = getattr(MudraDevice, f"set_{prefix}_odr")
        get_odr = getattr(MudraDevice, f"get_{prefix}_odr")
        set_acc = getattr(MudraDevice, f"set_{prefix}_acc")
        get_acc = getattr(MudraDevice, f"get_{prefix}_acc")
        set_gyr = getattr(MudraDevice, f"set_{prefix}_gyr")
        get_gyr = getattr(MudraDevice, f"get_{prefix}_gyr")
        get_acc_res = getattr(MudraDevice, f"get_{prefix}_acc_res")
        get_gyr_res = getattr(MudraDevice, f"get_{prefix}_gyr_res")
        set_acc_bw = getattr(MudraDevice, f"set_{prefix}_acc_bw")
        get_acc_bw = getattr(MudraDevice, f"get_{prefix}_acc_bw")
        set_gyr_bw = getattr(MudraDevice, f"set_{prefix}_gyr_bw")
        get_gyr_bw = getattr(MudraDevice, f"get_{prefix}_gyr_bw")
        set_acc_avg = getattr(MudraDevice, f"set_{prefix}_acc_avg")
        get_acc_avg = getattr(MudraDevice, f"get_{prefix}_acc_avg")
        set_gyr_avg = getattr(MudraDevice, f"set_{prefix}_gyr_avg")
        get_gyr_avg = getattr(MudraDevice, f"get_{prefix}_gyr_avg")

        sensor_key = "IMU_H" if prefix == "h_imu" else "IMU_F"
        odr_panels = [f"{sensor_key}_ACC", f"{sensor_key}_GYRO"]

        # ODR/ACC/GYR are covered by the pinned status above (ImuStatus
        # carries all three, re-seeded on every change) -- no Set/Get here,
        # just apply on selection.
        mid = config_row(form, "ODR Hz")
        odr_box = combo(mid, IMU_ODR_VALUES, IMUODR.imuHOdr100.value_int)
        odr_box.pack(side=tk.LEFT)

        def _set_imu_odr(_evt=None) -> None:
            value = IMUODR.from_value(int(odr_box.get()))
            if value is None:
                return
            _set_chart_odr(state, odr_panels, value.value_int)
            state.run_device(f"{title}_ODR", lambda d: set_odr(d, value))

        odr_box.bind("<<ComboboxSelected>>", _set_imu_odr)

        mid = config_row(form, "ACC g")
        acc_box = combo(mid, IMU_ACC_VALUES, 4)
        acc_box.pack(side=tk.LEFT)
        acc_box.bind(
            "<<ComboboxSelected>>",
            lambda _evt: state.run_device(
                f"{title}_ACC", lambda d: set_acc(d, int(acc_box.get()))
            ),
        )

        mid = config_row(form, "GYR dps")
        gyr_box = combo(mid, IMU_GYR_VALUES, 500)
        gyr_box.pack(side=tk.LEFT)
        gyr_box.bind(
            "<<ComboboxSelected>>",
            lambda _evt: state.run_device(
                f"{title}_GYR", lambda d: set_gyr(d, int(gyr_box.get()))
            ),
        )

        config_row(
            form,
            "ACC_RES",
            get_fn=lambda: state.run_device(f"{title}_ACC_RES?", lambda d: get_acc_res(d)),
        )
        config_row(
            form,
            "GYR_RES",
            get_fn=lambda: state.run_device(f"{title}_GYR_RES?", lambda d: get_gyr_res(d)),
        )

        # BW/AVG aren't part of ImuStatus, so there's no push to show their
        # current value -- keep Get, but still apply on selection, no Set.
        mid = config_row(
            form,
            "ACC_BW",
            get_fn=lambda: state.run_device(f"{title}_ACC_BW?", lambda d: get_acc_bw(d)),
        )
        acc_bw_box = combo(mid, IMU_BW_VALUES, 2)
        acc_bw_box.pack(side=tk.LEFT)
        acc_bw_box.bind(
            "<<ComboboxSelected>>",
            lambda _evt: state.run_device(
                f"{title}_ACC_BW", lambda d: set_acc_bw(d, int(acc_bw_box.get()))
            ),
        )

        mid = config_row(
            form,
            "GYR_BW",
            get_fn=lambda: state.run_device(f"{title}_GYR_BW?", lambda d: get_gyr_bw(d)),
        )
        gyr_bw_box = combo(mid, IMU_BW_VALUES, 2)
        gyr_bw_box.pack(side=tk.LEFT)
        gyr_bw_box.bind(
            "<<ComboboxSelected>>",
            lambda _evt: state.run_device(
                f"{title}_GYR_BW", lambda d: set_gyr_bw(d, int(gyr_bw_box.get()))
            ),
        )

        mid = config_row(
            form,
            "ACC_AVG",
            get_fn=lambda: state.run_device(f"{title}_ACC_AVG?", lambda d: get_acc_avg(d)),
        )
        acc_avg_box = combo(mid, IMU_AVG_VALUES, 1)
        acc_avg_box.pack(side=tk.LEFT)
        acc_avg_box.bind(
            "<<ComboboxSelected>>",
            lambda _evt: state.run_device(
                f"{title}_ACC_AVG", lambda d: set_acc_avg(d, int(acc_avg_box.get()))
            ),
        )

        mid = config_row(
            form,
            "GYR_AVG",
            get_fn=lambda: state.run_device(f"{title}_GYR_AVG?", lambda d: get_gyr_avg(d)),
        )
        gyr_avg_box = combo(mid, IMU_AVG_VALUES, 1)
        gyr_avg_box.pack(side=tk.LEFT)
        gyr_avg_box.bind(
            "<<ComboboxSelected>>",
            lambda _evt: state.run_device(
                f"{title}_GYR_AVG", lambda d: set_gyr_avg(d, int(gyr_avg_box.get()))
            ),
        )

    _imu_tab("H_IMU", "h_imu")
    _imu_tab("F_IMU", "f_imu")

    # ---- PPG tabs (PPG_H = hand, AFE ch 0-1; PPG_F = finger/ring, AFE ch 2-3) ----
    # One AFE chip serves both: ODR, DEC and PRPCT are chip-wide (setting
    # them on either tab changes both sensors); LED/TIA/SRC take the
    # sensor's local channel 0-1. SRC's LED/PD numbers are absolute (TX1-8,
    # IN1-4), so each tab defaults to its own optics: band ch0 = TX1/IN1,
    # ring ch0 = TX5/IN4.
    ppg_src_defaults = {"ppg_h": ("1", "1"), "ppg_f": ("5", "4")}
    ppg_notes = {
        "ppg_h": "Band optics (AFE ch 0-1).",
        "ppg_f": "Ring optics (AFE ch 2-3) -- needs the ring connected.",
    }

    def _ppg_tab(title: str, prefix: str) -> None:
        bar, form = config_tab(notebook, title)
        get_status = getattr(MudraDevice, f"get_{prefix}_status")
        state.config_status_labels.setdefault(title, []).append(
            pin_status(bar, title, lambda: state.run_device(f"{title}_STATUS?", get_status))
        )
        note = tk.Label(
            form,
            text=(
                f"{ppg_notes[prefix]} ODR, DEC and PRPCT are shared with the other "
                "PPG tab (one chip). Config is rejected while PPG_H or PPG_F streams."
            ),
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=FONT_SMALL,
            justify=tk.LEFT,
            anchor="w",
            # Starting wraplength only; auto_wrap() follows the real width.
            wraplength=px(240),
        )
        note.pack(fill=tk.X, pady=(0, 4))
        auto_wrap(note)

        set_odr = getattr(MudraDevice, f"set_{prefix}_odr")
        set_dec = getattr(MudraDevice, f"set_{prefix}_dec")
        get_dec = getattr(MudraDevice, f"get_{prefix}_dec")
        set_led = getattr(MudraDevice, f"set_{prefix}_led")
        get_led = getattr(MudraDevice, f"get_{prefix}_led")
        set_tia = getattr(MudraDevice, f"set_{prefix}_tia")
        get_tia = getattr(MudraDevice, f"get_{prefix}_tia")
        set_prpct = getattr(MudraDevice, f"set_{prefix}_prpct")
        get_prpct = getattr(MudraDevice, f"get_{prefix}_prpct")
        clear = getattr(MudraDevice, f"{prefix}_clear")
        set_src = getattr(MudraDevice, f"set_{prefix}_src")
        get_src = getattr(MudraDevice, f"get_{prefix}_src")

        # ODR is covered by the pinned status above (PpgStatus, re-seeded on
        # every change) -- no Set/Get here, just apply on selection. It's
        # chip-wide, so both PPG sensors' charts follow it.
        mid = config_row(form, "ODR Hz")
        # Firmware boots PPG at 25 Hz; the status push re-syncs this anyway.
        odr_box = combo(mid, PPG_ODR_VALUES, PPGODR.ppgOdr25.value_int)
        odr_box.pack(side=tk.LEFT)
        state.ppg_odr_combos.append(odr_box)

        def _set_ppg_odr(_evt=None) -> None:
            odr = PPGODR.from_value(int(odr_box.get()))
            if odr is None:
                return
            for other in state.ppg_odr_combos:
                other.set(str(odr.value_int))
            _set_chart_odr(
                state, ["PPG_H_CH0", "PPG_H_CH1", "PPG_F_CH0", "PPG_F_CH1"], odr.value_int
            )
            state.run_device(f"{title}_ODR", lambda d: set_odr(d, odr))

        odr_box.bind("<<ComboboxSelected>>", _set_ppg_odr)

        # Everything below isn't part of PpgStatus, so there's no push to show
        # its current value -- these keep Get, but still apply on change (combo
        # selection, or Enter in a text field), no Set button.
        mid = config_row(
            form, "DEC", get_fn=lambda: state.run_device(f"{title}_DEC?", lambda d: get_dec(d))
        )
        dec_box = combo(mid, PPG_DEC_VALUES, 4)
        dec_box.pack(side=tk.LEFT)
        dec_box.bind(
            "<<ComboboxSelected>>",
            lambda _evt: state.run_device(f"{title}_DEC", lambda d: set_dec(d, int(dec_box.get()))),
        )

        def _channel_row(label: str, name: str, getter, setter, defaults) -> None:
            # Channel is a 0/1 picker: each PPG sensor has exactly two local
            # channels, so a free-text field only invited out-of-range input.
            fields: List[ttk.Entry] = []
            mid = config_row(
                form,
                label,
                get_fn=lambda: state.run_device(
                    f"{title}_{name}?", lambda d: getter(d, int(ch_box.get()))
                ),
            )
            ch_box = combo(mid, PPG_LOCAL_CHANNELS, 0, width=2)
            ch_box.pack(side=tk.LEFT, padx=(0, 3))
            for default in defaults:
                e = entry(mid, default, 3)
                e.pack(side=tk.LEFT, padx=(0, 3))
                fields.append(e)
            _apply_on_enter(
                fields,
                lambda: state.run_device(
                    f"{title}_{name}",
                    lambda d: setter(d, int(ch_box.get()), *(int(f.get()) for f in fields)),
                ),
            )

        _channel_row("LED ch/d1/d2", "LED", get_led, set_led, ("0", "0"))
        _channel_row("TIA ch/rf/cf", "TIA", get_tia, set_tia, ("0", "0"))

        mid = config_row(
            form, "PRPCT", get_fn=lambda: state.run_device(f"{title}_PRPCT?", lambda d: get_prpct(d))
        )
        prpct = entry(mid, "1280", 8)
        prpct.pack(side=tk.LEFT)
        _apply_on_enter(
            (prpct,),
            lambda: state.run_device(f"{title}_PRPCT", lambda d: set_prpct(d, int(prpct.get(), 0))),
        )

        # Pure action, not a value to apply on change -- keeps its button.
        config_row(
            form, "CLEAR", set_fn=lambda: state.run_device(f"{title}_CLEAR", lambda d: clear(d))
        )

        _channel_row("SRC ch/led/pd", "SRC", get_src, set_src, ppg_src_defaults[prefix])

    _ppg_tab("PPG_H", "ppg_h")
    _ppg_tab("PPG_F", "ppg_f")
