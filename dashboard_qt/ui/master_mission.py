"""Master-Slave mission - a PURE DASHBOARD SIMULATION for the presentation.

The full graduation scenario, all orchestrated centrally by the laptop (the
robots do NOT talk to each other - the master->slave commands are mocked in the
logs). NOTHING real happens: no CMD_* is sent, no motor moves, no pump fires.

  robot1 "Alpha" = MASTER + mapper.
  robot2 "Beta"  = navigates, finds objects, detects FIRE, runs the PUMP.
  robot3 "Gamma" = goes to the fire and reads the GAS level.

Flow:
  ALPHA HOME  : robot1 finishes mapping, returns to base
  BETA NAV    : robot1 -> robot2: navigate the map and find objects
  BETA FIRE   : robot2 detects fire -> robot1 -> robot2: go extinguish it
  PUMP ACTION : robot2 at the fire -> 5 s operator-INTERRUPTIBLE pump countdown
  GAMMA GAS   : robot1 -> robot3: go to the fire and read the gas level
  DONE

AUTO advances on a timer; MANUAL steps via next_phase() (operator override).
"""

from __future__ import annotations

import math

from PySide6.QtCore import QObject, QTimer, Signal

SIM_SPEED_MPS = 0.35
MOVE_MIN_S, MOVE_MAX_S = 2.0, 7.0
DWELL_S = 2.0
ACTION_COUNTDOWN_S = 5          # operator interrupt window before the pump fires
SIM_GAS_PPM = 340               # mocked gas reading


def _move_secs(x0, y0, x1, y1) -> float:
    d = math.hypot(x1 - x0, y1 - y0)
    return max(MOVE_MIN_S, min(MOVE_MAX_S, d / SIM_SPEED_MPS))


