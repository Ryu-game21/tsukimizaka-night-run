"""visible-road extents vs wall distance. usage: wall_check.py course.json road.npy grid.json runoff [write_rw cap]"""
import sys, json, numpy as np
from scipy.ndimage import maximum_filter1d, gaussian_filter1d
c = json.load(open(sys.argv[1])); A = np.load(sys.argv[2]); x0, z0, R = json.load(open(sys.argv[3])); ro = float(sys.argv[4]); H, W = A.shape
P = np.array(c['pts'])[:, [0, 2]]; hw = np.array(c['hw']); n = len(P)
T = np.roll(P, -1, 0) - np.roll(P, 1, 0); T /= np.linalg.norm(T, axis=1)[:, None]; N = np.c_[-T[:, 1], T[:, 0]]
def on(q):
    j = int((q[0] - x0) / R); i = int((q[1] - z0) / R); return 0 <= i < H and 0 <= j < W and A[i, j]
ext = np.zeros((n, 2))
for k in range(n):
    for si, s in enumerate((1, -1)):
        d = 0; last = 0
        while d < 60:
            d += 0.5
            if on(P[k] + s * d * N[k]): last = d
            elif d - last > 1.5: break
        ext[k, si] = last
over = ext.max(1) - (hw + ro)
off = (ext[:, 0] - ext[:, 1]) / 2
bad = np.nonzero(over > 0)[0]; g = []
for k in bad:
    if g and k - g[-1][-1] <= 3: g[-1].append(k)
    else: g.append([k])
for x in g: print('wall inside visible road', x[0], x[-1], 'by %.1f m' % over[x].max())
print('centre offset from road middle: >2 m at', int((np.abs(off) > 2).sum()), 'points; max', np.abs(off).max().round(1))
if len(sys.argv) > 5:
    cap = float(sys.argv[6]) if len(sys.argv) > 6 else 25
    rw = np.minimum(ext.max(1) + 2.0, hw + cap); rw = np.maximum(rw, hw + ro)
    rw = maximum_filter1d(rw, 5, mode='wrap'); rw = gaussian_filter1d(rw, 1.5, mode='wrap')
    c['rw'] = np.round(rw, 2).tolist(); json.dump(c, open(sys.argv[1], 'w')); print('rw written', rw.min().round(1), rw.max().round(1))
