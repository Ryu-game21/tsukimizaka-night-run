"""heights + camber for the Suzuka centre line; handles the crossover (two road levels) by continuity -> course.json"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, triangles
D = os.environ.get('D', './')
SC = json.load(open(D + 'scale.json'))['scale']
ROADM = set(os.environ.get('ROADM', '282_69,282_64').split(','))
J, B = load(D + os.environ.get('GLB', 'suz.glb'))
X, Z, HW = np.load(D + 'cl_xz.npy').T
RES = 0.5
x0, z0 = X.min() - 40, Z.min() - 40
Wd = int((X.max() + 40 - x0) / RES); Hd = int((Z.max() + 40 - z0) / RES)
hmax = np.full((Hd, Wd), np.nan); hmin = np.full((Hd, Wd), np.nan); isroad = np.zeros((Hd, Wd), bool)
for m, t, nn in triangles(J, B):
    if m not in ROADM: continue
    for tr in t * SC:
        xs = (tr[:, 0] - x0) / RES; zs = (tr[:, 2] - z0) / RES
        i0, i1 = int(max(0, np.floor(zs.min()))), int(min(Hd - 1, np.ceil(zs.max())))
        j0, j1 = int(max(0, np.floor(xs.min()))), int(min(Wd - 1, np.ceil(xs.max())))
        if i1 < i0 or j1 < j0: continue
        yy, xx = np.mgrid[i0:i1 + 1, j0:j1 + 1] + 0.5
        a, b, c = np.c_[xs, zs]
        dd = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(dd) < 1e-9: continue
        l1 = ((b[1] - c[1]) * (xx - c[0]) + (c[0] - b[0]) * (yy - c[1])) / dd
        l2 = ((c[1] - a[1]) * (xx - c[0]) + (a[0] - c[0]) * (yy - c[1])) / dd
        l3 = 1 - l1 - l2
        mk = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
        h = l1 * tr[0, 1] + l2 * tr[1, 1] + l3 * tr[2, 1]
        s1 = hmax[i0:i1 + 1, j0:j1 + 1]; s2 = hmin[i0:i1 + 1, j0:j1 + 1]
        u = mk & (np.isnan(s1) | (h > s1)); s1[u] = h[u]
        u = mk & (np.isnan(s2) | (h < s2)); s2[u] = h[u]
        if m == sorted(ROADM)[0] or m == os.environ.get('MAINROAD'): isroad[i0:i1 + 1, j0:j1 + 1] |= mk
np.save(D + 'hmax.npy', hmax); np.save(D + 'hmin.npy', hmin); json.dump([x0, z0, RES], open(D + 'hmap_meta.json', 'w'))
def cell(x, z):
    j = int((x - x0) / RES); i = int((z - z0) / RES)
    return (i, j) if 0 <= i < Hd and 0 <= j < Wd else None
def hpick(x, z, ref):
    c = cell(x, z)
    if c is None or np.isnan(hmax[c]): return np.nan
    a, b = hmax[c], hmin[c]
    if os.environ.get('TOP'): return a
    if ref is None or not np.isfinite(ref): return a
    return a if abs(a - ref) <= abs(b - ref) else b
n = len(X)
BMAX = float(os.environ.get('BMAX', 0.12)); BTOL = float(os.environ.get('BTOL', 0))
T = np.c_[np.roll(X, -1) - np.roll(X, 1), np.roll(Z, -1) - np.roll(Z, 1)]; T /= np.linalg.norm(T, axis=1, keepdims=True)
NR = np.c_[T[:, 1], -T[:, 0]]
# widths in the main-straight gap (no 282_69 there): interpolate from neighbours
gap = np.array([not isroad[cell(X[k], Z[k])] if cell(X[k], Z[k]) else True for k in range(n)])
if gap.any(): HW[gap] = np.interp(np.nonzero(gap)[0], np.nonzero(~gap)[0], HW[~gap], period=n)
print('points off 282_69:', gap.sum())
HWc = np.clip(HW, float(os.environ.get('HWMIN', 5.0)), 8.0)
# pass 1: centre heights, two levels -> continuity (start from a point with a single level)
amb = np.array([(lambda c: c is not None and np.isfinite(hmax[c]) and hmax[c] - hmin[c] > 1.5)(cell(X[k], Z[k])) for k in range(n)])
print('two-level points', amb.sum())
k0 = int(np.nonzero(~amb)[0][0]); Yc = np.full(n, np.nan)
ref = None
for s in range(n):
    k = (k0 + s) % n
    Yc[k] = hpick(X[k], Z[k], ref)
    if np.isfinite(Yc[k]):
        # predict with the recent slope
        prev = [Yc[(k - q) % n] for q in range(0, 6)]
        ref = Yc[k] if not np.isfinite(prev[-1]) else Yc[k] + (Yc[k] - prev[-1]) / 5
bad = ~np.isfinite(Yc)
if bad.any(): Yc[bad] = np.interp(np.nonzero(bad)[0], np.nonzero(~bad)[0], Yc[~bad], period=n)
# pass 2: lateral fit using the level nearest the centre
Y = np.full(n, np.nan); BK = np.zeros(n)
for k in range(n):
    offs = np.linspace(-0.9, 0.9, 13) * HWc[k]
    hs = np.array([hpick(X[k] + NR[k, 0] * o, Z[k] + NR[k, 1] * o, Yc[k]) for o in offs])
    ok = np.isfinite(hs)
    if ok.any(): ok &= np.abs(hs - Yc[k]) < 0.8 + BTOL * np.abs(offs)
    if ok.sum() >= 4:
        sol = np.linalg.lstsq(np.c_[np.ones(ok.sum()), offs[ok]], hs[ok], rcond=None)[0]; Y[k], BK[k] = sol
    else: Y[k] = Yc[k]
def cs(a, w):
    k = np.ones(w) / w; return np.convolve(np.r_[a[-w:], a, a[:w]], k, 'same')[w:-w]
Y = cs(cs(Y, 3), 3); BK = np.clip(cs(cs(BK, 5), 5), -BMAX, BMAX)
worst = 0; wk = 0
for k in range(n):
    for o in np.linspace(-0.9, 0.9, 7) * HWc[k]:
        h = hpick(X[k] + NR[k, 0] * o, Z[k] + NR[k, 1] * o, Y[k])
        if np.isfinite(h) and abs(h - Y[k]) < 0.8 + BTOL * abs(o) and h - (Y[k] + BK[k] * o) > worst: worst = h - (Y[k] + BK[k] * o); wk = k
print(f'elev {Y.min():.1f}..{Y.max():.1f}  bank {BK.min():.3f}..{BK.max():.3f}  worst sink {worst:.2f} m at {wk}')
json.dump({'pts': np.c_[X, Y, Z].round(2).tolist(), 'hw': HWc.round(2).tolist(), 'bank': BK.round(4).tolist()}, open(D + 'course.json', 'w'))