class MasterMission(QObject):
    log = Signal(str)
    phaseChanged = Signal(str)
    statusChanged = Signal(dict)
    animate = Signal(str, float, float, float, float, float)  # rid,x0,y0,x1,y1,s
    actionPending = Signal(bool)            # the 5 s pump window is open
    finished = Signal()

    PHASES = ['ALPHA HOME', 'BETA NAV', 'BETA FIRE', 'PUMP ACTION',
              'GAMMA GAS', 'DONE']

    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps: list[dict] = []
        self._idx = -1
        self._auto = True
        self._status = {'alpha': 'IDLE', 'beta': 'IDLE', 'gamma': 'IDLE',
                        'link': 'OFFLINE', 'pump': 'OFF', 'gas': '-'}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)
        self._cd_timer = QTimer(self)       # 1 Hz pump-action countdown
        self._cd_timer.timeout.connect(self._tick_countdown)
        self._cd = 0
        self._alpha = self._beta = self._gamma = (0.0, 0.0)

    @property
    def active(self) -> bool:
        return 0 <= self._idx < len(self._steps)

    def set_auto(self, auto: bool) -> None:
        self._auto = bool(auto)
        if (self._auto and self.active and not self._cd_timer.isActive()
                and not self._timer.isActive()):
            self._timer.start(int(self._steps[self._idx]['dur'] * 1000))

    def configure(self, alpha_pos, alpha_home, beta_pos, gamma_pos,
                  object_xy, fire_xy):
        self._alpha = tuple(alpha_pos)
        self._beta = tuple(beta_pos)
        self._gamma = tuple(gamma_pos)
        self._alpha_home = tuple(alpha_home)
        self._object = tuple(object_xy)
        self._fire = tuple(fire_xy)

    # ── lifecycle ─────────────────────────────────────────────────────────
    def start(self) -> None:
        self._build_steps()
        self._idx = -1
        self._set_status(alpha='MAPPING', beta='IDLE', gamma='IDLE',
                         link='OFFLINE', pump='OFF', gas='-')
        self.log.emit('=== MISSION START - robot1 = MASTER (centralized) ===')
        self._advance()

    def next_phase(self) -> None:
        """Operator override: advance one step manually (MANUAL mode). Does not
        skip the live pump countdown - use interrupt for that."""
        if self.active and not self._cd_timer.isActive():
            self._advance()

    def interrupt_action(self) -> None:
        """Operator interrupts the pending pump action within the 5 s window."""
        if self._cd_timer.isActive():
            self._cd_timer.stop()
            self.actionPending.emit(False)
            self.log.emit('[ACTION] operator INTERRUPTED - pump cancelled')
            self._set_status(beta='HOLD', pump='OFF')
            self._after_action()

    def abort(self) -> None:
        if not self.active:
            return
        self._timer.stop()
        self._cd_timer.stop()
        self.actionPending.emit(False)
        self._idx = len(self._steps)
        self.log.emit('MISSION ABORTED - operator took manual control')
        self._set_status(alpha='IDLE', beta='IDLE', gamma='IDLE',
                         link='OFFLINE', pump='OFF')
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
        if step.get('countdown'):
            self._start_countdown()
        elif self._auto:
            self._timer.start(int(step['dur'] * 1000))

    # ── the 5 s interruptible pump action ─────────────────────────────────
    def _start_countdown(self) -> None:
        self._cd = ACTION_COUNTDOWN_S
        self.actionPending.emit(True)
        self._cd_timer.start(1000)
        self._tick_countdown()

    def _tick_countdown(self) -> None:
        if self._cd <= 0:
            self._cd_timer.stop()
            self.actionPending.emit(False)
            self.log.emit('robot2 PUMP ACTIVE - extinguishing the fire')
            self._set_status(beta='PUMPING', pump='ON')
            self._after_action()
            return
        self.log.emit(f'[ACTION] robot2 PUMP in {self._cd}s - '
                      'press INTERRUPT to cancel')
        self._set_status(beta=f'PUMP IN {self._cd}s')
        self._cd -= 1

    def _after_action(self) -> None:
        """Whether the pump fired or was interrupted, move on (AUTO) or wait
        for the operator (MANUAL)."""
        if self._auto:
            self._timer.start(2200)
        # MANUAL: operator clicks NEXT PHASE to send the Gamma order.

    # ── the scenario ──────────────────────────────────────────────────────
    def _build_steps(self) -> None:
        a0, ahome = self._alpha, self._alpha_home
        b0, g0 = self._beta, self._gamma
        obj, fire = self._object, self._fire

        def alpha_return():
            self.log.emit('robot1 finished mapping the area')
            self.log.emit('robot1 returning to base')
            self._set_status(alpha='RETURNING')
            self.animate.emit('robot1', a0[0], a0[1], ahome[0], ahome[1],
                              _move_secs(*a0, *ahome))

        def cmd_beta_nav():
            self.log.emit('robot1 reached base - taking MASTER role')
            self.log.emit('robot1 sent an action to robot2 to navigate through '
                          'the map and find objects')
            self.log.emit('robot2 ACK - navigating and scanning for objects')
            self._set_status(alpha='AT BASE', beta='NAVIGATING', link='ONLINE')
            self.animate.emit('robot2', b0[0], b0[1], obj[0], obj[1],
                              _move_secs(*b0, *obj))

        def beta_detect_fire():
            self.log.emit(f'robot2 DETECTED FIRE @ ({fire[0]:+.1f},{fire[1]:+.1f})')
            self.log.emit('robot1 sent an action to robot2 to navigate to the '
                          'fire and extinguish it')
            self.log.emit('robot2 ACK - navigating to the fire')
            self._set_status(beta='NAVIGATING')
            self.animate.emit('robot2', obj[0], obj[1], fire[0], fire[1],
                              _move_secs(*obj, *fire))

        def beta_at_fire():
            self.log.emit('robot2 arrived at the fire')
            self.log.emit('[ACTION] PUMP action armed - 5 s for operator to '
                          'INTERRUPT, else it runs automatically')
            self._set_status(beta='PUMP PENDING')

        def cmd_gamma_gas():
            self.log.emit('robot1 sent action to robot3 to go to the fire place '
                          'to get the gas level there')
            self.log.emit('robot3 ACK - navigating to the fire place')
            self._set_status(gamma='NAVIGATING')
            self.animate.emit('robot3', g0[0], g0[1], fire[0], fire[1],
                              _move_secs(*g0, *fire))

        def gamma_read_gas():
            self.log.emit('robot3 arrived at the fire place')
            self.log.emit(f'robot3 reading gas level... GAS = {SIM_GAS_PPM} ppm '
                          '(ELEVATED)')
            self._set_status(gamma='READING', gas=f'{SIM_GAS_PPM} ppm')

        def mission_done():
            self.log.emit('robot1 === MISSION COMPLETE ===')
            self._set_status(alpha='DONE', beta='DONE', gamma='DONE', pump='OFF')

        self._steps = [
            {'phase': 'ALPHA HOME', 'dur': _move_secs(*a0, *ahome),
             'enter': alpha_return},
            {'phase': 'BETA NAV', 'dur': _move_secs(*b0, *obj),
             'enter': cmd_beta_nav},
            {'phase': 'BETA FIRE', 'dur': _move_secs(*obj, *fire),
             'enter': beta_detect_fire},
            {'phase': 'PUMP ACTION', 'dur': 0.0, 'countdown': True,
             'enter': beta_at_fire},
            {'phase': 'GAMMA GAS', 'dur': _move_secs(*g0, *fire),
             'enter': cmd_gamma_gas},
            {'phase': 'GAMMA GAS', 'dur': DWELL_S + 1.0, 'enter': gamma_read_gas},
            {'phase': 'DONE', 'dur': 0.0, 'enter': mission_done},
        ]
