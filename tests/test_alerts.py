"""Alert engine tests — pure logic, driven without a Qt event loop
(QTimer sweeps are invoked directly)."""

import sys

import pytest

sys.path.insert(0, 'dashboard_qt')

from PySide6.QtCore import QCoreApplication

from alerts import (AlertManager, AlertState, CLEAR_AFTER_S, FIRE_RAISE_HITS)


@pytest.fixture(scope='module')
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture()
def mgr(qapp):
    m = AlertManager()
    m.raised, m.cleared, m.acked, m.lines = [], [], [], []
    m.alertRaised.connect(lambda k, info: m.raised.append((k, info)))
    m.alertCleared.connect(lambda k: m.cleared.append(k))
    m.alertAcked.connect(lambda k: m.acked.append(k))
    m.logEvent.connect(lambda s: m.lines.append(s))
    yield m
    m._sweep.stop()


def feed_fire(m, n, label='fire', conf=0.9):
    for _ in range(n):
        m.process_fire_detections('robot2', [(label, conf)])


def test_single_detection_does_not_raise(mgr):
    feed_fire(mgr, 1)
    assert mgr.raised == []
    assert mgr.state('FIRE') is AlertState.CLEAR


def test_debounced_raise_after_hits(mgr):
    feed_fire(mgr, FIRE_RAISE_HITS)
    assert len(mgr.raised) == 1
    kind, info = mgr.raised[0]
    assert kind == 'FIRE'
    assert info['robot'] == 'robot2'
    assert info['confidence'] == 90
    assert mgr.state('FIRE') is AlertState.ACTIVE


def test_fire_hydrant_must_not_raise_fire_alarm(mgr):
    # 'fire hydrant' contains the substring 'fire' — exact matching required
    feed_fire(mgr, 10, label='fire hydrant', conf=0.99)
    assert mgr.raised == []


def test_low_confidence_ignored(mgr):
    feed_fire(mgr, 10, conf=0.3)
    assert mgr.raised == []


def test_acknowledge_flow(mgr):
    feed_fire(mgr, FIRE_RAISE_HITS)
    mgr.acknowledge('FIRE')
    assert mgr.acked == ['FIRE']
    assert mgr.state('FIRE') is AlertState.ACKED
    mgr.acknowledge('FIRE')                  # idempotent
    assert mgr.acked == ['FIRE']


def test_auto_clear_after_quiet_period(mgr):
    feed_fire(mgr, FIRE_RAISE_HITS)
    tr = mgr._k[list(mgr._k)[0]]             # FIRE tracker
    tr.last_positive -= (CLEAR_AFTER_S + 1)  # simulate quiet period
    mgr._sweep_clears()
    assert mgr.cleared == ['FIRE']
    assert mgr.state('FIRE') is AlertState.CLEAR
    # a fresh fire afterwards must raise again (hits were reset)
    feed_fire(mgr, FIRE_RAISE_HITS)
    assert len(mgr.raised) == 2


def test_gas_needs_consecutive_polls(mgr):
    mgr.process_gas('robot3', True, 3100)
    assert mgr.raised == []
    mgr.process_gas('robot3', False, 100)    # flag dropped → streak resets
    mgr.process_gas('robot3', True, 3100)
    assert mgr.raised == []
    mgr.process_gas('robot3', True, 3200)    # 2 consecutive → raise
    assert len(mgr.raised) == 1
    assert mgr.raised[0][0] == 'GAS'


def test_drill_is_labeled(mgr):
    mgr.drill('FIRE')
    assert len(mgr.raised) == 1
    assert mgr.raised[0][1]['drill'] is True
    assert any('DRILL' in line for line in mgr.lines)


def test_configurable_threshold(qapp):
    # fire.pt scores 28-37% on real fire — a 0.25 threshold must catch it
    m = AlertManager(fire_conf_min=0.25)
    raised = []
    m.alertRaised.connect(lambda k, info: raised.append(k))
    for _ in range(FIRE_RAISE_HITS):
        m.process_fire_detections('robot2', [('Fire', 0.28)])
    m._sweep.stop()
    assert raised == ['FIRE']
