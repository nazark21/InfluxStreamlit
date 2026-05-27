"""
InfluxDB data simulator — Streamlit UI.

Run: streamlit run streamlit_app.py
"""

from __future__ import annotations

import time
from collections import deque

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from simulator.channel_defaults import (
    BASE_ROW,
    apply_defaults_to_row,
    apply_waveform_changes,
    defaults_for_waveform,
    normalize_channels_df,
)
from simulator.credentials_store import (
    InfluxCredentials,
    default_credentials,
    delete_user_credentials,
    get_user_credentials,
    resolve_credentials,
    save_user_credentials,
)
from simulator.engine import SimulationConfig, SimulationEngine
from simulator.waveforms import INTERVAL_OPTIONS, WAVEFORM_OPTIONS, ChannelConfig, preview_series

st.set_page_config(
    page_title="InfluxStreamlit",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.2rem; max-width: 1400px; }
    div[data-testid="stMetric"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.5rem 0.75rem;
    }
    .app-header {
        padding: 0.25rem 0 1rem 0;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

PRESETS: dict[str, list[dict]] = {
    "simulate11 (4 sensors)": [
        {"field_name": "T1--Temperature", "waveform": "Uniform noise", "min_value": 20, "max_value": 30, "amplitude": 5},
        {"field_name": "T1--Humidity", "waveform": "Uniform noise", "min_value": 40, "max_value": 60, "amplitude": 10},
        {"field_name": "T1--Pressure", "waveform": "Uniform noise", "min_value": 100, "max_value": 120, "amplitude": 10},
        {"field_name": "T1--Flow", "waveform": "Uniform noise", "min_value": 100, "max_value": 120, "amplitude": 10},
    ],
    "simulate4 (DAQ sample)": [
        {"field_name": "T1--Volts", "waveform": "Uniform noise", "min_value": 12.95, "max_value": 13.15, "amplitude": 0.1},
        {"field_name": "T1--Amps", "waveform": "Uniform noise", "min_value": 1.70, "max_value": 1.77, "amplitude": 0.04},
        {"field_name": "T1--Steady_State_Temp_C", "waveform": "Uniform noise", "min_value": 195, "max_value": 205, "amplitude": 5},
        {"field_name": "T1--Temperature_C", "waveform": "Sine", "amplitude": 10, "offset": 200, "frequency_hz": 0.1},
        {"field_name": "T1--Voltage_V", "waveform": "Sine", "amplitude": 0.2, "offset": 13, "frequency_hz": 0.2},
    ],
    "Waveform showcase": [
        {"field_name": "Sine", "waveform": "Sine"},
        {"field_name": "Square", "waveform": "Square"},
        {"field_name": "Triangle", "waveform": "Triangle"},
        {"field_name": "Sawtooth", "waveform": "Sawtooth"},
        {"field_name": "Chirp", "waveform": "Chirp (sweep)"},
    ],
}


def _safe_float(value: object, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, float) and pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _init_state() -> None:
    defaults = {
        "engine": SimulationEngine(),
        "log_lines": deque(maxlen=300),
        "user_id": "",
        "use_custom_creds": False,
        "channels_df": normalize_channels_df(pd.DataFrame([BASE_ROW.copy()])),
        "channels_df_prev": None,
        "measurement": "Test_connect",
        "run_id": "RUN3638",
        "interval_label": "1 s",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _df_to_channels(df: pd.DataFrame) -> list[ChannelConfig]:
    df = normalize_channels_df(df)
    channels: list[ChannelConfig] = []
    for _, row in df.iterrows():
        if not bool(row.get("enabled", True)):
            continue
        name = str(row.get("field_name", "")).strip()
        if not name:
            continue
        channels.append(
            ChannelConfig(
                enabled=True,
                field_name=name,
                waveform=str(row.get("waveform", "Sine")),
                amplitude=_safe_float(row.get("amplitude"), 1.0),
                frequency_hz=_safe_float(row.get("frequency_hz"), 0.5),
                offset=_safe_float(row.get("offset"), 0.0),
                phase_deg=_safe_float(row.get("phase_deg"), 0.0),
                duty=_safe_float(row.get("duty"), 0.5),
                min_value=_safe_float(row.get("min_value"), 0.0),
                max_value=_safe_float(row.get("max_value"), 100.0),
                noise_std=_safe_float(row.get("noise_std"), 0.1),
                decay_rate=_safe_float(row.get("decay_rate"), 0.05),
            )
        )
    return channels


def _sync_logs(engine: SimulationEngine) -> None:
    for line in engine.drain_logs():
        st.session_state.log_lines.appendleft(line)


def _apply_preset(name: str) -> None:
    rows = []
    for raw in PRESETS[name]:
        row = apply_defaults_to_row(raw, str(raw.get("waveform", "Sine")))
        rows.append(row)
    st.session_state.channels_df = normalize_channels_df(pd.DataFrame(rows))
    st.session_state.channels_df_prev = st.session_state.channels_df.copy()


_init_state()
_sync_logs(st.session_state.engine)
engine: SimulationEngine = st.session_state.engine
running = engine.is_running()

# —— Header ——
st.markdown('<div class="app-header">', unsafe_allow_html=True)
h1, h2 = st.columns([3, 1])
with h1:
    st.title("InfluxStreamlit")
    st.caption("Professional InfluxDB telemetry simulator for Testruns · measurement, RunID, multi-field waveforms")
with h2:
    status_label = "● Live" if running else "○ Idle"
    st.metric("Status", status_label)
st.markdown("</div>", unsafe_allow_html=True)

# —— Sidebar ——
with st.sidebar:
    st.subheader("Connection")
    st.session_state.user_id = st.text_input(
        "User ID",
        value=st.session_state.user_id,
        placeholder="For private saved credentials",
    )

    use_custom = st.toggle(
        "Use my Influx credentials (MongoDB)",
        value=st.session_state.use_custom_creds,
    )
    st.session_state.use_custom_creds = use_custom

    defaults = default_credentials()
    active = resolve_credentials(st.session_state.user_id, use_custom)
    if not defaults.is_complete():
        st.warning("Set `INFLUXDB_*` in `.env` or save custom credentials.")

    with st.expander("Connection details", expanded=False):
        st.write(f"**URL**  \n{active.url or '—'}")
        st.write(f"**Org**  \n{active.org or '—'}")
        st.write(f"**Bucket**  \n{active.bucket or '—'}")
        if active.token:
            st.write(f"**Token**  \n••••{active.token[-6:]}")

    with st.expander("Manage credentials", expanded=False):
        saved = get_user_credentials(st.session_state.user_id) if st.session_state.user_id.strip() else None
        c_url = st.text_input("URL", value=active.url, key="cred_url")
        c_org = st.text_input("Org", value=active.org, key="cred_org")
        c_bucket = st.text_input("Bucket", value=active.bucket, key="cred_bucket")
        c_token = st.text_input(
            "Token",
            value="",
            type="password",
            key="cred_token",
            placeholder="Leave blank to keep existing token",
        )
        c_ssl = st.checkbox("Verify SSL", value=active.verify_ssl, key="cred_ssl")

        b1, b2 = st.columns(2)
        if b1.button("Save", width="stretch"):
            try:
                token_to_save = c_token.strip() or (saved.token if saved else "")
                save_user_credentials(
                    st.session_state.user_id,
                    InfluxCredentials(c_url, token_to_save, c_org, c_bucket, c_ssl),
                )
                st.success("Saved")
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))
        if b2.button("Delete", width="stretch"):
            try:
                delete_user_credentials(st.session_state.user_id)
                st.info("Removed")
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))

    st.divider()
    st.subheader("Stream")

    if running and engine.status.started_at:
        elapsed = int(time.monotonic() - engine.status.started_at)
        c1, c2, c3 = st.columns(3)
        c1.metric("Writes", engine.status.writes)
        c2.metric("Errors", engine.status.errors)
        c3.metric("Uptime", f"{elapsed}s")

    if st.button("Start stream", type="primary", disabled=running, width="stretch"):
        try:
            creds = resolve_credentials(st.session_state.user_id, st.session_state.use_custom_creds)
            channels = _df_to_channels(st.session_state.channels_df)
            config = SimulationConfig(
                measurement=st.session_state.measurement.strip(),
                run_id=st.session_state.run_id.strip(),
                interval_s=INTERVAL_OPTIONS[st.session_state.interval_label],
                channels=channels,
                credentials=creds,
            )
            engine.start(config)
            st.session_state.log_lines.appendleft(
                f"{time.strftime('%H:%M:%S')}  Started {config.measurement} · RunID={config.run_id}"
            )
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))

    if st.button("Stop stream", disabled=not running, width="stretch"):
        engine.stop()
        st.session_state.log_lines.appendleft(f"{time.strftime('%H:%M:%S')}  Stopped")
        st.rerun()

