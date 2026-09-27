"""Sensor configuration panel (EMG / IMU / PPG)."""

from __future__ import annotations

from typing import List

import tkinter as tk
from tkinter import ttk

from mudra_sdk.models.enums import ProEMGODR, EmgRes, IMUODR, PPGODR
from mudra_sdk.models.mudra_device import MudraDevice

from ..state import AppState
from ..widgets import combo, config_row, entry, pin_status, scrollable_tab

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


def _set_chart_odr(state: AppState, panels: List[str], hz: int) -> None:
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


def build_sensor_config_ui(parent: tk.Widget, state: AppState) -> None:
    """EMG / H_IMU / F_IMU / PPG — Get Status pinned on every tab."""
    notebook = ttk.Notebook(parent)
    notebook.pack(fill=tk.BOTH, expand=True)

    # ---- EMG ----
    emg_bar, emg = scrollable_tab(notebook, "EMG")
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
        bar, form = scrollable_tab(notebook, title)
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

    # ---- PPG ----
    ppg_bar, ppg = scrollable_tab(notebook, "PPG")
    state.config_status_labels.setdefault("PPG", []).append(
        pin_status(
            ppg_bar, "PPG", lambda: state.run_device("PPG_STATUS?", lambda d: d.get_ppg_status())
        )
    )
    # ODR is covered by the pinned status above (PpgStatus, re-seeded on
    # every change) -- no Set/Get here, just apply on selection.
    mid = config_row(ppg, "ODR Hz")
    ppg_odr_box = combo(mid, PPG_ODR_VALUES, PPGODR.ppgOdr100.value_int)
    ppg_odr_box.pack(side=tk.LEFT)

    def _set_ppg_odr(_evt=None) -> None:
        odr = PPGODR.from_value(int(ppg_odr_box.get()))
        if odr is None:
            return
        _set_chart_odr(state, ["PPG1", "PPG2"], odr.value_int)
        state.run_device("PPG_ODR", lambda d: d.set_ppg_odr(odr))

    ppg_odr_box.bind("<<ComboboxSelected>>", _set_ppg_odr)

    # Everything below isn't part of PpgStatus, so there's no push to show
    # its current value -- these keep Get, but still apply on change (combo
    # selection, or Enter in a text field), no Set button.
    mid = config_row(ppg, "DEC", get_fn=lambda: state.run_device("PPG_DEC?", lambda d: d.get_ppg_dec()))
    dec_box = combo(mid, PPG_DEC_VALUES, 4)
    dec_box.pack(side=tk.LEFT)
    dec_box.bind(
        "<<ComboboxSelected>>",
        lambda _evt: state.run_device("PPG_DEC", lambda d: d.set_ppg_dec(int(dec_box.get()))),
    )

    mid = config_row(
        ppg,
        "LED ch/d1/d2",
        get_fn=lambda: state.run_device(
            "PPG_LED?", lambda d: d.get_ppg_led(int(led_ch.get()))
        ),
    )
    led_ch = entry(mid, "0", 3)
    led_d1 = entry(mid, "0", 3)
    led_d2 = entry(mid, "0", 3)
    for e in (led_ch, led_d1, led_d2):
        e.pack(side=tk.LEFT, padx=(0, 3))
    _apply_on_enter(
        (led_ch, led_d1, led_d2),
        lambda: state.run_device(
            "PPG_LED",
            lambda d: d.set_ppg_led(int(led_ch.get()), int(led_d1.get()), int(led_d2.get())),
        ),
    )

    mid = config_row(
        ppg,
        "TIA ch/rf/cf",
        get_fn=lambda: state.run_device(
            "PPG_TIA?", lambda d: d.get_ppg_tia(int(tia_ch.get()))
        ),
    )
    tia_ch = entry(mid, "0", 3)
    tia_rf = entry(mid, "0", 3)
    tia_cf = entry(mid, "0", 3)
    for e in (tia_ch, tia_rf, tia_cf):
        e.pack(side=tk.LEFT, padx=(0, 3))
    _apply_on_enter(
        (tia_ch, tia_rf, tia_cf),
        lambda: state.run_device(
            "PPG_TIA",
            lambda d: d.set_ppg_tia(int(tia_ch.get()), int(tia_rf.get()), int(tia_cf.get())),
        ),
    )

    mid = config_row(ppg, "PRPCT", get_fn=lambda: state.run_device("PPG_PRPCT?", lambda d: d.get_ppg_prpct()))
    prpct = entry(mid, "1280", 8)
    prpct.pack(side=tk.LEFT)
    _apply_on_enter(
        (prpct,),
        lambda: state.run_device("PPG_PRPCT", lambda d: d.set_ppg_prpct(int(prpct.get(), 0))),
    )

    # Pure action, not a value to apply on change -- keeps its button.
    config_row(
        ppg, "CLEAR", set_fn=lambda: state.run_device("PPG_CLEAR", lambda d: d.ppg_clear())
    )

    mid = config_row(
        ppg,
        "SRC ch/led/pd",
        get_fn=lambda: state.run_device(
            "PPG_SRC?", lambda d: d.get_ppg_src(int(src_ch.get()))
        ),
    )
    src_ch = entry(mid, "0", 3)
    src_led = entry(mid, "1", 3)
    src_pd = entry(mid, "1", 3)
    for e in (src_ch, src_led, src_pd):
        e.pack(side=tk.LEFT, padx=(0, 3))
    _apply_on_enter(
        (src_ch, src_led, src_pd),
        lambda: state.run_device(
            "PPG_SRC",
            lambda d: d.set_ppg_src(int(src_ch.get()), int(src_led.get()), int(src_pd.get())),
        ),
    )
