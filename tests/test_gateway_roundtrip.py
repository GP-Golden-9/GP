"""Gateway protocol tests over inproc:// — no ROS, no network, no robot."""

import time

import pytest
import zmq

from gateway.zmq_server import GatewayServer
from gpcore.protocol import commands as cmds
from gpcore.protocol.envelope import decode

ENDPOINTS = {
    'telemetry': 'inproc://gp-test-tele',
    'map': 'inproc://gp-test-map',
    'health': 'inproc://gp-test-health',
    'cmd': 'inproc://gp-test-cmd',
}


@pytest.fixture()
def rig():
    ctx = zmq.Context()
    server = GatewayServer(run_id='testrun', src='robot2',
                           endpoints=ENDPOINTS, context=ctx)

    dealer = ctx.socket(zmq.DEALER)
    dealer.setsockopt(zmq.LINGER, 0)
    dealer.connect(ENDPOINTS['cmd'])

    sub = ctx.socket(zmq.SUB)
    sub.setsockopt(zmq.LINGER, 0)
    sub.setsockopt(zmq.SUBSCRIBE, b'')
    sub.connect(ENDPOINTS['telemetry'])
    time.sleep(0.05)  # let inproc subscriptions settle

    yield server, dealer, sub

    dealer.close(0)
    sub.close(0)
    server.close()
    ctx.term()


def send_cmd(dealer, server, ctype, payload, cmd_id=None, seq=1):
    env = cmds.make_command(ctype, payload, seq=seq, run_id='testrun',
                            src='dash', cmd_id=cmd_id)
    from gpcore.protocol.envelope import encode
    dealer.send(encode(env))
    server.poll_commands(timeout_ms=200)
    assert dealer.poll(1000), 'no ACK received'
    ack = decode(dealer.recv())
    return env, ack


def test_telemetry_pubsub_with_increasing_seq(rig):
    server, _dealer, sub = rig
    server.publish('telemetry', 'tele.full', {'enc': [1, 2, 3, 4]})
    server.publish('telemetry', 'tele.full', {'enc': [5, 6, 7, 8]})
    first = decode(sub.recv())
    second = decode(sub.recv())
    assert (first.seq, second.seq) == (1, 2)
    assert first.src == 'robot2' and first.run_id == 'testrun'
    assert second.payload['enc'] == [5, 6, 7, 8]


def test_pump_command_executed_once_under_retry(rig):
    server, dealer, _sub = rig
    calls = []
    server.set_handler(cmds.CMD_PUMP, lambda env: (calls.append(env.payload['on']) or True, 'PUMP=ON'))

    env, ack = send_cmd(dealer, server, cmds.CMD_PUMP, {'on': True})
    assert ack.payload['ok'] is True
    assert calls == [True]

    # Network retry: same cmd_id again → acked OK but NOT re-executed
    _env2, ack2 = send_cmd(dealer, server, cmds.CMD_PUMP, {'on': True},
                           cmd_id=env.payload['cmd_id'], seq=2)
    assert ack2.payload['ok'] is True
    assert 'duplicate' in ack2.payload['detail']
    assert calls == [True]
    assert server.stats['deduped'] == 1


def test_drive_feeds_deadman_and_trips_on_silence(rig):
    server, dealer, _sub = rig
    server.set_handler(cmds.CMD_DRIVE, lambda env: (True, 'ok'))
    send_cmd(dealer, server, cmds.CMD_DRIVE, {'vx': 0.15, 'wz': 0.0})

    now = time.monotonic()
    assert server.deadman_tripped(now + 0.1) is False     # stream considered alive
    assert server.deadman_tripped(now + 5.0) is True      # silence → stop once
    assert server.deadman_tripped(now + 9.0) is False     # only fires once


def test_estop_latch_blocks_drive(rig):
    server, dealer, _sub = rig
    server.set_handler(cmds.CMD_ESTOP, lambda env: (True, 'engaged'))
    server.set_handler(cmds.CMD_DRIVE, lambda env: (True, 'ok'))

    _env, ack = send_cmd(dealer, server, cmds.CMD_ESTOP, {'engage': True})
    assert ack.payload['ok'] is True
    assert server.estop_latched is True

    _env2, ack2 = send_cmd(dealer, server, cmds.CMD_DRIVE, {'vx': 0.2, 'wz': 0.0}, seq=2)
    assert ack2.payload['ok'] is False
    assert 'estop' in ack2.payload['detail']

    _env3, ack3 = send_cmd(dealer, server, cmds.CMD_ESTOP, {'engage': False}, seq=3)
    assert server.estop_latched is False
    _env4, ack4 = send_cmd(dealer, server, cmds.CMD_DRIVE, {'vx': 0.2, 'wz': 0.0}, seq=4)
    assert ack4.payload['ok'] is True


def test_unhandled_command_acked_not_ok_and_ping_pongs(rig):
    server, dealer, _sub = rig
    _env, ack = send_cmd(dealer, server, cmds.CMD_SERVO, {'deg': 90})
    assert ack.payload['ok'] is False
    assert ack.payload['detail'] == 'no handler'

    _env2, ack2 = send_cmd(dealer, server, cmds.CMD_PING, {}, seq=2)
    assert ack2.payload['ok'] is True and ack2.payload['detail'] == 'pong'


def test_crashing_handler_is_contained(rig):
    server, dealer, _sub = rig

    def boom(env):
        raise RuntimeError('handler bug')

    server.set_handler(cmds.CMD_GOAL, boom)
    _env, ack = send_cmd(dealer, server, cmds.CMD_GOAL, {'x': 1, 'y': 2})
    assert ack.payload['ok'] is False
    assert 'handler error' in ack.payload['detail']
