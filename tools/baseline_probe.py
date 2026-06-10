#!/usr/bin/env python3
"""
Baseline Probe — measures the CURRENT (legacy) system so every later fix is
verifiable against numbers, not impressions.

Run on the LAPTOP while the robot is up and being driven around:

    python tools/baseline_probe.py --host robot2.local --duration 600
    python tools/baseline_probe.py --host robot.local  --duration 600 --no-video

Measures:
  * ZMQ video (port 5555): frames/sec, frame size, inter-arrival gap p50/p95/max
  * rosbridge (port 9090) topic inter-arrival for /map /odom /scan /motor_status
    (requires `pip install roslibpy`; skipped automatically if missing)

Outputs:
  * docs/baseline/probe_<host>_<UTCstamp>.csv   (one row per event)
  * docs/baseline/probe_<host>_<UTCstamp>.json  (summary statistics)
  * printed summary table

Pi-side measurements (run over SSH, paste into docs/baseline/robotN_<date>.md):
  vcgencmd get_throttled        # 0x0 = healthy; 0x50005 = undervoltage NOW+past
  vcgencmd measure_temp
  top -b -n 1 | head -20
  dmesg | grep -iE 'usb|under-volt|brown'
  iwconfig wlan0 | grep -E 'Signal|Bit Rate'
  udevadm info -q property -n /dev/ttyUSB0 | grep -E 'ID_VENDOR_ID|ID_MODEL'
  udevadm info -q property -n /dev/ttyUSB1 | grep -E 'ID_VENDOR_ID|ID_MODEL'
"""

import argparse
import csv
import json
import os
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone

try:
    import zmq
except ImportError:
    zmq = None

try:
    import roslibpy
except ImportError:
    roslibpy = None

ROS_TOPICS = {
    '/map': 'nav_msgs/OccupancyGrid',
    '/odom': 'nav_msgs/Odometry',
    '/scan': 'sensor_msgs/LaserScan',
    '/motor_status': 'std_msgs/String',
}


class StreamStats:
    """Arrival statistics for one stream (video or a ROS topic)."""

    def __init__(self, name):
        self.name = name
        self.arrivals = []      # monotonic timestamps
        self.sizes = []         # bytes (video only)
        self.lock = threading.Lock()

    def record(self, size=0):
        with self.lock:
            self.arrivals.append(time.monotonic())
            if size:
                self.sizes.append(size)

    def summary(self):
        with self.lock:
            arrivals = list(self.arrivals)
            sizes = list(self.sizes)
        if len(arrivals) < 2:
            return {'name': self.name, 'count': len(arrivals), 'note': 'insufficient data'}
        gaps = sorted(b - a for a, b in zip(arrivals, arrivals[1:]))
        duration = arrivals[-1] - arrivals[0]
        pct = lambda p: gaps[min(len(gaps) - 1, int(p * len(gaps)))]
        out = {
            'name': self.name,
            'count': len(arrivals),
            'rate_hz': round(len(arrivals) / duration, 2) if duration > 0 else 0.0,
            'gap_p50_ms': round(pct(0.50) * 1000, 1),
            'gap_p95_ms': round(pct(0.95) * 1000, 1),
            'gap_max_ms': round(gaps[-1] * 1000, 1),
        }
        if sizes:
            out['avg_size_kb'] = round(sum(sizes) / len(sizes) / 1024, 1)
        return out


def video_thread(host, port, stats, stop_event, writer, writer_lock):
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.SUB)
    sock.setsockopt(zmq.SUBSCRIBE, b'')
    sock.setsockopt(zmq.RCVTIMEO, 1000)
    sock.setsockopt(zmq.LINGER, 0)
    # NOTE: deliberately NO CONFLATE — we want true arrival behavior, queue included.
    sock.connect(f'tcp://{host}:{port}')
    print(f'[video] subscribed tcp://{host}:{port}')
    while not stop_event.is_set():
        try:
            frame = sock.recv()
        except zmq.Again:
            continue
        except zmq.ZMQError:
            break
        stats.record(size=len(frame))
        with writer_lock:
            writer.writerow([f'{time.monotonic():.6f}', 'video', len(frame)])
    sock.close(0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--host', required=True, help='robot hostname or IP (e.g. robot2.local)')
    ap.add_argument('--duration', type=int, default=600, help='seconds to run (default 600)')
    ap.add_argument('--video-port', type=int, default=5555)
    ap.add_argument('--ros-port', type=int, default=9090)
    ap.add_argument('--no-video', action='store_true')
    ap.add_argument('--no-ros', action='store_true')
    ap.add_argument('--out-dir', default=os.path.join(os.path.dirname(__file__), '..', 'docs', 'baseline'))
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    base = os.path.join(args.out_dir, f'probe_{args.host.replace(".", "_")}_{stamp}')

    csv_path = base + '.csv'
    csv_file = open(csv_path, 'w', newline='')
    writer = csv.writer(csv_file)
    writer.writerow(['t_mono', 'stream', 'size_bytes'])
    writer_lock = threading.Lock()

    stop_event = threading.Event()
    all_stats = {}
    threads = []

    if not args.no_video:
        if zmq is None:
            print('[video] pyzmq not installed — skipping video probe')
        else:
            st = all_stats['video'] = StreamStats('video')
            t = threading.Thread(target=video_thread,
                                 args=(args.host, args.video_port, st, stop_event, writer, writer_lock),
                                 daemon=True)
            t.start()
            threads.append(t)

    ros_client = None
    if not args.no_ros:
        if roslibpy is None:
            print('[ros] roslibpy not installed — skipping ROS probe (pip install roslibpy)')
        else:
            ros_client = roslibpy.Ros(host=args.host, port=args.ros_port)

            def make_cb(stats_obj, name):
                def cb(_msg):
                    stats_obj.record()
                    with writer_lock:
                        writer.writerow([f'{time.monotonic():.6f}', name, 0])
                return cb

            def on_ready():
                print(f'[ros] connected ws://{args.host}:{args.ros_port}')
                for topic, mtype in ROS_TOPICS.items():
                    st = all_stats[topic] = StreamStats(topic)
                    roslibpy.Topic(ros_client, topic, mtype).subscribe(make_cb(st, topic))

            ros_client.on_ready(on_ready)
            threading.Thread(target=ros_client.run_forever, daemon=True).start()

    print(f'[probe] running for {args.duration}s — drive the robot around now '
          f'(forward >2s holds, turns, map growth)…')
    t_end = time.monotonic() + args.duration
    try:
        while time.monotonic() < t_end:
            time.sleep(5)
            line = ' | '.join(
                f'{s.name}:{len(s.arrivals)}' for s in all_stats.values())
            print(f'[probe] {int(t_end - time.monotonic()):4d}s left | {line}')
    except KeyboardInterrupt:
        print('\n[probe] interrupted — writing what we have')

    stop_event.set()
    if ros_client is not None:
        try:
            ros_client.terminate()
        except Exception:
            pass
    time.sleep(1.2)
    csv_file.close()

    summaries = [s.summary() for s in all_stats.values()]
    with open(base + '.json', 'w') as f:
        json.dump({'host': args.host, 'stamp': stamp, 'duration_s': args.duration,
                   'streams': summaries}, f, indent=2)

    print('\n===== BASELINE SUMMARY =====')
    for s in summaries:
        print('  ' + json.dumps(s))
    print(f'\nWrote {csv_path}\n      {base}.json')
    print('Paste the summary into docs/baseline/ and fill in the verdict table '
          'from docs/baseline/README.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
