#!/usr/bin/env python3
"""Probe every fire-capable model against a test image at low confidence —
used to choose the best model + threshold for the alert pipeline."""

import os
import sys

import cv2

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'dashboard_qt'))

from inference.concat_head import install  # noqa: E402

install()
from ultralytics import YOLO  # noqa: E402

IMAGE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    REPO, 'dashboard_qt', 'sim', 'assets', 'fire_test.jpg')

img = cv2.imread(IMAGE)
if img is None:
    sys.exit(f'cannot read {IMAGE}')
print(f'image: {IMAGE} {img.shape}')

for model_name in ('yolov8n-fire.pt', 'fire.pt'):
    path = os.path.join(REPO, 'models', model_name)
    try:
        m = YOLO(path)
        names = m.names
        head = dict(list(names.items())[:3])
        print(f'--- {model_name}: {len(names)} classes, e.g. {head}')
        for label, frame in (('640x480', cv2.resize(img, (640, 480))),
                             ('native', img)):
            r = m(frame, verbose=False, conf=0.05)[0]
            dets = []
            if r.boxes is not None:
                for c, cf in zip(r.boxes.cls.tolist(), r.boxes.conf.tolist()):
                    dets.append((str(names.get(int(c), int(c))),
                                 round(float(cf) * 100)))
            dets.sort(key=lambda d: -d[1])
            print(f'    {label}: {dets[:6] or "no detections at conf>=5%"}')
    except Exception as exc:
        print(f'--- {model_name}: FAILED {type(exc).__name__}: {exc}')
