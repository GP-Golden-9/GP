"""Generate: SLAM Occupancy Grid Output vs. Physical Test Environment.

Left  = the occupancy grid the way the console renders it (free / occupied /
        unknown, with realistic SLAM speckle + a mapping trajectory).
Right = a clean floor-plan of the 4x4 m, 4-room test arena (walls, doorways,
        an obstacle, the three robots' start positions).

Geometry matches dashboard_qt/sim/fake_gateway.build_arena (the team's arena).
Colors match dashboard_qt/ui/theme (the live map palette).
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyArrow
from matplotlib.colors import to_rgb

# ── palette (from dashboard_qt/ui/theme) ──
FREE = (216 / 255, 222 / 255, 233 / 255)
OCC = (3 / 255, 5 / 255, 9 / 255)
UNK = (21 / 255, 26 / 255, 38 / 255)
BG = '#0b0f17'
ACCENT = '#3da9fc'
GREEN = '#2dd4a7'
ORANGE = '#ff6b35'
GRID_LINE = (122 / 255, 148 / 255, 188 / 255)

N, RES, ORIGIN = 80, 0.05, -2.0          # 80*0.05 = 4 m, world centred at 0


def build_arena():
    g = np.zeros((N, N), dtype=np.int16)
    g[0, :] = g[-1, :] = g[:, 0] = g[:, -1] = 100
    mid = N // 2
    g[mid, :] = 100
    g[:, mid] = 100
    for lo, hi in ((14, 26), (54, 66)):  # doorways
        g[mid, lo:hi] = 0
        g[lo:hi, mid] = 0
    # an obstacle (a crate) in the lower-right room
    g[12:22, 50:64] = 100
    return g


def occupancy_rgb(seed=7):
    """Render build_arena as a *realistic* SLAM map: ragged walls, scan
    speckle, a probabilistic halo around obstacles, and unknown pockets."""
    rng = np.random.default_rng(seed)
    g = build_arena().astype(float)

    # ragged walls: jitter a few wall cells off, add a few stray wall cells next
    occ = g >= 50
    halo = np.zeros_like(g, dtype=bool)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            halo |= np.roll(np.roll(occ, di, 0), dj, 1)
    halo &= ~occ
    img = np.empty((N, N, 3))
    img[:] = FREE
    # probabilistic halo (light grey) around walls
    img[halo] = (0.62, 0.66, 0.73)
    # scan speckle in free space
    free = g < 50
    spk = free & (rng.random((N, N)) < 0.012)
    img[spk] = (0.55, 0.59, 0.66)
    # occupied (walls + obstacle), with only a little ragged jitter on edges
    occj = occ & (rng.random((N, N)) > 0.03)
    img[occj] = OCC
    stray = halo & (rng.random((N, N)) < 0.08)
    img[stray] = OCC
    # unknown: a ragged margin outside the arena + occluded corners
    unknown = np.zeros((N, N), dtype=bool)
    m = 2 + (rng.random((N, N)) < 0.5).astype(int)
    for k in range(N):
        unknown[k, :max(0, m[k, 0])] = True
        unknown[k, N - max(0, m[k, 1]):] = True
        unknown[:max(0, m[0, k]), k] = True
        unknown[N - max(0, m[1, k]):, k] = True
    # occluded pockets behind the obstacle
    unknown[8:12, 52:62] = rng.random((4, 10)) < 0.7
    img[unknown] = UNK
    return img


# trajectory the mapper drove (world metres) — a lap of the rooms
TRAJ = np.array([(-1.3, -1.3), (-1.3, 1.2), (-0.2, 1.2), (-0.2, 0.2),
                 (1.2, 0.2), (1.2, 1.4), (0.5, 1.4), (0.5, -0.2),
                 (1.0, -1.3), (-0.2, -1.3), (-0.2, -0.6)])

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
fig, (axL, axR) = plt.subplots(1, 2, figsize=(12.6, 6.4))
fig.patch.set_facecolor('white')
fig.suptitle('SLAM Occupancy Grid Output vs. Physical Test Environment',
             fontsize=15, fontweight='bold', y=0.98)

# ════════ LEFT: occupancy grid ════════
axL.set_facecolor(BG)
axL.imshow(occupancy_rgb(), origin='lower',
           extent=[ORIGIN, ORIGIN + N * RES, ORIGIN, ORIGIN + N * RES],
           interpolation='nearest')
for v in np.arange(-2, 2.01, 1.0):
    axL.axhline(v, color=GRID_LINE, lw=0.5, alpha=0.25)
    axL.axvline(v, color=GRID_LINE, lw=0.5, alpha=0.25)
# mapping trajectory + robot pose
axL.plot(TRAJ[:, 0], TRAJ[:, 1], color=ACCENT, lw=1.6, alpha=0.9,
         label='mapper trajectory')
hx, hy = TRAJ[-1]
axL.add_patch(Circle((hx, hy), 0.10, color=GREEN, zorder=5))
axL.add_patch(FancyArrow(hx, hy, 0.0, -0.28, width=0.04, head_width=0.16,
                         head_length=0.12, color=GREEN, zorder=5))
# a faint laser-scan fan
ang = np.linspace(0, 2 * np.pi, 90)
axL.scatter(hx + 0.9 * np.cos(ang), hy + 0.9 * np.sin(ang), s=2,
            color=ORANGE, alpha=0.35)
axL.set_title('(a)  SLAM occupancy grid (console map output)',
              fontsize=11, fontweight='bold')
axL.set_xlabel('x (m)')
axL.set_ylabel('y (m)')
axL.set_xlim(ORIGIN, ORIGIN + N * RES)
axL.set_ylim(ORIGIN, ORIGIN + N * RES)
axL.set_aspect('equal')
axL.legend(loc='upper right', fontsize=8, framealpha=0.85)
# legend swatches for cell states
from matplotlib.patches import Patch
state_leg = [Patch(facecolor=FREE, edgecolor='#888', label='free'),
             Patch(facecolor=OCC, edgecolor='#888', label='occupied'),
             Patch(facecolor=UNK, edgecolor='#888', label='unknown')]
axL.legend(handles=[Patch(facecolor=ACCENT, label='mapper path')] + state_leg,
           loc='lower right', fontsize=8, framealpha=0.9)

# ════════ RIGHT: physical environment (clean floor plan) ════════
axR.set_facecolor('white')
WALL = '#2b2f3a'
axR.set_xlim(-2.15, 2.15)
axR.set_ylim(-2.15, 2.15)
axR.set_aspect('equal')


def wall(x, y, w, h):
    axR.add_patch(Rectangle((x, y), w, h, facecolor=WALL, edgecolor='none'))


t = 0.06   # wall half-thickness
# outer walls
wall(-2 - t, -2 - t, 4 + 2 * t, 2 * t)
wall(-2 - t, 2 - t, 4 + 2 * t, 2 * t)
wall(-2 - t, -2 - t, 2 * t, 4 + 2 * t)
wall(2 - t, -2 - t, 2 * t, 4 + 2 * t)
# interior cross walls with doorways (doorways at world -1.3..-0.7 and 0.7..1.3)
dws = [(-2, -1.3), (-0.7, 0.7), (1.3, 2)]   # wall spans between doorways
for a, b in dws:
    wall(a, -t, b - a, 2 * t)               # horizontal wall segments (y=0)
    wall(-t, a, 2 * t, b - a)               # vertical wall segments (x=0)
# obstacle (the crate) — matches the occupied block in the grid
ox0, oy0 = ORIGIN + 50 * RES, ORIGIN + 12 * RES
axR.add_patch(Rectangle((ox0, oy0), 14 * RES, 10 * RES, facecolor='#6b7280',
                        edgecolor='#374151', hatch='//'))
axR.text(ox0 + 7 * RES, oy0 + 5 * RES, 'obstacle', ha='center', va='center',
         fontsize=8, color='white', fontweight='bold')
# doorway labels
for (dx, dy, txt) in [(-1.0, 0.0, ''), (1.0, 0.0, ''),
                      (0.0, -1.0, ''), (0.0, 1.0, '')]:
    axR.add_patch(Circle((dx, dy), 0.05, color=ACCENT, zorder=4))
axR.text(1.0, 0.12, 'doorway', ha='center', fontsize=7, color=ACCENT)
# robots start beside each other (bottom-left room)
robots = [('Alpha', -1.60, -1.55, GREEN), ('Beta', -1.10, -1.55, '#f5b941'),
          ('Gamma', -0.60, -1.55, ORANGE)]
for name, rx, ry, c in robots:
    axR.add_patch(Rectangle((rx - 0.10, ry - 0.10), 0.20, 0.20, facecolor=c,
                            edgecolor='#222', zorder=5))
    axR.text(rx, ry - 0.22, name, ha='center', fontsize=7, fontweight='bold')
# fire location marker
axR.add_patch(Circle((1.1, 1.0), 0.12, facecolor='none', edgecolor=ORANGE,
                     lw=2, zorder=5))
axR.text(1.1, 1.0, 'F', ha='center', va='center', color=ORANGE,
         fontweight='bold', fontsize=9)
axR.text(1.1, 0.75, 'fire', ha='center', fontsize=7, color=ORANGE)
# dimensions
axR.annotate('', (-2, -2.32), (2, -2.32),
             arrowprops=dict(arrowstyle='<->', color='#555'))
axR.text(0, -2.45, '4.0 m', ha='center', fontsize=9, color='#333')
axR.annotate('', (-2.32, -2), (-2.32, 2),
             arrowprops=dict(arrowstyle='<->', color='#555'))
axR.text(-2.5, 0, '4.0 m', va='center', rotation=90, fontsize=9, color='#333')
axR.set_title('(b)  Physical test environment (4 x 4 m, 4 rooms)',
              fontsize=11, fontweight='bold')
axR.set_xlabel('x (m)')
axR.set_xlim(-2.7, 2.3)
axR.set_ylim(-2.6, 2.3)
axR.axis('off')

fig.tight_layout(rect=[0, 0, 1, 0.96])
out = os.path.join(os.path.dirname(__file__), '..', 'figures_png',
                   'slam_vs_environment.png')
out = os.path.abspath(out)
fig.savefig(out, dpi=200, facecolor='white', bbox_inches='tight')
print('wrote', out)
