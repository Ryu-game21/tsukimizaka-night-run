#!/usr/bin/env python3
"""Find stretches where a course's centre line runs on a different road from the one the circuit is drawn on
(a pit lane, a service road, an old layout), by the surfaces under and beside the line.

usage: route_audit.py model.glb course.json [min_run_pts=10]

For every point it looks at the surface (top triangle near road height) across the track, from -30 m to +30 m.
"Lap surfaces" are the materials found under the centre on at least 45% of the lap: the main asphalt and,
on most scanned circuits, the rubbered racing groove. A stretch is reported when one of them disappears from
under the centre (|offset| <= 3 m) for min_run_pts points or more while it is still there off to one side
(6-30 m): the line has left the track the circuit is drawn on, and the offset tells you which way it is.
It is a finder: check every hit by eye (tools/inspect_tiles.py, or a top-down render in the game) - a long
corner where the groove hugs the inside also shows up, with a small offset.
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glblib import load, triangles  # noqa: E402

path, course = sys.argv[1], sys.argv[2]
MINRUN = int(sys.argv[3]) if len(sys.argv) > 3 else 10
J, B = load(path)
names, tri = [], []
for m, t, _ in triangles(J, B):
    names.append(m); tri.append((len(names) - 1, t))
c = json.load(open(course)); P = np.array(c['pts'], float); n = len(P); C2 = P[:, [0, 2]]
T = np.roll(C2, -1, 0) - np.roll(C2, 1, 0); T /= np.linalg.norm(T, axis=1)[:, None]; N = np.c_[-T[:, 1], T[:, 0]]
lo, hi = C2.min(0) - 40, C2.max(0) + 40; CELL = 4.0
# triangles near the course, hashed on a 4 m grid
from collections import defaultdict
grid = defaultdict(list); TT = []; TM = []
for mi, t in tri:
    cen = t.mean(1)[:, [0, 2]]
    keep = np.all((cen > lo) & (cen < hi), axis=1)
    for tr in t[keep]:
        k = len(TT); TT.append(tr); TM.append(mi)
        x0, z0 = tr[:, [0, 2]].min(0); x1, z1 = tr[:, [0, 2]].max(0)
        if (x1 - x0) * (z1 - z0) > 4e4: continue   # huge ground sheets: skip from the hash, they are never the track
        for gx in range(int((x0 - lo[0]) // CELL), int((x1 - lo[0]) // CELL) + 1):
            for gz in range(int((z0 - lo[1]) // CELL), int((z1 - lo[1]) // CELL) + 1):
                grid[(gx, gz)].append(k)
TT = np.array(TT); TM = np.array(TM)


def surface(x, z, y):
    best, by = -1, -1e9
    for k in grid.get((int((x - lo[0]) // CELL), int((z - lo[1]) // CELL)), ()):
        a, b, cc = TT[k]
        d = (b[2] - cc[2]) * (a[0] - cc[0]) + (cc[0] - b[0]) * (a[2] - cc[2])
        if abs(d) < 1e-12: continue
        l1 = ((b[2] - cc[2]) * (x - cc[0]) + (cc[0] - b[0]) * (z - cc[2])) / d
        l2 = ((cc[2] - a[2]) * (x - cc[0]) + (a[0] - cc[0]) * (z - cc[2])) / d
        l3 = 1 - l1 - l2
        if min(l1, l2, l3) < -1e-6: continue
        yy = l1 * a[1] + l2 * b[1] + l3 * cc[1]
        if y - 4.0 < yy < y + 3.0 and yy > by: best, by = TM[k], yy
    return best


OFF = np.arange(-30, 30.5, 1.0)
prof = np.full((n, len(OFF)), -1, int)
for k in range(n):
    for j, o in enumerate(OFF):
        q = C2[k] + o * N[k]; prof[k, j] = surface(q[0], q[1], P[k, 1])
cen = np.abs(OFF) <= 3; far = np.abs(OFF) >= 12
# materials that belong to the drawn track: often under the centre, rarely 12-30 m away (run-off, pit lanes and
# service roads share the plain asphalt, so the asphalt alone tells nothing; the rubbered groove, the track's own
# texture tiles do). Scanned circuits split them over several materials: take them as one family.
fam = []
for mi in set(prof[:, cen].ravel()) - {-1}:
    c_ = (prof[:, cen] == mi).any(1).mean(); f_ = (prof[:, far] == mi).mean(1).mean() * far.sum() / max(1, cen.sum())
    if c_ >= 0.05 and c_ >= 2.5 * f_: fam.append(mi)
F = np.isin(prof, fam)
under = F[:, cen].any(1)
print(os.path.basename(os.path.dirname(os.path.abspath(path))) or path, 'points', n, '| track family under the centre on %.0f%% of the lap:' % (under.mean() * 100),
      ', '.join(names[m] for m in fam))
hits = []
miss = ~under
if miss.any() and not miss.all():
    start = int(np.argmax(~miss)); order = [(start + i) % n for i in range(n)]; run = []
    for kk in order + [None]:
        if kk is not None and miss[kk]: run.append(kk); continue
        if len(run) >= MINRUN:
            side = []
            for r in run:
                js = np.nonzero(F[r] & (np.abs(OFF) >= 6))[0]
                if len(js): side.append(OFF[js][np.argmin(np.abs(OFF[js]))])
            if len(side) >= 0.6 * len(run):
                hits.append((run[0], run[-1], len(run), float(np.median(side))))
        run = []
for a, b, L, o in sorted(hits):
    print('  off the drawn track %5d-%5d (%3d pts, %4.0f m)  track surface %+.0f m to the side' % (a, b, L, L * 4, o))
if not hits: print('  no stretch off the drawn track')
