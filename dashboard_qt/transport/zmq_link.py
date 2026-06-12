"""Per-robot ZMQ transport for the operator console.

``RobotLink``     — one background thread subscribing telemetry/map/health/
                    video; every message is re-emitted as a Qt signal into
                    the UI thread (queued connections).
``CommandClient`` — DEALER with the protocol's ACK semantics: 300 ms timeout,
                    ×2 retry with the SAME cmd_id, 1 Hz ping for liveness,
                    e-stop burst. UI-thread API; its own background thread.

Threads never touch widgets; the StateStore (UI thread) is the single writer
of app state.
"""

from __future__ import annotations

import threading
import time
from collections import deque

import zmq
from PySide6.QtCore import QObject, Signal

from gpcore.protocol import channels as ch
from gpcore.protocol import commands as cmds
from gpcore.protocol.envelope import ProtocolError, decode, encode, unpack_with_blob

RECONNECT_IVL_MS = 200
RECONNECT_MAX_MS = 2000


def _tune(sock: zmq.Socket, conflate: bool = False) -> None:
    sock.setsockopt(zmq.LINGER, 0)
    sock.setsockopt(zmq.RECONNECT_IVL, RECONNECT_IVL_MS)
    sock.setsockopt(zmq.RECONNECT_IVL_MAX, RECONNECT_MAX_MS)
    if conflate:
        sock.setsockopt(zmq.CONFLATE, 1)


class RobotLink(QObject):
    """Subscribes one robot's PUB channels and re-emits into the UI thread."""

    telemetryReceived = Signal(object)          # Envelope (tele.full)
    scanReceived = Signal(object)               # Envelope (tele.scan)
    mapReceived = Signal(object)                # Envelope (map.grid)
    healthReceived = Signal(object)             # Envelope (health | log.event)
    videoFrameReceived = Signal(object, bytes)  # Envelope (video.meta), jpeg
    legacyFrameReceived = Signal(bytes)         # raw jpeg (5555)

    def __init__(self, host: str, zmq_ports: dict, *, legacy_video_port: int = 0,
                 parent=None):
        super().__init__(parent)
        self.host = host
        self.ports = zmq_ports
        self.legacy_video_port = legacy_video_port
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # Own context so multiple RobotLinks and their reconnect cycles
        # don't compete for the singleton I/O thread.
        self._ctx = zmq.Context(io_threads=2)

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name=f'link-{self.host}')
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._ctx.term()

    def _loop(self) -> None:
        ctx = self._ctx

        def sub(port: int, conflate: bool) -> zmq.Socket | None:
            if not port:
                return None
            s = ctx.socket(zmq.SUB)
            _tune(s, conflate)
            s.setsockopt(zmq.SUBSCRIBE, b'')
            s.connect(f'tcp://{self.host}:{port}')
            return s

        tele = sub(self.ports.get('telemetry', 0), conflate=False)  # seq gaps matter
        mapc = sub(self.ports.get('map', 0), conflate=True)
        health = sub(self.ports.get('health', 0), conflate=False)
        video = sub(self.ports.get('video', 0), conflate=True)
        legacy = sub(self.legacy_video_port, conflate=True)

        poller = zmq.Poller()
        for s in (tele, mapc, health, video, legacy):
            if s is not None:
                poller.register(s, zmq.POLLIN)

        try:
            while not self._stop.is_set():
                events = dict(poller.poll(timeout=100))
                if tele in events:
                    self._emit_envelope(tele.recv(zmq.NOBLOCK))
                if mapc in events:
                    self._emit_envelope(mapc.recv(zmq.NOBLOCK))
                if health in events:
                    self._emit_envelope(health.recv(zmq.NOBLOCK))
                if video in events:
                    try:
                        meta, jpeg = unpack_with_blob(video.recv(zmq.NOBLOCK))
                        self.videoFrameReceived.emit(meta, jpeg)
                    except (ProtocolError, zmq.Again):
                        pass
                if legacy in events:
                    self.legacyFrameReceived.emit(legacy.recv(zmq.NOBLOCK))
        finally:
            for s in (tele, mapc, health, video, legacy):
                if s is not None:
                    s.close(0)

    def _emit_envelope(self, raw: bytes) -> None:
        try:
            env = decode(raw)
        except ProtocolError:
            return
        if env.type == ch.TELE_FULL:
            self.telemetryReceived.emit(env)
        elif env.type == ch.TELE_SCAN:
            self.scanReceived.emit(env)
        elif env.type == ch.MAP_GRID:
            self.mapReceived.emit(env)
        else:                                   # health, log.event, future types
            self.healthReceived.emit(env)