# —— Main: configuration ——
col_target, col_channels = st.columns([1, 2], gap="large")

with col_target:
    st.subheader("Write target")
    st.session_state.measurement = st.text_input("Measurement", value=st.session_state.measurement)
    st.session_state.run_id = st.text_input("RunID tag", value=st.session_state.run_id)
    labels = list(INTERVAL_OPTIONS.keys())
    idx = labels.index(st.session_state.interval_label) if st.session_state.interval_label in labels else 4
    st.session_state.interval_label = st.selectbox("Interval", labels, index=idx)

    st.markdown("**Presets**")
    preset = st.selectbox("Template", ["—"] + list(PRESETS.keys()), label_visibility="collapsed")
    if st.button("Load preset", width="stretch") and preset != "—":
        _apply_preset(preset)
        st.rerun()

with col_channels:
    st.subheader("Channels")
    st.caption("Changing **Waveform** auto-fills recommended parameters. Empty numeric cells are normalized on save.")

    q1, q2, q3, q4 = st.columns(4)
    with q1:
        new_field = st.text_input("New field name", value="T1--Channel", label_visibility="collapsed", placeholder="Field name")
    with q2:
        new_wave = st.selectbox("Waveform", WAVEFORM_OPTIONS, index=0, label_visibility="collapsed")
    with q3:
        if st.button("Add channel", width="stretch"):
            row = apply_defaults_to_row({"field_name": new_field, "waveform": new_wave}, new_wave)
            df = pd.concat(
                [st.session_state.channels_df, pd.DataFrame([row])],
                ignore_index=True,
            )
            st.session_state.channels_df = normalize_channels_df(df)
            st.session_state.channels_df_prev = st.session_state.channels_df.copy()
            st.rerun()
    with q4:
        if st.button("Defaults for all", width="stretch"):
            df = st.session_state.channels_df.copy()
            for idx in df.index:
                df.loc[idx] = apply_defaults_to_row(df.loc[idx])
            st.session_state.channels_df = normalize_channels_df(df)
            st.session_state.channels_df_prev = st.session_state.channels_df.copy()
            st.rerun()

    edited = st.data_editor(
        st.session_state.channels_df,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key="channels_editor",
        column_config={
            "enabled": st.column_config.CheckboxColumn("On", default=True, width="small"),
            "field_name": st.column_config.TextColumn("Field", required=True, width="medium"),
            "waveform": st.column_config.SelectboxColumn("Waveform", options=WAVEFORM_OPTIONS, width="medium"),
            "amplitude": st.column_config.NumberColumn("Amp", format="%.3f", width="small"),
            "frequency_hz": st.column_config.NumberColumn("Hz", format="%.3f", min_value=0.0001, width="small"),
            "offset": st.column_config.NumberColumn("Offset", format="%.3f", width="small"),
            "phase_deg": st.column_config.NumberColumn("Phase°", format="%.1f", width="small"),
            "duty": st.column_config.NumberColumn("Duty", format="%.2f", min_value=0.01, max_value=0.99, width="small"),
            "min_value": st.column_config.NumberColumn("Min", format="%.3f", width="small"),
            "max_value": st.column_config.NumberColumn("Max", format="%.3f", width="small"),
            "noise_std": st.column_config.NumberColumn("σ", format="%.3f", width="small"),
            "decay_rate": st.column_config.NumberColumn("Decay", format="%.3f", width="small"),
        },
    )

    prev_df = st.session_state.get("channels_df_prev")
    merged = apply_waveform_changes(prev_df, edited)
    st.session_state.channels_df = normalize_channels_df(merged)
    st.session_state.channels_df_prev = st.session_state.channels_df.copy()

