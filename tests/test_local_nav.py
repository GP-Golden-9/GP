"""Pure-logic tests for Beta's local-nav fusion math (no ROS, no hardware)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'navigation'))

from local_nav_math import goal_fusion, prox        # noqa: E402

BANDS = dict(stop=0.25, slow=0.60)
FUSE = dict(**BANDS, max_lin=0.15, turn=0.40, k_rep=0.40, deadband=0.10)


# ── prox ──────────────────────────────────────────────────────────────────
def test_prox_clear_is_zero():
    assert prox(0.60, **BANDS) == 0.0
    assert prox(1.50, **BANDS) == 0.0


def test_prox_at_stop_is_one():
    assert prox(0.25, **BANDS) == 1.0
    assert prox(0.10, **BANDS) == 1.0          # clamped


def test_prox_midpoint_is_half():
    assert abs(prox(0.425, **BANDS) - 0.5) < 1e-9


def test_prox_collapsed_bands_safe():
    assert prox(0.3, stop=0.6, slow=0.6) == 0.0    # no div-by-zero


# ── goal_fusion: repulsion steers AWAY from the nearer side ────────────────
def test_obstacle_on_left_steers_right():
    _, wz, _ = goal_fusion(0.15, 0.0, left=0.30, right=1.50, **FUSE)
    assert wz < 0.0                            # +wz = left, so right = negative


def test_obstacle_on_right_steers_left():
    _, wz, _ = goal_fusion(0.15, 0.0, left=1.50, right=0.30, **FUSE)
    assert wz > 0.0


def test_symmetric_clear_drives_straight_at_bias():
    vx, wz, blocked = goal_fusion(0.15, 0.0, 1.5, 1.5, **FUSE)
    assert abs(vx - 0.15) < 1e-9 and wz == 0.0 and not blocked


def test_symmetric_obstacle_no_steer_but_slows():
    # equal closeness → no net steer, but forward speed damped
    vx, wz, _ = goal_fusion(0.15, 0.0, 0.45, 0.45, **FUSE)
    assert wz == 0.0 and 0.0 < vx < 0.15


def test_dead_ahead_blocks_forward():
    vx, _, blocked = goal_fusion(0.15, 0.0, 0.25, 0.25, **FUSE)
    assert vx == 0.0 and blocked


def test_one_side_open_keeps_moving():
    # Doorway / wall-on-one-side: a near wall on the RIGHT (0.27 m) with the
    # LEFT open must NOT freeze forward motion — it should keep advancing and
    # steer left. Gating forward on the nearer wall (the old bug) pinned Beta
    # in place at every doorway.
    vx, wz, blocked = goal_fusion(0.15, 0.0, left=1.50, right=0.27, **FUSE)
    assert vx > 0.10 and not blocked        # near-full forward, not frozen
    assert wz > 0.0                         # steers left, away from the wall


def test_deadband_ignores_tiny_imbalance():
    # closeness diff below the deadband → no steer despite a small asymmetry
    _, wz, _ = goal_fusion(0.15, 0.0, left=0.50, right=0.52, **FUSE)
    assert wz == 0.0


def test_bias_turn_preserved_when_clear():
    # operator/heading bias turn passes through untouched in the clear
    _, wz, _ = goal_fusion(0.10, 0.30, 1.5, 1.5, **FUSE)
    assert abs(wz - 0.30) < 1e-9


def test_outputs_are_clamped():
    vx, wz, _ = goal_fusion(99.0, 99.0, 1.5, 1.5, **FUSE)
    assert vx == 0.15 and wz == 0.40
