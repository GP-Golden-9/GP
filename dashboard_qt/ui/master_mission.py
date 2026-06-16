"""Master–Slave mission — a PURE DASHBOARD SIMULATION for the presentation.

Makes it look like Alpha (master) autonomously commands Beta (slave) to scan an
object and then go to the fire and run the pump, after Alpha returns to base.
NOTHING real happens on the robots: no CMD_* is sent, no motor moves, no pump
fires. This object only emits mocked master→slave log lines, status updates, and
"glide this icon from A to B" animation requests that the main window plays on
the map. Everything stays centralized in the laptop.

Sequence (auto-advance, or step manually via next_phase() = the operator
override):
  ALPHA HOME      : Alpha finishes mapping → returns to base
  BETA SCAN       : Alpha commands Beta → navigate to object → scan
  BETA FIRE+PUMP  : Alpha commands Beta → navigate to fire → PUMP ON
  DONE
"""

from __future__ import annotations

import math

from PySide6.QtCore import QObject, QTimer, Signal

SIM_SPEED_MPS = 0.35           # pretend travel speed for animation timing
MOVE_MIN_S, MOVE_MAX_S = 2.0, 7.0
DWELL_S = 2.0                  # pause on an action step (scan, pump...)


def _move_secs(x0, y0, x1, y1) -> float:
    d = math.hypot(x1 - x0, y1 - y0)
    return max(MOVE_MIN_S, min(MOVE_MAX_S, d / SIM_SPEED_MPS))


class MasterMission(QObject):
    log = Signal(str)                       # a mocked master/slave log line
    phaseChanged = Signal(str)              # high-level phase label (stepper)
    statusChanged = Signal(dict)            # {alpha,beta,link,pump}
    animate = Signal(str, float, float, float, float, float)  # rid,x0,y0,x1,y1,s
    finished = Signal()

    PHASES = ['ALPHA HOME', 'BETA SCAN', 'BETA FIRE+PUMP', 'DONE']

    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps: list[dict] = []
        self._idx = -1
        self._auto = True
        self._status = {'alpha': 'IDLE', 'beta': 'IDLE',
                        'link': 'OFFLINE', 'pump': 'OFF'}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)
        # live positions used to chain animations
        self._alpha = (0.0, 0.0)
        self._beta = (0.0, 0.0)

    # ── config ────────────────────────────────────────────────────────────
    @property
    def active(self) -> bool:
        return self._idx >= 0 and self._idx < len(self._steps)

    def set_auto(self, auto: bool) -> None:
        self._auto = bool(auto)
        # If we just switched to AUTO mid-mission, resume the timer.
        if self._auto and self.active and not self._timer.isActive():
            self._timer.start(int(self._steps[self._idx]['dur'] * 1000))

    def configure(self, alpha_pos, alpha_home, beta_pos, object_xy, fire_xy):
        """Targets come from the main window (markers / clicks)."""
        self._alpha = tuple(alpha_pos)
        self._beta = tuple(beta_pos)
        self._alpha_home = tuple(alpha_home)
        self._object = tuple(object_xy)
        self._fire = tuple(fire_xy)

    # ── lifecycle ─────────────────────────────────────────────────────────
    def start(self) -> None:
        self._build_steps()
        self._idx = -1
        self._set_status(alpha='MAPPING', beta='IDLE', link='OFFLINE', pump='OFF')
        self.log.emit('=== MISSION START - Alpha = MASTER, Beta = SLAVE ===')
        self._advance()

    def next_phase(self) -> None:
        """Operator override: advance one step manually (used in MANUAL mode)."""
        if self.active:
            self._advance()

    def abort(self) -> None:
        if not self.active:
            return
        self._timer.stop()
        self._idx = len(self._steps)
        self.log.emit('MISSION ABORTED - operator took manual control')
        self._set_status(alpha='IDLE', beta='IDLE', link='OFFLINE', pump='OFF')
        self.phaseChanged.emit('')
        self.finished.emit()

    # ── internals ─────────────────────────────────────────────────────────
    def _set_status(self, **kw) -> None:
        self._status.update(kw)
        self.statusChanged.emit(dict(self._status))

    def _advance(self) -> None:
        self._timer.stop()
        self._idx += 1
        if self._idx >= len(self._steps):
            self.finished.emit()
            return
        step = self._steps[self._idx]
        self.phaseChanged.emit(step['phase'])
        step['enter']()
        if self._auto:
            self._timer.start(int(step['dur'] * 1000))

    def _build_steps(self) -> None:
        a0, ahome = self._alpha, self._alpha_home
        b0, obj, fire = self._beta, self._object, self._fire

        def alpha_return():
            self.log.emit('[MASTER Alpha] mapping complete - returning to base')
            self._set_status(alpha='RETURNING')
            self.animate.emit('robot1', a0[0], a0[1], ahome[0], ahome[1],
                              _move_secs(*a0, *ahome))

        def alpha_home_cmd_scan():
            self.log.emit('[MASTER Alpha] reached base - taking MASTER role')
            self.log.emit(f'[MASTER Alpha -> SLAVE Beta] CMD: SCAN object '
                          f'@ ({obj[0]:+.1f}, {obj[1]:+.1f})')
            self.log.emit('[SLAVE Beta] ACK - navigating to object')
            self._set_status(alpha='AT BASE', beta='NAVIGATING', link='ONLINE')
            self.animate.emit('robot2', b0[0], b0[1], obj[0], obj[1],
                              _move_secs(*b0, *obj))

        def beta_scanning():
            self.log.emit('[SLAVE Beta] arrived - scanning object...')
            self.log.emit('[SLAVE Beta] scan complete - holding for orders')
            self._set_status(beta='SCANNED')

        def beta_goto_fire():
            self.log.emit(f'[MASTER Alpha -> SLAVE Beta] CMD: GOTO fire '
                          f'@ ({fire[0]:+.1f}, {fire[1]:+.1f}) + PUMP ON')
            self.log.emit('[SLAVE Beta] ACK - navigating to fire')
            self._set_status(beta='NAVIGATING')
            self.animate.emit('robot2', obj[0], obj[1], fire[0], fire[1],
                              _move_secs(*obj, *fire))

        def beta_pump():
            self.log.emit('[SLAVE Beta] arrived at fire')
            self.log.emit('[SLAVE Beta] PUMP ACTIVE - extinguishing fire')
            self._set_status(beta='PUMPING', pump='ON')

        def mission_done():
            self.log.emit('[SLAVE Beta] fire suppressed - PUMP OFF')
            self.log.emit('[MASTER Alpha] === MISSION COMPLETE ===')
            self._set_status(alpha='DONE', beta='DONE', pump='OFF')

        self._steps = [
            {'phase': 'ALPHA HOME', 'dur': _move_secs(*a0, *ahome),
             'enter': alpha_return},
            {'phase': 'BETA SCAN', 'dur': _move_secs(*b0, *obj),
             'enter': alpha_home_cmd_scan},
            {'phase': 'BETA SCAN', 'dur': DWELL_S, 'enter': beta_scanning},
            {'phase': 'BETA FIRE+PUMP', 'dur': _move_secs(*obj, *fire),
             'enter': beta_goto_fire},
            {'phase': 'BETA FIRE+PUMP', 'dur': DWELL_S + 1.0, 'enter': beta_pump},
            {'phase': 'DONE', 'dur': 0.0, 'enter': mission_done},
        ]
