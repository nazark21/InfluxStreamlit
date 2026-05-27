"""Default parameter sets per waveform type for channel configuration."""

from __future__ import annotations

import pandas as pd

from simulator.waveforms import WAVEFORM_OPTIONS

# Base row used when creating a new channel
BASE_ROW: dict[str, object] = {
    "enabled": True,
    "field_name": "T1--Temperature",
    "waveform": "Sine",
    "amplitude": 5.0,
    "frequency_hz": 0.5,
    "offset": 25.0,
    "phase_deg": 0.0,
    "duty": 0.5,
    "min_value": 0.0,
    "max_value": 100.0,
    "noise_std": 0.1,
    "decay_rate": 0.05,
}

WAVEFORM_DEFAULTS: dict[str, dict[str, object]] = {
    "Sine": {
        "amplitude": 5.0,
        "frequency_hz": 0.5,
        "offset": 25.0,
        "phase_deg": 0.0,
        "min_value": 15.0,
        "max_value": 35.0,
    },
    "Cosine": {
        "amplitude": 5.0,
        "frequency_hz": 0.5,
        "offset": 25.0,
        "phase_deg": 0.0,
        "min_value": 15.0,
        "max_value": 35.0,
    },
    "Square": {
        "amplitude": 10.0,
        "frequency_hz": 0.25,
        "offset": 0.0,
        "phase_deg": 0.0,
        "min_value": -10.0,
        "max_value": 10.0,
    },
    "Triangle": {
        "amplitude": 8.0,
        "frequency_hz": 0.4,
        "offset": 20.0,
        "phase_deg": 0.0,
        "min_value": 12.0,
        "max_value": 28.0,
    },
    "Sawtooth": {
        "amplitude": 6.0,
        "frequency_hz": 0.3,
        "offset": 10.0,
        "phase_deg": 0.0,
        "min_value": 4.0,
        "max_value": 16.0,
    },
    "Reverse sawtooth": {
        "amplitude": 6.0,
        "frequency_hz": 0.3,
        "offset": 10.0,
        "phase_deg": 0.0,
        "min_value": 4.0,
        "max_value": 16.0,
    },
    "Pulse": {
        "amplitude": 12.0,
        "frequency_hz": 1.0,
        "offset": 0.0,
        "duty": 0.25,
        "min_value": 0.0,
        "max_value": 12.0,
    },
    "Constant": {
        "amplitude": 0.0,
        "frequency_hz": 0.5,
        "offset": 42.0,
        "min_value": 42.0,
        "max_value": 42.0,
    },
    "Uniform noise": {
        "amplitude": 5.0,
        "frequency_hz": 0.5,
        "offset": 25.0,
        "min_value": 20.0,
        "max_value": 30.0,
    },
    "Gaussian noise": {
        "amplitude": 3.0,
        "frequency_hz": 0.5,
        "offset": 50.0,
        "noise_std": 0.15,
        "min_value": 40.0,
        "max_value": 60.0,
    },
    "Random walk": {
        "amplitude": 2.0,
        "frequency_hz": 0.5,
        "offset": 50.0,
        "min_value": 0.0,
        "max_value": 100.0,
    },
    "Ramp": {
        "amplitude": 100.0,
        "frequency_hz": 0.05,
        "offset": 0.0,
        "min_value": 0.0,
        "max_value": 100.0,
    },
    "Exponential decay": {
        "amplitude": 100.0,
        "frequency_hz": 0.5,
        "offset": 0.0,
        "decay_rate": 0.08,
        "min_value": 0.0,
        "max_value": 100.0,
    },
    "Chirp (sweep)": {
        "amplitude": 5.0,
        "frequency_hz": 0.2,
        "offset": 0.0,
        "min_value": -6.0,
        "max_value": 6.0,
    },
    "Heartbeat": {
        "amplitude": 80.0,
        "frequency_hz": 1.2,
        "offset": 0.0,
        "min_value": 0.0,
        "max_value": 80.0,
    },
    "CPU usage %": {
        "amplitude": 0.0,
        "frequency_hz": 0.5,
        "offset": 0.0,
        "min_value": 0.0,
        "max_value": 100.0,
    },
    "Memory usage %": {
        "amplitude": 0.0,
        "frequency_hz": 0.5,
        "offset": 0.0,
        "min_value": 0.0,
        "max_value": 100.0,
    },
    "Network send (KB/s)": {
        "amplitude": 0.0,
        "frequency_hz": 0.5,
        "offset": 0.0,
        "min_value": 0.0,
        "max_value": 10_000.0,
    },
    "Network recv (KB/s)": {
        "amplitude": 0.0,
        "frequency_hz": 0.5,
        "offset": 0.0,
        "min_value": 0.0,
        "max_value": 10_000.0,
    },
}

NUMERIC_COLUMNS = [
    "amplitude",
    "frequency_hz",
    "offset",
    "phase_deg",
    "duty",
    "min_value",
    "max_value",
    "noise_std",
    "decay_rate",
]


def defaults_for_waveform(waveform: str) -> dict[str, object]:
    row = {**BASE_ROW, **WAVEFORM_DEFAULTS.get(waveform, {})}
    row["waveform"] = waveform
    return row


def apply_defaults_to_row(row: dict | pd.Series, waveform: str | None = None) -> dict:
    """Apply waveform defaults to a single channel row (keeps field_name / enabled if set)."""
    w = waveform or str(row.get("waveform") or "Sine")
    base = defaults_for_waveform(w)
    out = {**base}
    if row.get("field_name"):
        out["field_name"] = row.get("field_name")
    if "enabled" in row and row.get("enabled") is not None:
        out["enabled"] = bool(row.get("enabled"))
    out["waveform"] = w
    return out


def normalize_channels_df(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all columns exist and NaN/None numeric cells have safe defaults."""
    if df is None or df.empty:
        return pd.DataFrame([BASE_ROW.copy()])

    out = df.copy()
    for col in BASE_ROW:
        if col not in out.columns:
            out[col] = BASE_ROW[col]

    for idx in out.index:
        w = str(out.at[idx, "waveform"] or "Sine")
        if w not in WAVEFORM_OPTIONS:
            w = "Sine"
            out.at[idx, "waveform"] = w
        defaults = defaults_for_waveform(w)
        for key in list(BASE_ROW.keys()):
            val = out.at[idx, key]
            if key == "field_name":
                if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() == "":
                    out.at[idx, key] = defaults.get("field_name", "T1--Channel")
                continue
            if key == "enabled":
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    out.at[idx, key] = True
                continue
            if key == "waveform":
                continue
            if val is None or (isinstance(val, float) and pd.isna(val)):
                out.at[idx, key] = defaults[key]

    return out[list(BASE_ROW.keys())]


def apply_waveform_changes(prev: pd.DataFrame | None, curr: pd.DataFrame) -> pd.DataFrame:
    """When waveform changes in a row, refill that row's parameters from presets."""
    curr = normalize_channels_df(curr)
    if prev is None:
        return curr

    prev = normalize_channels_df(prev)
    out = curr.copy().reset_index(drop=True)
    prev = prev.reset_index(drop=True)
    n = min(len(prev), len(out))
    for i in range(n):
        old_w = str(prev.iloc[i]["waveform"])
        new_w = str(out.iloc[i]["waveform"])
        if old_w != new_w:
            merged = apply_defaults_to_row(out.iloc[i], new_w)
            for key, val in merged.items():
                out.at[i, key] = val
    return out
