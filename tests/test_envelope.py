import msgpack
import pytest

from gpcore.protocol import Envelope, ProtocolError, SeqTracker, decode, encode, make_envelope


def test_roundtrip_all_fields():
    env = make_envelope('tele.full', {'enc': [1, 2, 3, 4], 'pwm': 180},
                        seq=42, run_id='20260610T1200-abcd', src='robot2',
                        t_mono=123.456, t_wall=1750000000.0)
    out = decode(encode(env))
    assert out == env


def test_roundtrip_binary_payload():
    scan = bytes(range(256)) * 4
    env = make_envelope('tele.scan', {'ranges': scan, 'a0': -3.14},
                        seq=1, run_id='r', src='robot1')
    out = decode(encode(env))
    assert out.payload['ranges'] == scan


def test_wrong_version_rejected():
    raw = msgpack.packb({'v': 99, 'seq': 1, 't_mono': 0.0, 't_wall': 0.0,
                         'run_id': 'r', 'src': 's', 'type': 't', 'payload': {}},
                        use_bin_type=True)
    with pytest.raises(ProtocolError, match='version'):
        decode(raw)


def test_missing_field_rejected():
    raw = msgpack.packb({'v': 1, 'seq': 1}, use_bin_type=True)
    with pytest.raises(ProtocolError, match='missing'):
        decode(raw)


def test_garbage_bytes_rejected():
    with pytest.raises(ProtocolError):
        decode(b'\xc1\x00\xff not msgpack')
    with pytest.raises(ProtocolError):
        decode(msgpack.packb([1, 2, 3]))  # valid msgpack, wrong shape


def test_seq_tracker_counts_gaps_and_duplicates():
    t = SeqTracker()
    assert t.feed(10) == 0          # first message — baseline
    assert t.feed(11) == 0
    assert t.feed(14) == 2          # 12, 13 lost
    assert t.feed(14) == 0          # duplicate
    assert t.feed(1) == 0           # sender restart — not loss
    assert t.gaps == 1
    assert t.lost == 2
    assert t.duplicates == 1
    assert t.received == 5
    assert 0 < t.loss_ratio() < 1


def test_envelope_age():
    env = make_envelope('x', {}, seq=0, run_id='r', src='s', t_mono=100.0)
    assert env.age_s(now_mono=100.5) == pytest.approx(0.5)
