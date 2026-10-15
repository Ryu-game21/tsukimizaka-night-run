"""Post-fit adjustments on cl_xz.npy:
 - optional separating-line raster (e.g. pit-lane line): where it lies within reach on one side, the band is fitted
   between that line and the road edge on the other side
 - hw capped by the turning radius (no folded inner edge)
usage: band_limit.py [sepline.npy]"""
import sys, json, numpy as np
from scipy.ndimage import gaussian_filter1d as gf
C = np.load('cl_xz.npy'); P = C[:, :2].copy(); HW = C[:, 2].copy(); n = len(P)
A = np.load('road.npy'); x0, z0, R = json.load(open('grid.json')); H, W = A.shape
def cell(M, q):
    j = int((q[0] - x0) / R); i = int((q[1] - z0) / R)
    return 0 <= i < H and 0 <= j < W and M[i, j]
T = np.roll(P, -1, 0) - np.roll(P, 1, 0); T /= np.linalg.norm(T, axis=1)[:, None]; N = np.c_[-T[:, 1], T[:, 0]]
if len(sys.argv) > 1:
    S = np.load(sys.argv[1]); off = np.zeros(n); hit = np.zeros(n, bool); hwn = HW.copy()
    for k in range(n):
        for s in (1, -1):
            d = 0.0; ds = None
            while d < 25:
                d += 0.25
                if cell(S, P[k] + s * d * N[k]): ds = d; break
                if not cell(A, P[k] + s * d * N[k]) and d > 2: break
            if ds is None: continue
            # other side road edge
            e = 0.0; last = 0.0
            while e < 40:
                e += 0.25
                if cell(A, P[k] - s * e * N[k]): last = e
                elif e - last > 1.0: break
            a, b = -last, ds - 0.6       # span along s*N
            off[k] = s * (a + b) / 2; hwn[k] = (b - a) / 2 - 0.3; hit[k] = True; break
    print('separator found at', hit.sum(), 'points')
    w = gf(hit.astype(float), 4, mode='wrap'); w = np.clip(w * 1.5, 0, 1)
    offs = np.where(hit, off, 0.0); offs = gf(offs, 2, mode='wrap') / np.maximum(gf(hit.astype(float), 2, mode='wrap'), 1e-3)
    offs = np.where(gf(hit.astype(float), 2, mode='wrap') > 0.05, offs, 0.0)
    P = P + (offs * w)[:, None] * N
    hwn = np.where(hit, hwn, HW); HW = HW * (1 - w) + gf(hwn, 2, mode='wrap') * w
# radius cap: circumradius over +-2 points, local minimum over +-3
from scipy.ndimage import minimum_filter1d
a = np.roll(P, 2, 0); b = P; c = np.roll(P, -2, 0)
ab = np.linalg.norm(a - b, axis=1); bc = np.linalg.norm(b - c, axis=1); ca = np.linalg.norm(c - a, axis=1)
cr = np.abs((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])) / 2
Rr = ab * bc * ca / np.maximum(4 * cr, 1e-9); Rr = minimum_filter1d(np.minimum(Rr, 1000), 7, mode='wrap')
cap = np.maximum(0.85 * Rr, 4.0); HWc = np.minimum(HW, cap)
HWc = minimum_filter1d(HWc, 3, mode='wrap')
print('hw capped at', (HWc < HW - 0.05).sum(), 'points; min hw', HWc.min().round(1))
np.save('cl_xz.npy', np.c_[P, HWc])
