"""Pure (ROS-free) math for Beta's local navigation fuser.

Kept separate from robot2_local_nav.py so it imports with no rclpy and can be
unit-tested off-robot AND reused by the simulator. The stateful recovery
latches (reverse/pivot locks) live in the node; this is just the per-tick
clear-band fusion of goal-attraction with ultrasonic repulsion.
"""

from __future__ import annotations


def prox(d: float, stop: float, slow: float) -> float:
    """Per-sensor closeness: 0.0 clear (d >= slow) … 1.0 at the stop band."""
    if slow <= stop:
        return 0.0
    return max(0.0, min(1.0, (slow - d) / (slow - stop)))


def goal_fusion(bias_vx: float, bias_wz: float, left: float, right: float, *,
                stop: float, slow: float, max_lin: float, turn: float,
                k_rep: float, deadband: float) -> tuple[float, float, bool]:
    """Fuse the laptop's attraction bias with ultrasonic repulsion.

    Returns ``(vx, wz, blocked)`` clamped to the speed limits. ``blocked`` is
    True when an obstacle inside the stop band has zeroed forward motion (the
    robot may still pivot to steer clear). This is the GOAL-mode "clear band"
    only — the node applies hard reverse/pivot overrides before calling this.
    """
    pl, pr = prox(left, stop, slow), prox(right, stop, slow)
    # ROS convention: +wz = CCW = turn LEFT. Steer AWAY from the nearer side:
    # obstacle on the LEFT (pl > pr) → negative wz (turn right). So the drive
    # term is (right-closeness − left-closeness).
    diff = pr - pl
    wz_rep = k_rep * diff if abs(diff) >= deadband else 0.0
    # Forward motion is gated by the MORE-OPEN side (min closeness), not the
    # nearer wall. A wall on ONE side (a doorway, or driving alongside a wall)
    # must NOT freeze the robot — it should keep moving and let the repulsion
    # term steer it clear. Gating on max() instead pinned Beta in a potential-
    # field local minimum at every doorway (vx→0 while one post sat ~0.27 m
    # away) so it never threaded the gap. Forward stops only when BOTH sides
    # are blocked (a genuine head-on wall / dead end).
    open_side = min(pl, pr)
    fwd_scale = max(0.0, 1.0 - open_side)
    vx = max(0.0, min(max_lin, bias_vx * fwd_scale))
    wz = max(-turn, min(turn, bias_wz + wz_rep))
    return vx, wz, (fwd_scale == 0.0)
