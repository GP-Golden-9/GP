#!/usr/bin/env python3
"""Standalone fire-model check — answers three questions before any
end-to-end test:

  1. does yolov8n-fire.pt load with the ConcatHead monkey-patch?
  2. what class names does it output (what will the alert engine see)?
  3. does it fire on the simulator's synthetic flame, and at what confidence?

    python tools/test_fire_model.py [--model models/yolov8n-fire.pt]
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'dashboard_qt'))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default=os.path.join(REPO, 'models', 'yolov8n-fire.pt'))
    args = ap.parse_args()

    print(f'[1/3] loading {os.path.basename(args.model)} (ConcatHead patched)…')
    from inference.concat_head import install
    install()
    from ultralytics import YOLO
    t0 = time.monotonic()
    model = YOLO(args.model)
    print(f'      loaded in {time.monotonic() - t0:.1f}s')

    names = getattr(model, 'names', {}) or {}
    print(f'[2/3] model classes ({len(names)}): {dict(list(names.items())[:90])}')
    fire_like = [n for n in names.values()
                 if any(t in str(n).lower() for t in ('fire', 'smoke', 'flame'))]
    print(f'      fire-like labels the alert engine will match: {fire_like or "NONE!"}')

    print('[3/3] inference on the simulator synthetic flame…')
    from sim.fake_gateway import draw_flame
    rng = np.random.default_rng(7)
    best: dict[str, float] = {}
    times = []
    for i in range(12):
        frame = np.zeros((480, 640, 3), np.uint8)
        frame[:] = (40, 30, 24)
        draw_flame(frame, 320, 300, t=i * 0.13, rng=rng)
        t0 = time.monotonic()
        results = model(frame, verbose=False)
        times.append(time.monotonic() - t0)
        boxes = results[0].boxes
        if boxes is not None and len(boxes) > 0:
            for cls_id, conf in zip(boxes.cls.tolist(), boxes.conf.tolist()):
                label = str(names.get(int(cls_id), int(cls_id)))
                best[label] = max(best.get(label, 0.0), float(conf))
    avg_ms = sum(times) / len(times) * 1000
    print(f'      inference avg {avg_ms:.0f} ms/frame (CPU) over {len(times)} frames')
    if best:
        for label, conf in sorted(best.items(), key=lambda kv: -kv[1]):
            mark = '🔥' if any(t in label.lower() for t in ('fire', 'smoke', 'flame')) else '  '
            print(f'      {mark} {label}: max conf {conf * 100:.0f}%')
    else:
        print('      no detections on the synthetic flame — use a real fire '
              'photo: python dashboard_qt/sim/fake_gateway.py --fire-image <jpg>')
    return 0


if __name__ == '__main__':
    sys.exit(main())
