import pytest

from gpcore.protocol import commands as cmds
from gpcore.protocol.commands import (CommandDeduper, CommandError, DriveDeadman,
                                      make_ack, make_command, validate_command)


def test_make_command_attaches_cmd_id():
    env = make_command(cmds.CMD_PUMP, {'on': True}, seq=1, run_id='r', src='dash')
    assert env.type == 'cmd.pump'
    assert len(env.payload['cmd_id']) == 12
    assert validate_command(env) == env.payload['cmd_id']


def test_retry_reuses_same_cmd_id():
    first = make_command(cmds.CMD_SERVO, {'deg': 90}, seq=1, run_id='r', src='d')
    retry = make_command(cmds.CMD_SERVO, {'deg': 90}, seq=2, run_id='r', src='d',
                         cmd_id=first.payload['cmd_id'])
    assert retry.payload['cmd_id'] == first.payload['cmd_id']


def test_unknown_command_rejected():
    with pytest.raises(CommandError):
        make_command('cmd.selfdestruct', {}, seq=1, run_id='r', src='d')


def test_validate_requires_cmd_id():
    env = make_command(cmds.CMD_DRIVE, {'vx': 0.1, 'wz': 0}, seq=1, run_id='r', src='d')
    env.payload.pop('cmd_id')
    with pytest.raises(CommandError, match='cmd_id'):
        validate_command(env)


def test_ack_echoes_cmd_id():
    env = make_command(cmds.CMD_GOAL, {'x': 1, 'y': 2}, seq=5, run_id='r', src='d')
    ack = make_ack(env, ok=True, detail='accepted', seq=9, run_id='r', src='robot2')
    assert ack.type == 'ack'
    assert ack.payload['cmd_id'] == env.payload['cmd_id']
    assert ack.payload['cmd_type'] == 'cmd.goal'


def test_reset_map_is_a_known_exactly_once_command():
    # A retried cmd.reset_map must NOT restart the robot stack twice.
    env = make_command(cmds.CMD_RESET_MAP, {}, seq=1, run_id='r', src='dash')
    assert validate_command(env) == env.payload['cmd_id']
    assert cmds.CMD_RESET_MAP in cmds.EXACTLY_ONCE


def test_deduper_lru():
    d = CommandDeduper(capacity=2)
    assert d.seen_before('a') is False
    assert d.seen_before('a') is True
    d.seen_before('b')
    d.seen_before('c')          # evicts 'a'
    assert d.seen_before('a') is False


def test_drive_deadman_trips_once_on_silence():
    dm = DriveDeadman(timeout_s=0.6)
    dm.feed(0.15, 0.0, now_mono=100.0)
    assert dm.should_stop(100.5) is False     # still within window
    assert dm.should_stop(100.7) is True      # silence > 0.6s while moving
    assert dm.should_stop(101.5) is False     # only trips once
    dm.feed(0.0, 0.0, now_mono=102.0)         # explicit stop arrived
    assert dm.should_stop(103.0) is False     # not moving → nothing to stop
