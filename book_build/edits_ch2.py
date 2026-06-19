# -*- coding: utf-8 -*-
# Chapter 2 (Literature Review) machine-applyable edits.
# Each "find" is verified to occur EXACTLY ONCE as a contiguous substring of a
# single paragraph in docx_paras.txt. Source: docs/book_corrections/chapter2_corrections.md
#
# Anchors (docx_paras.txt lines):
#   Edit 1 -> P00510 (line 469)   YOLO default-model inversion (sec 2.5.2)
#   Edit 2 -> P00568 (line 526)   summary inverted model emphasis (sec 2.9)
#   Edit 3 -> P00458 (line 419)   differential-drive wording (sec 2.2.2)
#   Edit 4 -> P00529 (line 487)   in-process YOLO wording (sec 2.6.3)

EDITS = [
    {
        "type": "para",
        "find": "The dashboard supports selectable YOLO models, with the default configuration using a fire-detection model (fire.pt) to identify fire-related hazards and project detections onto the shared map. General object and human detection remains available as an alternative model configuration for broader situational awareness.",
        "replace": "The dashboard supports selectable YOLO models. The default (primary) model is a clean COCO-trained network (yolov8s.pt) used for general object and human detection — for example person, dog, and cat — and to project detections onto the shared map. A secondary, fire-only model (fire.pt) is available for identifying fire-related hazards in emergency-response scenarios. The fire-tuned model is deliberately kept as the secondary option and is never used as the primary, because its fire fine-tuning degrades its general (COCO) detection performance.",
        "expect": 1,
        "note": "Edit 1 / sec 2.5.2: YOLO default-model roles were inverted (fire.pt is secondary; yolov8s.pt COCO is primary).",
    },
    {
        "type": "para",
        "find": "In the area of perception, YOLO-based object detection methods emerged as a practical choice for real-time visual detection, with the deployed system focusing primarily on fire, smoke, and flame detection to support emergency response scenarios.",
        "replace": "In the area of perception, YOLO-based object detection methods emerged as a practical choice for real-time visual detection. The deployed system uses a clean COCO-trained model as its primary detector for general object and human detection, with a dedicated secondary model available for fire, smoke, and flame detection to support emergency-response scenarios.",
        "expect": 1,
        "note": "Edit 2 / sec 2.9 summary: same inverted model emphasis as Edit 1.",
    },
    {
        "type": "para",
        "find": "These findings directly influenced our project’s decision to adopt ROS, use a differential-drive configuration, and rely on 2D LiDAR for mapping and localization",
        "replace": "These findings directly influenced our project’s decision to adopt ROS, use a four-wheel skid-steer base controlled kinematically as a differential drive, and rely on 2D LiDAR for mapping and localization",
        "expect": 1,
        "note": "Edit 3 / sec 2.2.2: 'differential-drive configuration' conflicts with Beta's four-wheel hardware.",
    },
    {
        "type": "para",
        "find": "its ability to integrate directly with ZeroMQ transport and in-process YOLO inference without browser-imposed constraints.",
        "replace": "its ability to integrate directly with ZeroMQ transport and to host YOLO inference inside the desktop application. Rather than running the model in the UI thread, the console isolates YOLO in a dedicated crash-isolated subprocess, so a model crash, hang, or out-of-memory event cannot freeze or kill the operator console — a level of native integration and process control that a browser-based dashboard cannot provide.",
        "expect": 1,
        "note": "Edit 4 / sec 2.6.3: 'in-process YOLO' should reflect the crash-isolated subprocess design.",
    },
]
