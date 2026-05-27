# InfluxDB Streamlit Simulator

Web UI to stream synthetic sensor data to InfluxDB (same shape as `simulate11.py` / `simulate4.py`).

## Setup

```bash
cd Testruns/InfluxStreamlit
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Influx + MongoDB URLs
```

## Run

```bash
streamlit run streamlit_app.py
```

## Features

- **Default credentials** from `.env` (`INFLUXDB_URL`, `TOKEN`, `ORG`, `BUCKET`)
- **Per-user credentials** in MongoDB (keyed by User ID) when “Use my saved credentials” is enabled
- **Interval**: 50 ms … 1 min
- **`_measurement`**, **`RunID`** tag, multiple **`_fields`**
- **Waveforms**: sine, square, triangle, sawtooth, pulse, noise, chirp, heartbeat, CPU/memory/network metrics, etc.
- **Presets**: simulate11-style and simulate4-style channel sets
- **Live preview** chart (Plotly) before streaming

## MongoDB document shape

```json
{
  "userId": "user@example.com",
  "influx": {
    "url": "https://…",
    "token": "…",
    "org": "Testruns",
    "bucket": "Testruns",
    "verify_ssl": false
  },
  "updatedAt": "…"
}
```

Only the user who saved credentials can load them (by entering the same User ID).
