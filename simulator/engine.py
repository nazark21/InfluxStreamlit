"""Background streaming loop writing points to InfluxDB."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime

import backoff
import urllib3
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from urllib3.exceptions import ReadTimeoutError

from simulator.credentials_store import InfluxCredentials
from simulator.waveforms import ChannelConfig, generate_value, reset_state

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@dataclass
class SimulationConfig:
    measurement: str
    run_id: str
    interval_s: float
    channels: list[ChannelConfig]
    credentials: InfluxCredentials


@dataclass
class SimulationStatus:
    running: bool = False
    writes: int = 0
    errors: int = 0
    last_line: str = ""
    last_error: str = ""
    started_at: float | None = None


class SimulationEngine:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.status = SimulationStatus()
        self._client: InfluxDBClient | None = None
        self._write_api = None
        self._t0: float = 0.0
        self._step = 0
        self._log_lock = threading.Lock()
        self._logs: deque[str] = deque(maxlen=300)

    def _log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        with self._log_lock:
            self._logs.appendleft(f"{stamp}  {message}")

    def drain_logs(self) -> list[str]:
        with self._log_lock:
            lines = list(self._logs)
            self._logs.clear()
            return lines

    def is_running(self) -> bool:
        return self.status.running and self._thread is not None and self._thread.is_alive()

    def start(self, config: SimulationConfig) -> None:
        if self.is_running():
            raise RuntimeError("Simulation already running")

        if not config.credentials.is_complete():
            raise ValueError("Incomplete InfluxDB credentials")

        enabled = [c for c in config.channels if c.enabled and c.field_name.strip()]
        if not enabled:
            raise ValueError("Add at least one enabled channel with a field name")

        self._stop.clear()
        reset_state()
        self.status = SimulationStatus(running=True, started_at=time.monotonic())
        self._step = 0
        self._t0 = time.monotonic()

        def run() -> None:
            try:
                self._client = InfluxDBClient(
                    url=config.credentials.url,
                    token=config.credentials.token,
                    org=config.credentials.org,
                    verify_ssl=config.credentials.verify_ssl,
                    timeout=30_000,
                )
                self._write_api = self._client.write_api(write_options=SYNCHRONOUS)

                while not self._stop.is_set():
                    try:
                        line = self._write_point(config, enabled)
                        self.status.writes += 1
                        self.status.last_line = line
                        self._log(line)
                    except Exception as exc:  # noqa: BLE001
                        self.status.errors += 1
                        self.status.last_error = str(exc)
                        self._log(f"ERROR: {exc}")

                    self._step += 1
                    if self._stop.wait(config.interval_s):
                        break
            finally:
                self._close_client()
                self.status.running = False

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._thread = None
        self.status.running = False

    def _close_client(self) -> None:
        if self._client:
            try:
                self._client.close()
            except Exception:  # noqa: BLE001
                pass
        self._client = None
        self._write_api = None

    @backoff.on_exception(backoff.expo, (ReadTimeoutError, Exception), max_tries=3)
    def _write_point(self, config: SimulationConfig, channels: list[ChannelConfig]) -> str:
        t = time.monotonic() - self._t0
        point = Point(config.measurement).tag("RunID", config.run_id)
        for ch in channels:
            value = generate_value(ch, t, self._step)
            point = point.field(ch.field_name.strip(), round(float(value), 6))

        point = point.time(datetime.now(UTC), WritePrecision.NS)
        assert self._write_api is not None
        self._write_api.write(
            bucket=config.credentials.bucket,
            org=config.credentials.org,
            record=point,
        )
        return point.to_line_protocol() or ""
