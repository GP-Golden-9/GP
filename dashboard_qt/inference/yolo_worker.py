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


def _child_main(in_q: mp.Queue, out_q: mp.Queue, model_path: str) -> None:
    """Runs in the child process. Heavy imports happen here, not in the UI."""
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
        out_q.put(('ready', model_path))
    except Exception as exc:
        out_q.put(('unavailable', f'{type(exc).__name__}: {exc}'))
        return

    while True:
        try:
            item = in_q.get(timeout=1.0)
        except queue_mod.Empty:
            continue
        kind = item[0]
        if kind == 'stop':
            return
        if kind == 'model':
            try:
                model = load_and_warm(item[1])
                out_q.put(('ready', item[1]))
            except Exception as exc:
                out_q.put(('error', f'model load failed: {exc}'))
            continue
        if kind != 'frame':
            continue
        _, frame_id, jpeg = item
        try:
            arr = np.frombuffer(jpeg, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                continue
            results = model(frame, verbose=False)
            annotated = results[0].plot()

            # detection dicts with normalized bbox geometry — the console
            # uses label/conf for alerts and cx/h to PROJECT the detection
            # onto the shared map (bearing from cx + FOV, range from h)
            detections = []
            boxes = getattr(results[0], 'boxes', None)
            names = getattr(results[0], 'names', None) or {}
            if boxes is not None and len(boxes) > 0:
                xywhn = boxes.xywhn.tolist()
                for (bx, by, bw, bh), cls_id, conf in zip(
                        xywhn, boxes.cls.tolist(), boxes.conf.tolist()):
                    detections.append({
                        'label': str(names.get(int(cls_id), int(cls_id))),
                        'conf': float(conf),
                        'cx': float(bx), 'cy': float(by),
                        'w': float(bw), 'h': float(bh),
                    })

            ok, buf = cv2.imencode('.jpg', annotated,
                                   [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if ok:
                out_q.put(('annotated', frame_id, buf.tobytes(), detections))
        except Exception as exc:
            out_q.put(('error', f'inference: {exc}'))


class YoloManager(QObject):
    annotatedFrame = Signal(int, bytes, object)  # frame_id, jpeg, [(label, conf)]
    availabilityChanged = Signal(bool, str)      # ai_on, reason
    modelChanged = Signal(str)

    def __init__(self, model_path: str, parent=None):
        super().__init__(parent)
        self.model_path = model_path
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
        self._in_q = ctx.Queue(maxsize=2)
        self._out_q = ctx.Queue(maxsize=4)
        self._proc = ctx.Process(target=_child_main,
                                 args=(self._in_q, self._out_q, self.model_path),
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
