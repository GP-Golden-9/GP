"""LIVE Beta hand-off — the REAL robot half of the master/slave scenario.

Sequences the pieces that already work (map-aware planning + the
MissionExecutor's bias streaming + the pump command) into the graduation
scenario's Beta leg, for real, on the robot:

    GOTO FIRE : drive Beta to the fire location (planned, obstacle-dodging)
    PUMP      : 5 s operator-INTERRUPTIBLE pump (firmware also hard-caps 5 s)
    RETURN    : drive Beta back to where it started
    DONE

This is the live counterpart to MasterMission (the pure animation). The
MissionPanel SIM/LIVE toggle picks which one START runs, so the polished
simulation stays as a one-click fallback if hardware misbehaves on stage.

No driving logic lives here — it is injected:
  navigate(target_xy, label) -> bool   plan + start a mission to target;
                                        False if no path / not ready.
  pump(on: bool)                        CMD_PUMP passthrough.
  stop()                                cancel mission + stop the bias stream.
The owner calls on_arrived(reason) from MissionExecutor.missionFinished.
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple

from PySide6.QtCore import QObject, QTimer, Signal

PUMP_SECONDS = 5

Pt = Tuple[float, float]


class LiveHandoff(QObject):
    phaseChanged = Signal(str)
    statusChanged = Signal(dict)
    log = Signal(str)
    actionPending = Signal(bool)        # 5 s pump window open → enable INTERRUPT
    finished = Signal(str)              # 'done' | 'aborted' | reason

    PHASES = ['BETA FIRE', 'PUMP ACTION', 'RETURN', 'DONE']

    def __init__(self, *, navigate: Callable[[Pt, str], bool],
                 pump: Callable[[bool], None],
                 stop: Callable[[], None],
                 arm: Callable[[bool], None], parent=None):
        super().__init__(parent)
        self._navigate = navigate
        self._pump = pump
        self._stop = stop
        self._arm = arm                  # enable/disable Beta's autonomy
        self._phase = 'IDLE'
        self._home: Optional[Pt] = None
        self._fire: Optional[Pt] = None
        self._status = {'beta': 'IDLE', 'pump': 'OFF', 'link': 'OFFLINE'}
        self._cd = 0
        self._cd_timer = QTimer(self)
        self._cd_timer.timeout.connect(self._tick_pump)

    @property
    def active(self) -> bool:
        return self._phase not in ('IDLE', 'DONE')

    # ── lifecycle ─────────────────────────────────────────────────────────
    def start(self, home_xy: Pt, fire_xy: Pt) -> bool:
        """Begin the live hand-off. Returns False (and does nothing) if the
        first navigation leg can't be planned — the caller surfaces why."""
        self._home = tuple(home_xy)
        self._fire = tuple(fire_xy)
        self._set_status(beta='NAVIGATING', pump='OFF', link='ONLINE')
        self.log.emit('=== LIVE HAND-OFF — robot1 (master) → robot2 ===')
        self.log.emit(f'robot1 → robot2: navigate to the fire '
                      f'({fire_xy[0]:+.2f}, {fire_xy[1]:+.2f}) and extinguish')
        self._phase = 'BETA FIRE'
        self.phaseChanged.emit('BETA FIRE')
        if not self._navigate(self._fire, 'fire'):
            self.log.emit('LIVE ABORT — no path to the fire (map/alignment?)')
            self._reset('aborted')
            return False
        return True

    def on_arrived(self, reason: str) -> None:
        """Driven by MissionExecutor.missionFinished while a leg is active."""
        if not self.active:
            return
        if reason != 'arrived':
            self.log.emit(f'LIVE ABORT — Beta did not arrive ({reason})')
            self._stop()
            self._pump(False)
            self._reset('aborted')
            return
        if self._phase == 'BETA FIRE':
            self._arm(False)             # HOLD at the fire — don't wander while pumping
            self.log.emit('robot2 arrived at the fire')
            self.log.emit(f'[ACTION] PUMP armed — {PUMP_SECONDS} s to INTERRUPT, '
                          'else it runs automatically')
            self._phase = 'PUMP ACTION'
            self.phaseChanged.emit('PUMP ACTION')
            self._set_status(beta='PUMP PENDING')
            self._cd = PUMP_SECONDS
            self.actionPending.emit(True)
            self._cd_timer.start(1000)
            self._tick_pump_msg()
        elif self._phase == 'RETURN':
            self.log.emit('robot2 back at start — LIVE HAND-OFF COMPLETE')
            self._set_status(beta='DONE', pump='OFF')
            self._reset('done')

    def interrupt(self) -> None:
        """Operator cancels the pump within the 5 s window."""
        if self._cd_timer.isActive():
            self._cd_timer.stop()
            self.actionPending.emit(False)
            self.log.emit('[ACTION] operator INTERRUPTED — pump cancelled')
            self._set_status(beta='HOLD', pump='OFF')
            self._begin_return()

    def abort(self) -> None:
        if not self.active:
            return
        self._cd_timer.stop()
        self.actionPending.emit(False)
        self._stop()
        self._pump(False)
        self.log.emit('LIVE HAND-OFF ABORTED — operator took control')
        self._reset('aborted')

    # ── pump countdown ────────────────────────────────────────────────────
    def _tick_pump_msg(self) -> None:
        self.log.emit(f'[ACTION] robot2 PUMP in {self._cd}s — INTERRUPT to cancel')
        self._set_status(beta=f'PUMP IN {self._cd}s')

    def _tick_pump(self) -> None:
        self._cd -= 1
        if self._cd > 0:
            self._tick_pump_msg()
            return
        self._cd_timer.stop()
        self.actionPending.emit(False)
        self.log.emit('robot2 PUMP ON — extinguishing (5 s, firmware-capped)')
        self._set_status(beta='PUMPING', pump='ON')
        self._pump(True)
        # firmware auto-offs at 5 s; send an explicit OFF after, then return
        QTimer.singleShot(PUMP_SECONDS * 1000, self._pump_done)

    def _pump_done(self) -> None:
        self._pump(False)
        if self._phase != 'PUMP ACTION':     # aborted/interrupted mid-pump → bail
            return
        self._set_status(beta='HOLD', pump='OFF')
        self._begin_return()

    def _begin_return(self) -> None:
        if self._home is None:
            self._reset('done')
            return
        self.log.emit(f'robot2 returning to start '
                      f'({self._home[0]:+.2f}, {self._home[1]:+.2f})')
        self._phase = 'RETURN'
        self.phaseChanged.emit('RETURN')
        self._set_status(beta='RETURNING')
        if not self._navigate(self._home, 'home'):
            self.log.emit('LIVE — no path home; stopping where it is')
            self._reset('aborted')

    # ── helpers ───────────────────────────────────────────────────────────
    def _set_status(self, **kw) -> None:
        self._status.update(kw)
        self.statusChanged.emit(dict(self._status))

    def _reset(self, why: str) -> None:
        self._arm(False)                     # ensure Beta is disarmed/stopped
        self._phase = 'DONE' if why == 'done' else 'IDLE'
        self.phaseChanged.emit('DONE' if why == 'done' else '')
        self.finished.emit(why)
