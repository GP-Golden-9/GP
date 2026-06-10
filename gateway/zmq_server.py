"""Robot-side ZMQ machinery — deliberately free of ROS imports.

Owns the sockets, sequence counters, command dedupe and the drive deadman so
all of it is unit-testable over ``inproc://`` transports (see
tests/test_gateway_roundtrip.py). ``gateway_node.py`` wires this to ROS.

Channels (PUB unless noted):
    telemetry  tele.full / tele.scan
    map        map.grid
    health     health
    cmd        ROUTER — receives cmd.*, replies ack
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, Optional, Tuple

import zmq

from gpcore.protocol import channels as ch
from gpcore.protocol import commands as cmds
from gpcore.protocol.envelope import Envelope, ProtocolError, decode, encode, make_envelope

log = logging.getLogger('gp.zmq_server')

CommandHandler = Callable[[Envelope], Tuple[bool, str]]


class GatewayServer:
    """Socket lifecycle + protocol bookkeeping for one robot.

    ``endpoints`` maps channel name → ZMQ endpoint. Production uses
    ``tcp://*:<port>``; tests use ``inproc://…`` with a shared context.
    """

    PUB_CHANNELS = ('telemetry', 'map', 'health')

    def __init__(self, *, run_id: str, src: str,
                 endpoints: Dict[str, str],
                 context: Optional[zmq.Context] = None):
        self.run_id = run_id
        self.src = src
        self._own_context = context is None
        self.ctx = context or zmq.Context.instance()

        self._pub: Dict[str, zmq.Socket] = {}
        for name in self.PUB_CHANNELS:
            sock = self.ctx.socket(zmq.PUB)
            sock.setsockopt(zmq.SNDHWM, 10)
            sock.setsockopt(zmq.LINGER, 0)
            sock.bind(endpoints[name])
            self._pub[name] = sock

        self.cmd_sock = self.ctx.socket(zmq.ROUTER)
        self.cmd_sock.setsockopt(zmq.LINGER, 0)
        self.cmd_sock.bind(endpoints['cmd'])

        # seq counters are PER MESSAGE TYPE (not per channel): tele.full and
        # tele.scan interleave on one socket, and a shared counter would make
        # every scan look like a lost tele.full to consumers' gap detection.
        self._seq: Dict[str, int] = {}

        self.deduper = cmds.CommandDeduper()
        self.deadman = cmds.DriveDeadman()
        self.estop_latched = False

        self._handlers: Dict[str, CommandHandler] = {}
        self.stats = {'cmds': 0, 'acks': 0, 'rejected': 0, 'deduped': 0}

    # ── publishing ────────────────────────────────────────────────────────
    def publish(self, channel: str, msg_type: str, payload: dict) -> int:
        seq = self._seq.get(msg_type, 0) + 1
        self._seq[msg_type] = seq
        env = make_envelope(msg_type, payload, seq=seq, run_id=self.run_id,
                            src=self.src)
        try:
            self._pub[channel].send(encode(env), zmq.NOBLOCK)
        except zmq.Again:
            pass  # HWM hit — slow/absent subscriber must not block the robot
        return seq

    # ── command handling ──────────────────────────────────────────────────
    def set_handler(self, cmd_type: str, fn: CommandHandler) -> None:
        if cmd_type not in cmds.ALL_COMMANDS:
            raise ValueError(f'unknown command type {cmd_type!r}')
        self._handlers[cmd_type] = fn

    def poll_commands(self, timeout_ms: int = 0) -> int:
        """Drain pending commands, dispatch handlers, send ACKs.

        Returns the number of commands processed. Call from the gateway's
        main loop at ≥ 20 Hz.
        """
        processed = 0
        while True:
            if not self.cmd_sock.poll(timeout_ms if processed == 0 else 0):
                return processed
            try:
                frames = self.cmd_sock.recv_multipart(zmq.NOBLOCK)
            except zmq.Again:
                return processed
            processed += 1
            if len(frames) < 2:
                continue
            identity, raw = frames[0], frames[-1]
            self._handle_one(identity, raw)

    def _handle_one(self, identity: bytes, raw: bytes) -> None:
        self.stats['cmds'] += 1
        try:
            env = decode(raw)
            cmd_id = cmds.validate_command(env)
        except (ProtocolError, cmds.CommandError) as exc:
            self.stats['rejected'] += 1
            log.warning('rejected command: %s', exc)
            return  # cannot ack without a decodable cmd_id

        duplicate = self.deduper.seen_before(cmd_id)
        if duplicate and env.type in cmds.EXACTLY_ONCE:
            # Retry of an already-executed command: ack success, don't re-run.
            self.stats['deduped'] += 1
            self._ack(identity, env, ok=True, detail='duplicate (already executed)')
            return

        if env.type == cmds.CMD_DRIVE:
            if self.estop_latched:
                self._ack(identity, env, ok=False, detail='estop latched')
                return
            vx = float(env.payload.get('vx', 0.0))
            wz = float(env.payload.get('wz', 0.0))
            self.deadman.feed(vx, wz, time.monotonic())
        elif env.type == cmds.CMD_ESTOP:
            self.estop_latched = bool(env.payload.get('engage', True))

        handler = self._handlers.get(env.type)
        if handler is None:
            if env.type == cmds.CMD_PING:
                self._ack(identity, env, ok=True, detail='pong')
            else:
                self._ack(identity, env, ok=False, detail='no handler')
            return

        try:
            ok, detail = handler(env)
        except Exception as exc:  # a handler bug must never kill the gateway
            log.exception('handler for %s crashed', env.type)
            ok, detail = False, f'handler error: {exc}'
        self._ack(identity, env, ok=ok, detail=detail)

    def _ack(self, identity: bytes, env: Envelope, *, ok: bool, detail: str) -> None:
        seq = self._seq.get('ack', 0) + 1
        self._seq['ack'] = seq
        ack = cmds.make_ack(env, ok=ok, detail=detail, seq=seq,
                            run_id=self.run_id, src=self.src)
        try:
            self.cmd_sock.send_multipart([identity, encode(ack)], zmq.NOBLOCK)
            self.stats['acks'] += 1
        except zmq.Again:
            pass

    # ── deadman ───────────────────────────────────────────────────────────
    def deadman_tripped(self, now_mono: Optional[float] = None) -> bool:
        """True exactly once when the drive stream died mid-motion.
        Caller must then command a stop on the robot side."""
        return self.deadman.should_stop(
            time.monotonic() if now_mono is None else now_mono)

    def close(self) -> None:
        for sock in self._pub.values():
            sock.close(0)
        self.cmd_sock.close(0)
        if self._own_context:
            # don't term the shared instance() context — other users may exist
            pass