st.divider()

tab_preview, tab_log, tab_line = st.tabs(["Wave preview", "Activity log", "Last line protocol"])

with tab_preview:
    names = [
        str(x).strip()
        for x in st.session_state.channels_df.get("field_name", pd.Series(dtype=str)).tolist()
        if str(x).strip()
    ]
    if not names:
        st.info("Add at least one channel with a field name.")
    else:
        p1, p2 = st.columns([2, 1])
        with p1:
            preview_channel = st.selectbox("Channel to preview", names)
        with p2:
            dur = st.slider("Duration (s)", 2, 60, 10)
        ch_row = st.session_state.channels_df[
            st.session_state.channels_df["field_name"].astype(str) == preview_channel
        ]
        if len(ch_row):
            ch = _df_to_channels(ch_row)[0]
            times, values = preview_series(ch, duration_s=float(dur))
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(x=times, y=values, mode="lines", line=dict(color="#2563eb", width=2), name=preview_channel)
            )
            fig.update_layout(
                template="plotly_white",
                title=f"{preview_channel} · {ch.waveform}",
                xaxis_title="Time (s)",
                yaxis_title="Value",
                height=380,
                margin=dict(l=40, r=20, t=48, b=40),
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.warning("Channel not found.")

with tab_log:
    lc1, lc2 = st.columns([1, 5])
    if lc1.button("Clear log"):
        st.session_state.log_lines.clear()
    log_box = st.container(height=280)
    with log_box:
        for line in list(st.session_state.log_lines)[:80]:
            st.text(line)

with tab_line:
    if engine.status.last_line:
        st.code(engine.status.last_line, language="text")
    else:
        st.caption("Start streaming to see the latest Influx line protocol here.")
    if engine.status.last_error:
        st.error(engine.status.last_error)

if running:
    _sync_logs(engine)
    time.sleep(0.4)
    st.rerun()
