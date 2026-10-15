"""Find places on a scanned circuit where something blocks the driver's view of the road ahead.
Casts segments from eye height (1.1 m) to the road 20/40/70 m ahead every ~10 m of the lap and tests
them against (a) the circuit model triangles and (b) the game's own distant-ground skirts.
usage: sightlines.py model.glb course.json"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, triangles

J, B = load(sys.argv[1])
cd = json.load(open(sys.argv[2]))
C = np.array(cd['pts']); HWc = np.array(cd['hw'])
n = len(C)
T = np.roll(C, -1, 0) - np.roll(C, 1, 0); T[:, 1] = 0; T /= np.linalg.norm(T, axis=1, keepdims=True)
NR = np.c_[T[:, 2], np.zeros(n), -T[:, 0]]

from scipy.spatial import cKDTree
_kd = cKDTree(C[:, [0, 2]])
def below_roads(V, drop):
    # every skirt vertex sits under the lowest stretch of road within 450 m
    out = V.copy()
    for k, v in enumerate(V):
        near = _kd.query_ball_point(v[[0, 2]], 450)
        out[k, 1] = min(v[1], C[near, 1].min() - drop) if near else v[1]
    return out
def skirts():
    out = []
    for s in (1, -1):
        a = below_roads(C + NR * s * (HWc + 95)[:, None] + np.array([0, -3, 0]), 4)
        b = below_roads(C + NR * s * (HWc + 380)[:, None] + np.array([0, -70, 0]), 12)
        a2, b2 = np.roll(a, -1, 0), np.roll(b, -1, 0)
        out.append(np.stack([a, b, a2], 1)); out.append(np.stack([b, b2, a2], 1))
    return np.concatenate(out)

sets = {}
for m, t, nn in triangles(J, B):
    sets.setdefault(m, []).append(t)
groups = {k: np.concatenate(v) for k, v in sets.items()}
groups['__game_skirts__'] = skirts()
allT = np.concatenate(list(groups.values())); owner = np.concatenate([np.full(len(v), k, dtype=object) for k, v in groups.items()])
# spatial hash on xz, 20 m cells
CELL = 20.0
mn = allT.min(1); mx = allT.max(1)
from collections import defaultdict
grid = defaultdict(list)
for i in range(len(allT)):
    x0, x1 = int(np.floor(mn[i, 0] / CELL)), int(np.floor(mx[i, 0] / CELL))
    z0, z1 = int(np.floor(mn[i, 2] / CELL)), int(np.floor(mx[i, 2] / CELL))
    if (x1 - x0 + 1) * (z1 - z0 + 1) > 400:  # huge triangles (skirt) – register along a coarse sweep
        for gx in range(x0, x1 + 1, 1):
            for gz in range(z0, z1 + 1, 1): grid[(gx, gz)].append(i)
        continue
    for gx in range(x0, x1 + 1):
        for gz in range(z0, z1 + 1): grid[(gx, gz)].append(i)

def seg_hits(o, e):
    d = e - o; L = np.linalg.norm(d)
    cells = set()
    for t in np.linspace(0, 1, int(L / 5) + 2):
        p = o + d * t; cells.add((int(np.floor(p[0] / CELL)), int(np.floor(p[2] / CELL))))
    cand = np.unique(np.concatenate([np.array(grid[c], int) for c in cells if c in grid] or [np.zeros(0, int)]))
    if len(cand) == 0: return []
    v0, v1, v2 = allT[cand, 0], allT[cand, 1], allT[cand, 2]
    e1, e2 = v1 - v0, v2 - v0
    h = np.cross(d, e2); a = np.einsum('ij,ij->i', e1, h)
    ok = np.abs(a) > 1e-9
    f = np.where(ok, 1 / np.where(ok, a, 1), 0)
    s_ = o - v0; u = f * np.einsum('ij,ij->i', s_, h)
    q = np.cross(s_, e1); v = f * (q @ d); t = f * np.einsum('ij,ij->i', e2, q)
    hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0.02) & (t < 0.98)
    return list(zip(cand[hit], t[hit]))

IGN = set(os.environ['IGNORE'].split(',')) if os.environ.get('IGNORE') else None
ds = np.mean(np.linalg.norm(np.diff(C[:, [0, 2]], axis=0), axis=1))
report = defaultdict(list)
if len(sys.argv) > 3:  # chase-camera mode: camera behind & above the car looking at it
    back, up = float(sys.argv[3]), float(sys.argv[4])
    for i in range(0, n, max(1, int(10 / ds))):
        cam = C[(i - int(back / ds)) % n] + np.array([0, up, 0]); car = C[i] + np.array([0, 0.8, 0])
        for k, t in seg_hits(cam, car):
            m = owner[k]
            if (m in IGN) if IGN else m in ('asph.001', 'asph_new.001', 'line.001', 'kerb_new.001', 'CURB_B.001', 'groove1.001', 'groove2.001', 'groove3.001', 'groove_custom.001'): continue
            report[m].append((i, back, 0))
    dist = lambda i: int(i * ds)
    for m, hits in sorted(report.items(), key=lambda kv: -len(kv[1])):
        idxs = sorted(set(h[0] for h in hits)); spans = []
        for k in idxs:
            if spans and k - spans[-1][1] <= int(30 / ds): spans[-1][1] = k
            else: spans.append([k, k])
        print(f'{m:28s} blocked {len(hits):4d}  at ' + ', '.join(f'{dist(a)}-{dist(b)}m' for a, b in spans[:14]))
    sys.exit()
for i in range(0, n, max(1, int(10 / ds))):
    eye = C[i] + np.array([0, 1.1, 0])
    for ahead in (20, 40, 70):
        j = (i + int(ahead / ds)) % n
        tgt = C[j] + np.array([0, 0.6, 0])
        for k, t in seg_hits(eye, tgt):
            m = owner[k]
            # ignore the road surface itself being grazed and its decals (kerbs, lines)
            if (m in IGN) if IGN else m in ('asph.001', 'asph_new.001', 'line.001', 'kerb_new.001', 'CURB_B.001', 'groove1.001', 'groove2.001', 'groove3.001', 'groove_custom.001', 'carpet.001', 'carpet-full.001'):
                continue
            hp = eye + (tgt - eye) * t
            dd, jj = _kd.query(hp[[0, 2]])
            report[m].append((i, ahead, round(float(t) * ahead, 1), round(float(dd - HWc[jj]), 1), round(float(hp[1] - C[jj, 1]), 1)))
dist = lambda i: int(i * ds)
for m, hits in sorted(report.items(), key=lambda kv: -len(kv[1])):
    idxs = sorted(set(h[0] for h in hits))
    spans = []
    for k in idxs:
        if spans and k - spans[-1][1] <= int(30 / ds): spans[-1][1] = k
        else: spans.append([k, k])
    print(f'{m:28s} blocked rays {len(hits):4d}  at ' + ', '.join(f'{dist(a)}-{dist(b)}m' for a, b in spans[:12]))
    if os.environ.get('DETAIL'):
        H = np.array([h[3:] for h in hits]); print('      beyond-edge m: min %.1f med %.1f | height above road: min %.1f max %.1f' % (H[:, 0].min(), np.median(H[:, 0]), H[:, 1].min(), H[:, 1].max()))
