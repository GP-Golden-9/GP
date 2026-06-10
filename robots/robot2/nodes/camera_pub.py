#!/usr/bin/env python3
"""Robot 2 camera publisher — standalone, NO ROS dependency.

Runs as its own systemd unit so video keeps flowing even if the entire ROS
stack on the Pi crashes (and vice versa: a camera fault can't take down
control). Replaces classification/tcp_rasp*.py.

Publishes BOTH:
  :5560  framed protocol — multipart [envelope(video.meta), jpeg bytes]
         (capture timestamp + seq → the Qt dashboard shows true frame age)
  :5555  legacy raw JPEG (NiceGUI dashboard) while migration is in progress;
         disable with camera.legacy_port: 0 in config/robot2.yaml
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import cv2
import zmq

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', '..', '..', 'common'))
from gpcore.config import get_path, load_config              # noqa: E402
from gpcore.logging_setup import new_run_id, setup_logging   # noqa: E402
from gpcore.protocol import channels as ch                   # noqa: E402
from gpcore.protocol.envelope import make_envelope, pack_with_blob  # noqa: E402

REOPEN_AFTER_FAILURES = 30      # consecutive read failures → reopen device


def open_camera(device: int, width: int, height: int, fps: int):
    cam = cv2.VideoCapture(device)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cam.set(cv2.CAP_PROP_FPS, fps)
    return cam


def main():
    ap = argparse.ArgumentParser()
    default_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               '..', '..', '..', 'config', 'robot2.yaml')
    ap.add_argument('--config', default=default_cfg)
    args = ap.parse_args()

    cfg = load_config(args.config)
    run_id = os.environ.get('GP_RUN_ID') or new_run_id()
    log = setup_logging('camera_pub', run_id=run_id)

    device = get_path(cfg, 'camera.device', 0)
    width = get_path(cfg, 'camera.width', 640)
    height = get_path(cfg, 'camera.height', 480)
    fps = get_path(cfg, 'camera.fps', 15)
    quality = get_path(cfg, 'camera.jpeg_quality', 35)
    video_port = get_path(cfg, 'zmq.video', 5560)
    legacy_port = get_path(cfg, 'camera.legacy_port', 0)
    src = get_path(cfg, 'robot.id', 'robot2')

    ctx = zmq.Context()
    pub = ctx.socket(zmq.PUB)
    pub.setsockopt(zmq.SNDHWM, 2)
    pub.setsockopt(zmq.LINGER, 0)
    pub.bind(f'tcp://*:{video_port}')

    legacy = None
    if legacy_port:
        legacy = ctx.socket(zmq.PUB)
        legacy.setsockopt(zmq.SNDHWM, 1)
        legacy.setsockopt(zmq.LINGER, 0)
        legacy.bind(f'tcp://*:{legacy_port}')

    log.info('camera publisher up', extra={'kv': {
        'device': device, 'res': f'{width}x{height}', 'fps': fps,
        'jpeg_q': quality, 'port': video_port, 'legacy_port': legacy_port}})

    cam = open_camera(device, width, height, fps)
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
    frame_interval = 1.0 / max(1, fps)
    seq = 0
    failures = 0
    next_frame_at = time.monotonic()

    try:
        while True:
            now = time.monotonic()
            if now < next_frame_at:
                time.sleep(min(0.005, next_frame_at - now))
                continue
            next_frame_at = max(next_frame_at + frame_interval, now)

            ok, frame = cam.read()
            t_cap = time.monotonic()
            if not ok or frame is None:
                failures += 1
                if failures >= REOPEN_AFTER_FAILURES:
                    log.error('camera stalled — reopening device',
                              extra={'kv': {'failures': failures}})
                    cam.release()
                    time.sleep(1.0)
                    cam = open_camera(device, width, height, fps)
                    failures = 0
                continue
            failures = 0

            ok, buf = cv2.imencode('.jpg', frame, encode_params)
            if not ok:
                continue
            jpeg = buf.tobytes()
            seq += 1

            meta = make_envelope(ch.VIDEO_META, {
                'w': int(frame.shape[1]), 'h': int(frame.shape[0]),
                'fmt': 'jpeg', 'cap_t_mono': t_cap, 'frame_id': seq,
            }, seq=seq, run_id=run_id, src=src)
            try:
                # single-part (header-prefixed): CONFLATE-safe on the consumer
                pub.send(pack_with_blob(meta, jpeg), zmq.NOBLOCK)
            except zmq.Again:
                pass
            if legacy is not None:
                try:
                    legacy.send(jpeg, zmq.NOBLOCK)
                except zmq.Again:
                    pass
    except KeyboardInterrupt:
        pass
    finally:
        cam.release()
        pub.close(0)
        if legacy is not None:
            legacy.close(0)
        log.info('camera publisher down')


if __name__ == '__main__':
    main()
