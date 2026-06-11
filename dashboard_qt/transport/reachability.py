"""Background host-reachability prober for the fleet pills.

The command-channel heartbeat answers "is the robot's SOFTWARE ready?".
This prober answers the layer below: "is the Pi even on the network?" —
so the header can distinguish three truths the operator needs:

    READY        heartbeat ACKs       → green
    ON NETWORK   TCP port open, no    → amber: powered + connected, the
                 heartbeat            stack just isn't running
    UNREACHABLE  nothing answers      → red: off / not on this network

Probes a TCP connect (port 22 for the Pis, the HTTP port for the ESP32)
every PROBE_PERIOD_S from one daemon thread; results re-enter Qt via a
queued signal.
"""

from __future__ import annotations

import socket
import threading

from PySide6.QtCore import QObject, Signal

PROBE_PERIOD_S = 5.0
PROBE_TIMEOUT_S = 1.5


class ReachabilityProber(QObject):
    reachableChanged = Signal(str, bool)        # robot_id, reachable

    def __init__(self, targets: dict[str, tuple[str, int]], parent=None):
        """targets: robot_id → (host, tcp_port)"""
        super().__init__(parent)
        self._targets = dict(targets)
        self._state: dict[str, bool | None] = {rid: None for rid in targets}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name='reachability')
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            for rid, (host, port) in self._targets.items():
                ok = self._probe(host, port)
                if ok != self._state[rid]:          # edge-triggered
                    self._state[rid] = ok
                    self.reachableChanged.emit(rid, ok)
            self._stop.wait(PROBE_PERIOD_S)

    @staticmethod
    def _probe(host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port),
                                          timeout=PROBE_TIMEOUT_S):
                return True
        except OSError:
            return False
