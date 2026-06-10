"""System health scraping for the health channel. Pi-specific probes degrade
to ``None`` on other platforms, so the module imports cleanly everywhere."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Dict, Optional


def _run(cmd: list[str], timeout: float = 1.5) -> Optional[str]:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def read_throttled() -> Optional[str]:
    """Raspberry Pi undervoltage/throttle flags, e.g. '0x0' or '0x50005'."""
    out = _run(['vcgencmd', 'get_throttled'])
    return out.split('=', 1)[1] if out and '=' in out else None


def read_temp_c() -> Optional[float]:
    out = _run(['vcgencmd', 'measure_temp'])     # "temp=48.3'C"
    if out and '=' in out:
        try:
            return float(out.split('=')[1].split("'")[0])
        except (ValueError, IndexError):
            return None
    try:  # generic Linux fallback
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return int(f.read().strip()) / 1000.0
    except (OSError, ValueError):
        return None


def read_wifi_rssi_dbm(iface: str = 'wlan0') -> Optional[int]:
    try:
        with open('/proc/net/wireless') as f:
            for line in f:
                if line.strip().startswith(iface + ':'):
                    return int(float(line.split()[3]))
    except (OSError, ValueError, IndexError):
        return None
    return None


def read_loadavg() -> Optional[float]:
    try:
        return os.getloadavg()[0]
    except (OSError, AttributeError):  # not on Windows
        return None


def read_mem_free_mb() -> Optional[int]:
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemAvailable:'):
                    return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def disk_free_mb(path: str = '/') -> Optional[int]:
    try:
        return shutil.disk_usage(path).free // (1024 * 1024)
    except OSError:
        return None


class HealthAggregator:
    """Combines system probes with per-stream data freshness.

    ``touch(name)`` is called by the gateway every time a message arrives on
    a ROS topic; ``snapshot()`` reports each stream's age — the dashboard's
    health panel is rendered directly from this payload.
    """

    SYS_PROBE_PERIOD_S = 5.0   # vcgencmd is not free; don't call it at 1 Hz

    def __init__(self, streams: tuple[str, ...]):
        self._last_seen: Dict[str, float] = {s: 0.0 for s in streams}
        self._sys_cache: dict = {}
        self._sys_cached_at = 0.0
        self.started_mono = time.monotonic()

    def touch(self, stream: str) -> None:
        self._last_seen[stream] = time.monotonic()

    def snapshot(self) -> dict:
        now = time.monotonic()
        if now - self._sys_cached_at > self.SYS_PROBE_PERIOD_S:
            self._sys_cache = {
                'throttled': read_throttled(),
                'temp_c': read_temp_c(),
                'rssi_dbm': read_wifi_rssi_dbm(),
                'load1': read_loadavg(),
                'mem_free_mb': read_mem_free_mb(),
                'disk_free_mb': disk_free_mb(),
            }
            self._sys_cached_at = now
        streams = {
            name: round(now - seen, 2) if seen > 0 else None   # None = never seen
            for name, seen in self._last_seen.items()
        }
        return {
            'uptime_s': round(now - self.started_mono, 1),
            'streams_age_s': streams,
            'sys': self._sys_cache,
        }
