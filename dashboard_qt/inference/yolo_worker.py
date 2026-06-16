"""Crash-isolated YOLO inference.

The model runs in a CHILD PROCESS: a torch/ultralytics crash, OOM, or hang
can never freeze or kill the operator console. The parent-side
``YoloManager``:

  * feeds the newest JPEG (latest-wins, queue depth 1 — stale frames dropped)
  * receives annotated JPEGs
  * watches for hangs (no result for 5 s while frames flow) and silent death,
    then respawns the child — and tells the UI to fall back to RAW video

Child protocol (multiprocessing queues):
  in:  ('frame', frame_id, jpeg_bytes) | ('model', path) | ('stop',)
  out: ('ready', model_name) | ('annotated', frame_id, jpeg_bytes)
       | ('unavailable', reason) | ('error', text)
"""

from __future__ import annotations

import multiprocessing as mp
import queue as queue_mod
import threading
import time

from PySide6.QtCore import QObject, Signal

# Generous: the child warms the model before 'ready', so a healthy worker
# answers every frame in well under a second — but a busy CPU (screen
# recording, model swap) must not get the child shot for a slow burst.
HANG_TIMEOUT_S = 12.0
MAX_RESPAWNS_PER_MIN = 3

# Labels routed to the secondary fire model, never to the primary COCO net.
_FIRE_NAMES = ('fire', 'smoke', 'flame')


def _resolve_class_ids(model, class_names):
    """Map wanted class NAMES → the model's class IDs (None = all classes).

    'fire' is accepted for the model's 'Fire' label (case-insensitive). A
    requested name the model doesn't know is dropped with no error so a
    COCO-only model still runs (it just won't surface 'fire')."""
    if not class_names:
        return None
    rev = {str(v).strip().lower(): k for k, v in (model.names or {}).items()}
    ids = [rev[n.strip().lower()] for n in class_names
           if n.strip().lower() in rev]
    return ids or None


def detect_flame_prop(frame, min_area_frac: float = 0.01):
    """Classical detector for a PRINTED/animated flame (the real-fire YOLO
    net can't see a flat cartoon flame — it learned actual flames). The
    printed prop has an unmistakable signature: one large blob holding BOTH
    saturated red/orange AND saturated yellow, taller than it is wide. Tuned
    to fire on the prop while staying silent on skin, wood, and lamps.
    Returns the same normalized detection dicts as the YOLO path."""
    import cv2
    import numpy as np
    h, w = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    s, v, hue = hsv[:, :, 1], hsv[:, :, 2], hsv[:, :, 0]
    red = ((s > 110) & (v > 90) & ((hue <= 15) | (hue >= 165))) | \
          ((s > 110) & (v > 90) & (hue > 8) & (hue <= 22))
    yellow = (s > 110) & (v > 110) & (hue >= 20) & (hue <= 38)
    red = red.astype(np.uint8)
    yellow = yellow.astype(np.uint8)
    combined = ((red | yellow) * 255).astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, k, iterations=2)
    cnts, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL,
                               cv2.CHAIN_APPROX_SIMPLE)
    out = []
    img_area = h * w
    for c in cnts:
        x, y, bw, bh = cv2.boundingRect(c)
        area = bw * bh
        if area < min_area_frac * img_area:
            continue
        rfrac = red[y:y + bh, x:x + bw].sum() / area
        yfrac = yellow[y:y + bh, x:x + bw].sum() / area
        if rfrac < 0.06 or yfrac < 0.02:      # needs BOTH flame colours
            continue
        if bh < 0.9 * bw:                     # flame is tall, not wide
            continue
        conf = max(0.0, min(0.97, 0.55 + 0.8 * (rfrac + yfrac - 0.25)
                            + 0.5 * min(rfrac, 0.4)))
        out.append({'label': 'fire', 'conf': float(conf),
                    'cx': (x + bw / 2) / w, 'cy': (y + bh / 2) / h,
                    'w': bw / w, 'h': bh / h})
    return out


def _iou(a, b):
    """IoU of two normalized cx/cy/w/h detection dicts."""
    ax1, ay1 = a['cx'] - a['w'] / 2, a['cy'] - a['h'] / 2
    ax2, ay2 = a['cx'] + a['w'] / 2, a['cy'] + a['h'] / 2
    bx1, by1 = b['cx'] - b['w'] / 2, b['cy'] - b['h'] / 2
    bx2, by2 = b['cx'] + b['w'] / 2, b['cy'] + b['h'] / 2
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = a['w'] * a['h'] + b['w'] * b['h'] - inter
    return inter / union if union > 0 else 0.0


def _extract_dets(results):
    """Ultralytics result → list of normalized detection dicts. The console
    uses label/conf for alerts and cx/h to PROJECT onto the shared map."""
    dets = []
    boxes = getattr(results[0], 'boxes', None)
    names = getattr(results[0], 'names', None) or {}
    if boxes is not None and len(boxes) > 0:
        for (bx, by, bw, bh), cls_id, cf in zip(
                boxes.xywhn.tolist(), boxes.cls.tolist(), boxes.conf.tolist()):
            dets.append({
                'label': str(names.get(int(cls_id), int(cls_id))),
                'conf': float(cf),
                'cx': float(bx), 'cy': float(by),
                'w': float(bw), 'h': float(bh),
            })
    return dets


