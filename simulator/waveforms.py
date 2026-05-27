"""Waveform and system-metric value generators for Influx field simulation."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Callable

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore


WAVEFORM_OPTIONS: list[str] = [
    "Sine",
    "Cosine",
    "Square",
    "Triangle",
    "Sawtooth",
    "Reverse sawtooth",
    "Pulse",
    "Constant",
    "Uniform noise",
    "Gaussian noise",
    "Random walk",
    "Ramp",
    "Exponential decay",
    "Chirp (sweep)",
    "Heartbeat",
    "CPU usage %",
    "Memory usage %",
    "Network send (KB/s)",
    "Network recv (KB/s)",
]

INTERVAL_OPTIONS: dict[str, float] = {
    "50 ms": 0.05,
    "100 ms": 0.1,
    "200 ms": 0.2,
    "500 ms": 0.5,
    "1 s": 1.0,
    "2 s": 2.0,
    "5 s": 5.0,
    "10 s": 10.0,
    "30 s": 30.0,
    "1 min": 60.0,
}


@dataclass
class ChannelConfig:
    field_name: str
    waveform: str = "Sine"
    amplitude: float = 1.0
    frequency_hz: float = 0.5
    offset: float = 0.0
    phase_deg: float = 0.0
    duty: float = 0.5
    min_value: float = 0.0
    max_value: float = 100.0
    noise_std: float = 0.1
    decay_rate: float = 0.05
    enabled: bool = True


def _phase_rad(phase_deg: float) -> float:
    return math.radians(phase_deg)


def _norm_phase(t: float, frequency_hz: float, phase_deg: float) -> float:
    return 2 * math.pi * frequency_hz * t + _phase_rad(phase_deg)


class _NetworkSampler:
    """Tracks delta bytes between calls for KB/s estimates."""

    def __init__(self) -> None:
        self._last: tuple[float, float, float] | None = None

    def sample(self) -> tuple[float, float]:
        if psutil is None:
            return 0.0, 0.0
        counters = psutil.net_io_counters()
        now = time.monotonic()
        sent_kbps = 0.0
        recv_kbps = 0.0
        if self._last is not None:
            dt = max(now - self._last[0], 1e-6)
            sent_kbps = max(0.0, (counters.bytes_sent - self._last[1]) / 1024 / dt)
            recv_kbps = max(0.0, (counters.bytes_recv - self._last[2]) / 1024 / dt)
        self._last = (now, counters.bytes_sent, counters.bytes_recv)
        return sent_kbps, recv_kbps


_NETWORK = _NetworkSampler()
_RANDOM_WALK: dict[str, float] = {}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def generate_value(channel: ChannelConfig, t: float, step_index: int) -> float:
    """Return one scalar sample for a channel at simulation time t (seconds)."""
    w = channel.waveform
    amp = channel.amplitude
    freq = max(channel.frequency_hz, 1e-9)
    off = channel.offset
    phase = _norm_phase(t, freq, channel.phase_deg)

    if w == "Sine":
        return off + amp * math.sin(phase)
    if w == "Cosine":
        return off + amp * math.cos(phase)
    if w == "Square":
        return off + (amp if math.sin(phase) >= 0 else -amp)
    if w == "Triangle":
        return off + (2 * amp / math.pi) * math.asin(math.sin(phase))
    if w == "Sawtooth":
        period = 1 / freq
        p = (t % period) / period
        return off + amp * (2 * p - 1)
    if w == "Reverse sawtooth":
        period = 1 / freq
        p = (t % period) / period
        return off + amp * (1 - 2 * p)
    if w == "Pulse":
        period = 1 / freq
        p = (t % period) / period
        return off + (amp if p < channel.duty else 0.0)
    if w == "Constant":
        return off + amp
    if w == "Uniform noise":
        return _clamp(
            off + random.uniform(-amp, amp),
            channel.min_value,
            channel.max_value,
        )
    if w == "Gaussian noise":
        return _clamp(
            off + random.gauss(0, max(channel.noise_std, 1e-9) * amp),
            channel.min_value,
            channel.max_value,
        )
    if w == "Random walk":
        key = channel.field_name
        prev = _RANDOM_WALK.get(key, off)
        step = random.uniform(-amp, amp) * 0.1
        prev = _clamp(prev + step, channel.min_value, channel.max_value)
        _RANDOM_WALK[key] = prev
        return prev
    if w == "Ramp":
        period = max(1 / freq, 1e-9)
        p = min((t % period) / period, 1.0)
        return off + amp * p
    if w == "Exponential decay":
        return off + amp * math.exp(-channel.decay_rate * t)
    if w == "Chirp (sweep)":
        f_end = freq * 4
        sweep = freq + (f_end - freq) * (0.5 * (1 - math.cos(phase)))
        return off + amp * math.sin(2 * math.pi * sweep * t)
    if w == "Heartbeat":
        period = max(1 / freq, 1e-9)
        p = (t % period) / period
        if p < 0.15:
            v = amp
        elif p < 0.25:
            v = amp * 0.35
        else:
            v = 0.0
        return off + v

    if w == "CPU usage %":
        if psutil is None:
            return off
        return off + psutil.cpu_percent(interval=None)
    if w == "Memory usage %":
        if psutil is None:
            return off
        return off + psutil.virtual_memory().percent
    if w == "Network send (KB/s)":
        sent, _ = _NETWORK.sample()
        return off + sent
    if w == "Network recv (KB/s)":
        _, recv = _NETWORK.sample()
        return off + recv

    return off + amp * math.sin(phase)


def reset_state() -> None:
    _RANDOM_WALK.clear()
    global _NETWORK
    _NETWORK = _NetworkSampler()


def preview_series(
    channel: ChannelConfig,
    duration_s: float = 10.0,
    sample_hz: float = 20.0,
) -> tuple[list[float], list[float]]:
    """Generate time series for chart preview."""
    if duration_s <= 0 or sample_hz <= 0:
        return [], []
    dt = 1.0 / sample_hz
    times: list[float] = []
    values: list[float] = []
    steps = int(duration_s * sample_hz)
    for i in range(steps + 1):
        t = i * dt
        times.append(t)
        values.append(generate_value(channel, t, i))
    return times, values
