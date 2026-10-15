"""Centre line + half width from a racing-line loop and the road raster.
usage: fit_band.py HWT [iters]   (in a dir with loop.npy, road.npy, grid.json) -> cl_xz.npy, scale.json, band.json"""
import sys, json, numpy as np
from scipy.ndimage import gaussian_filter1d as gf
HWT = float(sys.argv[1]); IT = int(sys.argv[2]) if len(sys.argv) > 2 else 2
XZ = np.load('loop.npy'); A = np.load('road.npy'); x0, z0, R = json.load(open('grid.json')); H, W = A.shape
def resample(P, step):
    c = np.r_[P, P[:1]]; d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))]
    n = int(round(d[-1] / step)); s = np.linspace(0, d[-1], n, endpoint=False)
    return np.c_[np.interp(s, d, c[:, 0]), np.interp(s, d, c[:, 1])]
P = resample(XZ, 1.0)
P = np.c_[gf(P[:, 0], 6, mode='wrap'), gf(P[:, 1], 6, mode='wrap')]; P = resample(P, 1.0)
def on(x, z):
    j = int((x - x0) / R); i = int((z - z0) / R)
    return 0 <= i < H and 0 <= j < W and A[i, j]
def extents(P):
    T = np.roll(P, -1, 0) - np.roll(P, 1, 0); T /= np.linalg.norm(T, axis=1)[:, None]; N = np.c_[-T[:, 1], T[:, 0]]
    out = np.zeros((len(P), 2))
    for k in range(len(P)):
        for si, s in enumerate((1, -1)):
            e = 0.0; last = 0.0; d = 0.0
            while d < 30:
                d += 0.25
                if on(*(P[k] + s * d * N[k])): last = d
                elif d - last > 1.0: break
            out[k, si] = last
    return out, N
for it in range(IT):
    E, N = extents(P); Lr, Rr = E[:, 0], E[:, 1]
    hw = np.full(len(P), HWT); o = np.zeros(len(P))
    narrow = Lr + Rr <= 2 * HWT + 1
    o[narrow] = (Lr[narrow] - Rr[narrow]) / 2; hw[narrow] = np.maximum((Lr[narrow] + Rr[narrow]) / 2 - 0.3, 4.0)
    w = ~narrow; o[w] = np.clip(0, -Rr[w] + HWT, Lr[w] - HWT)
    import os
    if os.environ.get('CENTER'):
        cw = w & (Lr + Rr < float(os.environ['CENTER'])); o[cw] = (Lr[cw] - Rr[cw]) / 2
    o = gf(o, 8, mode='wrap'); hw = gf(hw, 10, mode='wrap')
    P = P + o[:, None] * N
    P = np.c_[gf(P[:, 0], 3, mode='wrap'), gf(P[:, 1], 3, mode='wrap')]
    print('iter', it, 'narrow share', narrow.mean().round(2), 'max |o|', np.abs(o).max().round(1))
# final widths at the fitted line
E, N = extents(P); hwf = np.minimum(np.interp(np.arange(len(P)), np.arange(len(P)), hw), np.minimum(E[:, 0], E[:, 1]) + 1.0)
hwf = np.clip(gf(hwf, 6, mode='wrap'), 4.0, HWT)
c = np.r_[P, P[:1]]; d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))]; L = d[-1]
n = int(round(L / 4)); s = np.linspace(0, L, n, endpoint=False)
X = np.interp(s, d, c[:, 0]); Z = np.interp(s, d, c[:, 1]); HW = np.interp(s, d, np.r_[hwf, hwf[:1]])
np.save('cl_xz.npy', np.c_[X, Z, HW]); json.dump({'scale': 1.0}, open('scale.json', 'w'))
print('length', round(L), 'pts', n, 'hw', HW.min().round(1), HW.max().round(1))
