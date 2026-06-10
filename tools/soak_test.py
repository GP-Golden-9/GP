#!/usr/bin/env python3
"""Soak test — measures the gateway protocol KPIs against a live robot
(or the sim) and verdicts them against the acceptance gates.

    python tools/soak_test.py --host robot2.local --minutes 30
    python tools/soak_test.py --host 127.0.0.1 --minutes 1      # vs sim

KPIs and gates (from the remediation plan):
    telemetry seq loss        < 1 %
    video fps                 ≥ 12
    video capture-age p95     ≤ 350 ms
    map inter-arrival p95     ≤ 2.0 s
    cmd→ack RTT p95           ≤ 150 ms
    health stream             alive (gap p95 ≤ 2.5 s)

Writes docs/baseline/soak_<host>_<UTC>.json and prints a PASS/FAIL table.
Run the kill -9 recovery drills manually while this is running — outages
show up in the max-gap columns.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone

import zmq

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'common'))
from gpcore.protocol import channels as ch                       # noqa: E402
from gpcore.protocol import commands as cmds                     # noqa: E402
from gpcore.protocol.envelope import (ProtocolError, SeqTracker, decode,  # noqa: E402
                                      encode, unpack_with_blob)

GATES = {
    'tele_loss_pct': ('<', 1.0),
    'video_fps': ('>=', 12.0),
    'video_age_p95_ms': ('<=', 350.0),
    'map_gap_p95_s': ('<=', 2.0),
    'ack_p95_ms': ('<=', 150.0),
    'health_gap_p95_s': ('<=', 2.5),
}


def pct(sorted_vals, p):
    if not sorted_vals:
        return None
    return sorted_vals[min(len(sorted_vals) - 1, int(p * len(sorted_vals)))]


class Collector:
    def __init__(self):
        self.lock = threading.Lock()
        self.arrivals: dict[str, list[float]] = {k: [] for k in
                                                 ('tele', 'scan', 'map', 'health', 'video')}
        self.video_ages: list[float] = []
        self.ack_rtts: list[float] = []
        self.tele_tracker = SeqTracker()
        self.video_offset: float | None = None

    def hit(self, stream: str):
        with self.lock:
            self.arrivals[stream].append(time.monotonic())


def sub_thread(host: str, port: int, handler, stop: threading.Event):
    ctx = zmq.Context.instance()
    s = ctx.socket(zmq.SUB)
    s.setsockopt(zmq.SUBSCRIBE, b'')
    s.setsockopt(zmq.RCVTIMEO, 500)
    s.setsockopt(zmq.LINGER, 0)
    s.connect(f'tcp://{host}:{port}')
    while not stop.is_set():
        try:
            handler(s.recv())
        except zmq.Again:
            continue
        except zmq.ZMQError:
            break
    s.close(0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', required=True)
    ap.add_argument('--minutes', type=float, default=30)
    ap.add_argument('--out-dir', default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'baseline'))
    args = ap.parse_args()

    col = Collector()
    stop = threading.Event()

    def on_tele(raw):
        try:
            env = decode(raw)
        except ProtocolError:
            return
        if env.type == ch.TELE_FULL:
            col.tele_tracker.feed(env.seq)
            col.hit('tele')
        elif env.type == ch.TELE_SCAN:
            col.hit('scan')

    def on_map(raw):
        col.hit('map')

    def on_health(raw):
        col.hit('health')

    def on_video(raw):
        try:
            meta, _jpeg = unpack_with_blob(raw)
        except ProtocolError:
            return
        col.hit('video')
        cap = meta.payload.get('cap_t_mono')
        if isinstance(cap, (int, float)):
            now = time.monotonic()
            off = now - cap
            col.video_offset = off if col.video_offset is None else min(col.video_offset, off)
            with col.lock:
                col.video_ages.append(now - (cap + col.video_offset))

    threads = [
        threading.Thread(target=sub_thread, args=(args.host, ch.PORT_TELEMETRY, on_tele, stop), daemon=True),
        threading.Thread(target=sub_thread, args=(args.host, ch.PORT_MAP, on_map, stop), daemon=True),
        threading.Thread(target=sub_thread, args=(args.host, ch.PORT_HEALTH, on_health, stop), daemon=True),
        threading.Thread(target=sub_thread, args=(args.host, ch.PORT_VIDEO, on_video, stop), daemon=True),
    ]
    for t in threads:
        t.start()

    # ping loop on the command channel → ack RTTs
    def ping_loop():
        ctx = zmq.Context.instance()
        d = ctx.socket(zmq.DEALER)
        d.setsockopt(zmq.LINGER, 0)
        d.connect(f'tcp://{args.host}:{ch.PORT_COMMAND}')
        seq = 0
        while not stop.is_set():
            seq += 1
            env = cmds.make_command(cmds.CMD_PING, {}, seq=seq, run_id='soak', src='soak')
            t0 = time.monotonic()
            d.send(encode(env))
            if d.poll(1000):
                try:
                    d.recv(zmq.NOBLOCK)
                    with col.lock:
                        col.ack_rtts.append(time.monotonic() - t0)
                except zmq.Again:
                    pass
            time.sleep(0.5)
        d.close(0)

    threading.Thread(target=ping_loop, daemon=True).start()

    total_s = args.minutes * 60
    t_end = time.monotonic() + total_s
    print(f'[soak] {args.minutes:g} min against {args.host} -- '
          'run your kill/recovery drills now')
    try:
        while time.monotonic() < t_end:
            time.sleep(5)
            with col.lock:
                line = ' | '.join(f'{k}:{len(v)}' for k, v in col.arrivals.items())
            print(f'[soak] {int(t_end - time.monotonic()):5d}s left | {line} '
                  f'| acks:{len(col.ack_rtts)}')
    except KeyboardInterrupt:
        print('[soak] interrupted -- evaluating what we have')
        total_s = max(1.0, total_s - (t_end - time.monotonic()))
    stop.set()
    time.sleep(0.8)

    # ── evaluate ──
    def gaps(stream):
        a = col.arrivals[stream]
        return sorted(b - x for x, b in zip(a, a[1:]))

    video_n = len(col.arrivals['video'])
    ages = sorted(col.video_ages)
    acks = sorted(col.ack_rtts)
    metrics = {
        'tele_rate_hz': round(len(col.arrivals['tele']) / total_s, 2),
        'tele_loss_pct': round(col.tele_tracker.loss_ratio() * 100, 3),
        'video_fps': round(video_n / total_s, 2),
        'video_age_p95_ms': round((pct(ages, 0.95) or 0) * 1000, 1) if ages else None,
        'map_gap_p95_s': round(pct(gaps('map'), 0.95), 2) if len(col.arrivals['map']) > 2 else None,
        'map_gap_max_s': round(gaps('map')[-1], 2) if len(col.arrivals['map']) > 2 else None,
        'health_gap_p95_s': round(pct(gaps('health'), 0.95), 2) if len(col.arrivals['health']) > 2 else None,
        'ack_p95_ms': round((pct(acks, 0.95) or 0) * 1000, 1) if acks else None,
        'ack_count': len(acks),
        'scan_rate_hz': round(len(col.arrivals['scan']) / total_s, 2),
    }

    print('\n==== SOAK RESULTS ====')
    overall = True
    for key, (op, limit) in GATES.items():
        val = metrics.get(key)
        if val is None:
            ok, shown = False, 'NO DATA'
        else:
            ok = (val < limit if op == '<' else
                  val <= limit if op == '<=' else val >= limit)
            shown = val
        overall &= ok
        print(f'  {"PASS" if ok else "FAIL":4} {key:20} {shown}  (gate {op} {limit})')
    for k, v in metrics.items():
        if k not in GATES:
            print(f'       {k:20} {v}')
    print(f'\n  OVERALL: {"PASS" if overall else "FAIL"}')

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = os.path.join(args.out_dir,
                       f'soak_{args.host.replace(".", "_")}_{stamp}.json')
    with open(out, 'w') as f:
        json.dump({'host': args.host, 'minutes': args.minutes,
                   'metrics': metrics, 'pass': overall}, f, indent=2)
    print(f'  report: {out}')
    return 0 if overall else 1


if __name__ == '__main__':
    sys.exit(main())