class CommandClient(QObject):
    """ACKed command channel to one robot (UI-thread API, own worker thread)."""

    ackReceived = Signal(str, str, bool, str)   # cmd_id, cmd_type, ok, detail
    commandFailed = Signal(str, str, str)       # cmd_id, cmd_type, reason
    linkUp = Signal(bool)                       # ping-based liveness

    PING_PERIOD_S = 1.0

    def __init__(self, host: str, cmd_port: int, *, run_id: str, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = cmd_port
        self.run_id = run_id
        self._stop = threading.Event()
        self._outbox: deque = deque()
        self._lock = threading.Lock()
        self._seq = 0
        self._thread: threading.Thread | None = None
        self._link_up: bool | None = None
        # Own context so RobotLink's high-throughput SUB sockets
        # (video 20fps + tele 20Hz) don't starve our DEALER I/O thread.
        self._ctx = zmq.Context(io_threads=2)

    # ── UI-thread API ─────────────────────────────────────────────────────
    def send(self, cmd_type: str, payload: dict) -> str:
        """Queue a command; returns its cmd_id immediately."""
        self._seq += 1
        env = cmds.make_command(cmd_type, payload, seq=self._seq,
                                run_id=self.run_id, src='dashboard')
        with self._lock:
            self._outbox.append(env)
        return env.payload['cmd_id']

    def drive(self, vx: float, wz: float) -> str:
        return self.send(cmds.CMD_DRIVE, {'vx': vx, 'wz': wz})

    def estop(self, engage: bool) -> None:
        # Burst: e-stop must survive packet loss without waiting on retries.
        for _ in range(cmds.ESTOP_BURST):
            self.send(cmds.CMD_ESTOP, {'engage': engage})

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name=f'cmd-{self.host}')
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._ctx.term()

    # ── worker thread ─────────────────────────────────────────────────────
    def _loop(self) -> None:
        sock = self._ctx.socket(zmq.DEALER)
        _tune(sock)
        sock.connect(f'tcp://{self.host}:{self.port}')

        pending: dict[str, dict] = {}    # cmd_id → {env, attempts, deadline}
        last_ping = 0.0
        last_ack = 0.0

        try:
            while not self._stop.is_set():
                now = time.monotonic()

                # 1. flush the outbox
                while True:
                    with self._lock:
                        env = self._outbox.popleft() if self._outbox else None
                    if env is None:
                        break
                    self._transmit(sock, env, pending, now)

                # 2. periodic ping → liveness
                if now - last_ping > self.PING_PERIOD_S:
                    last_ping = now
                    self._seq += 1
                    ping = cmds.make_command(cmds.CMD_PING, {}, seq=self._seq,
                                             run_id=self.run_id, src='dashboard')
                    self._transmit(sock, ping, pending, now)

                # 3. receive ACKs
                while sock.poll(timeout=20):
                    try:
                        ack = decode(sock.recv(zmq.NOBLOCK))
                    except (zmq.Again, ProtocolError):
                        break
                    if ack.type != ch.ACK:
                        continue
                    last_ack = time.monotonic()
                    info = pending.pop(ack.payload.get('cmd_id', ''), None)
                    cmd_type = ack.payload.get('cmd_type', '?')
                    if info is not None and cmd_type != cmds.CMD_PING:
                        self.ackReceived.emit(ack.payload['cmd_id'], cmd_type,
                                              bool(ack.payload.get('ok')),
                                              str(ack.payload.get('detail', '')))

                # 4. retries / failures
                for cmd_id in list(pending):
                    info = pending[cmd_id]
                    if now < info['deadline']:
                        continue
                    # NEVER retry a drive: it's a 10 Hz stream, so a retry
                    # delivers an OBSOLETE stick position after the link
                    # recovers — the robot replays the past (field
                    # 2026-06-12: 1 s of stick = 2-3 s of motion). The next
                    # stream tick carries fresher intent, and the gateway
                    # deadman covers total silence. Pings likewise: the
                    # next periodic ping IS the retry.
                    if info['env'].type in (cmds.CMD_DRIVE, cmds.CMD_PING):
                        pending.pop(cmd_id)
                        continue
                    if info['attempts'] <= cmds.ACK_RETRIES:
                        self._transmit(sock, info['env'], pending, now)
                    else:
                        pending.pop(cmd_id)
                        if info['env'].type != cmds.CMD_PING:
                            self.commandFailed.emit(cmd_id, info['env'].type,
                                                    'no ACK after retries')

                # 5. liveness signal (edge-triggered)
                up = (time.monotonic() - last_ack) < 3.0 if last_ack else False
                if up != self._link_up:
                    self._link_up = up
                    self.linkUp.emit(up)
        finally:
            sock.close(0)

    def _transmit(self, sock, env, pending, now) -> None:
        prev = pending.get(env.payload['cmd_id'])
        attempts = (prev['attempts'] + 1) if prev else 1
        try:
            sock.send(encode(env), zmq.NOBLOCK)
        except zmq.Again:
            pass  # DEALER buffer full — retry path will resend
        pending[env.payload['cmd_id']] = {
            'env': env, 'attempts': attempts,
            'deadline': now + cmds.ACK_TIMEOUT_S,
        }