def _child_main(in_q: mp.Queue, out_q: mp.Queue, model_path: str,
                class_names=None, conf: float = 0.25,
                imgsz: int = 640, augment: bool = False,
                fire_model_path=None, fire_prop: bool = True) -> None:
    """Runs in the child process. Heavy imports happen here, not in the UI.

    DUAL-MODEL: the primary model (a clean COCO net) handles person/dog/cat;
    an optional secondary model (fire.pt) handles ONLY 'fire'. fire.pt is a
    fire-fine-tuned net whose COCO classes are wrecked — so we never trust it
    for people/animals, only for flames. Both run per frame and their
    detections are merged; the secondary's boxes are drawn over the primary's
    annotated frame."""
    try:
        from inference.concat_head import install as install_concat_head
    except ImportError:                       # alternate import roots
        try:
            from dashboard_qt.inference.concat_head import install as install_concat_head
        except ImportError:
            from concat_head import install as install_concat_head

    def load_and_warm(path):
        """Load + one throwaway inference: torch's FIRST forward pass can
        take seconds (kernel selection/tracing) — warming here keeps the
        parent's hang watchdog honest once we report 'ready'."""
        m = YOLO(path)
        m(np.zeros((480, 640, 3), dtype=np.uint8), verbose=False)
        return m

    try:
        import cv2
        import numpy as np
        install_concat_head()
        from ultralytics import YOLO
        model = load_and_warm(model_path)
        # The primary keeps only the non-fire wanted classes it actually has.
        primary_names = [n for n in (class_names or [])
                         if str(n).strip().lower() not in _FIRE_NAMES]
        class_ids = _resolve_class_ids(model, primary_names or class_names)
        # Secondary fire model (best-effort — absent/failed = fire disabled).
        fire_model = None
        fire_ids = None
        wants_fire = any(str(n).strip().lower() in _FIRE_NAMES
                         for n in (class_names or []))
        if fire_model_path and wants_fire:
            try:
                fire_model = load_and_warm(fire_model_path)
                fire_ids = _resolve_class_ids(fire_model, list(_FIRE_NAMES))
            except Exception:
                fire_model = None
        out_q.put(('ready', model_path))
    except Exception as exc:
        out_q.put(('unavailable', f'{type(exc).__name__}: {exc}'))
        return

    while True:
        try:
            item = in_q.get(timeout=1.0)
        except queue_mod.Empty:
            continue
        # Latest-wins: drain everything queued right now and keep only the
        # NEWEST frame. Frames that piled up while the previous (dual-model)
        # inference ran are already stale — annotating them just piles
        # inference latency onto the live view (the "camera ms" climbs).
        # This bounds the displayed frame to at most one inference old.
        # Control messages (stop/model) are always honored in order.
        frame_item = None
        while item is not None:
            kind = item[0]
            if kind == 'stop':
                return
            if kind == 'model':
                try:
                    model = load_and_warm(item[1])
                    primary_names = [n for n in (class_names or [])
                                     if str(n).strip().lower() not in _FIRE_NAMES]
                    class_ids = _resolve_class_ids(
                        model, primary_names or class_names)
                    out_q.put(('ready', item[1]))
                except Exception as exc:
                    out_q.put(('error', f'model load failed: {exc}'))
            elif kind == 'frame':
                frame_item = item            # keep newest, discard older
            try:
                item = in_q.get_nowait()
            except queue_mod.Empty:
                item = None
        if frame_item is None:
            continue
        _, frame_id, jpeg = frame_item
        try:
            arr = np.frombuffer(jpeg, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                continue
            results = model(frame, classes=class_ids, conf=conf,
                            imgsz=imgsz, augment=augment, verbose=False)
            detections = _extract_dets(results)

            # Secondary pass: fire only.
            fdets = []
            if fire_model is not None:
                fres = fire_model(frame, classes=fire_ids, conf=conf,
                                  imgsz=imgsz, augment=augment, verbose=False)
                fdets = _extract_dets(fres)
            # Tertiary pass: printed/animated flame prop the real-fire net
            # can't see. Add only props that don't overlap a real-fire hit.
            if fire_prop and wants_fire:
                for pd in detect_flame_prop(frame):
                    if all(_iou(pd, fd) < 0.3 for fd in fdets):
                        fdets.append(pd)
            if fdets:
                detections.extend(fdets)

            # Decoupled rendering: the UI shows the RAW frame the instant it
            # arrives and overlays these boxes as vectors. So the live video
            # is bounded by network latency, not inference — and we skip
            # plot() + JPEG re-encode + shipping a second JPEG over the IPC,
            # all of which was pure added latency on the display path. Only
            # the (small) detection list crosses the process boundary now.
            out_q.put(('annotated', frame_id, b'', detections))
        except Exception as exc:
            out_q.put(('error', f'inference: {exc}'))


class YoloManager(QObject):
    annotatedFrame = Signal(int, bytes, object)  # frame_id, jpeg, [(label, conf)]
    availabilityChanged = Signal(bool, str)      # ai_on, reason
    modelChanged = Signal(str)

    def __init__(self, model_path: str, parent=None, *,
                 classes=None, conf: float = 0.25,
                 imgsz: int = 640, augment: bool = False,
                 fire_model_path=None, fire_prop: bool = True):
        super().__init__(parent)
        self.model_path = model_path
        self.classes = classes            # wanted class names, or None = all
        self.conf = conf                  # worker-side confidence floor
        self.imgsz = imgsz                # inference working resolution
        self.augment = augment            # test-time augmentation (TTA)
        self.fire_model_path = fire_model_path   # secondary fire-only net
        self.fire_prop = fire_prop        # classical printed-flame detector
        self._proc: mp.Process | None = None
        self._in_q: mp.Queue | None = None
        self._out_q: mp.Queue | None = None
        self._reader: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_sent = 0.0
        self._last_result = 0.0
        self._inflight = 0
        self._available = False
        self._respawn_times: list[float] = []

    # ── lifecycle ─────────────────────────────────────────────────────────
    def start(self) -> None:
        self._stop.clear()
        self._spawn()
        self._reader = threading.Thread(target=self._read_loop, daemon=True,
                                        name='yolo-reader')
        self._reader.start()

    def stop(self) -> None:
        self._stop.set()
        self._terminate_child()
        if self._reader:
            self._reader.join(timeout=2.0)

    def _spawn(self) -> None:
        ctx = mp.get_context('spawn')
        # Depth 4 so a fresh frame is usually waiting when an inference ends;
        # the child drains to the newest and discards the rest (latest-wins),
        # so a deeper queue lowers latency here rather than adding to it.
        self._in_q = ctx.Queue(maxsize=4)
        self._out_q = ctx.Queue(maxsize=4)
        self._proc = ctx.Process(
            target=_child_main,
            args=(self._in_q, self._out_q, self.model_path,
                  self.classes, self.conf, self.imgsz, self.augment,
                  self.fire_model_path, self.fire_prop),
            daemon=True, name='gp-yolo')
        self._proc.start()
        self._inflight = 0
        self._last_result = time.monotonic()

    def _terminate_child(self) -> None:
        if self._proc is not None and self._proc.is_alive():
            try:
                self._in_q.put_nowait(('stop',))
            except Exception:
                pass
            self._proc.join(timeout=1.0)
            if self._proc.is_alive():
                self._proc.terminate()
        self._proc = None

    def _respawn(self, reason: str) -> None:
        now = time.monotonic()
        self._respawn_times = [t for t in self._respawn_times if now - t < 60]
        self._set_available(False, reason)
        self._terminate_child()
        if len(self._respawn_times) >= MAX_RESPAWNS_PER_MIN:
            self._set_available(False, f'{reason} (giving up — raw video)')
            return
        self._respawn_times.append(now)
        self._spawn()

    # ── frames in ─────────────────────────────────────────────────────────
    def submit_frame(self, frame_id: int, jpeg: bytes) -> None:
        """Latest-wins: drop the queued frame if the worker is behind."""
        if self._proc is None or not self._proc.is_alive():
            return
        now = time.monotonic()
        # hang watchdog: frames flowing but no result for HANG_TIMEOUT_S
        if (self._inflight > 0 and self._available
                and now - self._last_result > HANG_TIMEOUT_S):
            self._respawn('inference hung')
            return
        try:
            self._in_q.put_nowait(('frame', frame_id, jpeg))
            self._inflight += 1
            self._last_sent = now
        except queue_mod.Full:
            pass

    def set_model(self, path: str) -> None:
        self.model_path = path
        if self._proc is not None and self._proc.is_alive():
            try:
                self._in_q.put_nowait(('model', path))
            except queue_mod.Full:
                pass

    @property
    def available(self) -> bool:
        return self._available

    # ── results out (reader thread) ───────────────────────────────────────
    def _read_loop(self) -> None:
        while not self._stop.is_set():
            if self._proc is not None and not self._proc.is_alive() and self._available:
                self._respawn('inference process died')
            try:
                item = self._out_q.get(timeout=0.5)
            except (queue_mod.Empty, OSError):
                continue
            kind = item[0]
            if kind == 'annotated':
                self._inflight = max(0, self._inflight - 1)
                self._last_result = time.monotonic()
                detections = item[3] if len(item) > 3 else []
                self.annotatedFrame.emit(item[1], item[2], detections)
            elif kind == 'ready':
                self._respawn_times.clear()       # healthy again → fresh budget
                self._inflight = 0
                self._last_result = time.monotonic()
                self._set_available(True, '')
                self.modelChanged.emit(item[1])
            elif kind == 'unavailable':
                self._set_available(False, item[1])
                self._terminate_child()
            elif kind == 'error':
                self._last_result = time.monotonic()
                self._inflight = max(0, self._inflight - 1)

    def _set_available(self, on: bool, reason: str) -> None:
        if on != self._available:
            self._available = on
            self.availabilityChanged.emit(on, reason)
