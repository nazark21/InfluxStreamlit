# InfluxStreamlit

Streamlit app to stream synthetic sensor data to InfluxDB (Testruns-compatible: `_measurement`, `RunID`, `_fields`).

## Setup

```bash
cd Testruns/InfluxStreamlit
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with Influx defaults and optional MongoDB URI
```

## Run

```bash
streamlit run streamlit_app.py
```

## Features

- Default Influx credentials from `.env`
- Per-user credentials in MongoDB (sidebar User ID)
- Intervals from 50 ms to 1 min
- Waveforms: sine, square, triangle, sawtooth, pulse, noise, chirp, CPU/memory/network, etc.
- Presets based on `InfluxDB_Simulation/simulate11.py` and `simulate4.py`

See `SIMULATOR_README.md` for MongoDB document shape and env variables.
