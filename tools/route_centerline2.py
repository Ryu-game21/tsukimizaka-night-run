"""Yas Marina: GP-loop centre line from the asphalt skeleton graph (edges.json from the graph step).
Writes course.json in SCALED metres: pts [[x,y,z]] every 4 m, hw, bank (dy per metre of lateral offset along NR)."""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, triangles
import os
D = os.environ.get('D', './')
R, X0, Z0 = json.load(open(D + 'grid.json'))[2], *json.load(open(D + 'grid.json'))[:2]
E = json.load(open(D + 'edges.json'))
ROUTE = json.loads(os.environ['ROUTE'])
pts = []
for k in ROUTE:
    p = np.array(E[k][3], float)
    if pts:
        last = pts[-1]
        if np.linalg.norm(p[-1] - last) < np.linalg.norm(p[0] - last): p = p[::-1]
        gap = np.linalg.norm(p[0] - last)
        assert gap < 40, (k, gap)
        if gap > 2:  # bridge the crossover junction / gaps with a straight join
            m_ = int(gap); pts.extend((last + (p[0] - last) * (np.arange(1, m_) / m_)[:, None]).tolist())
    elif True:
        # first edge (19) runs N9 -> N24: orient so that the next edge (2) connects to its end
        q = np.array(E[ROUTE[1 % len(ROUTE)]][3], float)
        if len(ROUTE) == 1: q = p[:1] + 1e9  # single closed loop: keep the traced order
        if min(np.linalg.norm(p[0] - q[0]), np.linalg.norm(p[0] - q[-1])) < min(np.linalg.norm(p[-1] - q[0]), np.linalg.norm(p[-1] - q[-1])): p = p[::-1]
    pts.extend(p.tolist())
pts = np.array(pts)
gap = np.linalg.norm(pts[0] - pts[-1]); print('closing gap px', gap)
m_ = int(gap); pts = np.r_[pts, pts[-1] + (pts[0] - pts[-1]) * (np.arange(1, m_) / m_)[:, None]]
XZ = np.c_[(pts[:, 1] + 0.5) * R + X0, (pts[:, 0] + 0.5) * R + Z0]
# drop duplicates, resample every 2 m (model units)
d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(XZ, axis=0), axis=1))]
keep = np.r_[True, np.diff(d) > 1e-6]; XZ = XZ[keep]; d = d[keep]
Ltot = d[-1] + np.linalg.norm(XZ[-1] - XZ[0])
S0 = np.arange(0, Ltot, 1.0)
c = np.r_[XZ, XZ[:1]]; dd = np.r_[d, Ltot]
X = np.interp(S0, dd, c[:, 0]); Z = np.interp(S0, dd, c[:, 1])
def circ_smooth(a, w):
    k = np.ones(w) / w; return np.convolve(np.r_[a[-w:], a, a[:w]], k, 'same')[w:-w]
for _ in range(4): X, Z = circ_smooth(X, 9), circ_smooth(Z, 9)
L0 = np.sum(np.hypot(np.diff(np.r_[X, X[:1]]), np.diff(np.r_[Z, Z[:1]])))
SHC = float(os.environ.get("SHC", 2.5)); NIT = int(os.environ.get("NIT", 2))
SCALE = float(os.environ.get('TARGET', 0)) / L0 if os.environ.get('TARGET') else 1.0
print(f'model loop {L0:.1f} -> scale {SCALE:.4f}')
json.dump({'scale': SCALE}, open(D + 'scale.json', 'w'))
# --- recentre on the asphalt and measure widths (model units) ---
asph = np.load(D + 'asph.npy'); H, W = asph.shape
def inside(x, z):
    j = int((x - X0) / R); i = int((z - Z0) / R)
    return 0 <= i < H and 0 <= j < W and asph[i, j]
for it in range(NIT):
    T = np.c_[np.roll(X, -1) - np.roll(X, 1), np.roll(Z, -1) - np.roll(Z, 1)]; T /= np.linalg.norm(T, axis=1, keepdims=True)
    Nn = np.c_[T[:, 1], -T[:, 0]]   # = game NR (t.z, -t.x)
    hl, hr = [], []
    for k in range(len(X)):
        out = []
        for s in (1, -1):
            dd_ = 0.0
            while dd_ < 16 and inside(X[k] + Nn[k, 0] * s * (dd_ + 0.25), Z[k] + Nn[k, 1] * s * (dd_ + 0.25)): dd_ += 0.25
            out.append(dd_)
        hl.append(out[0]); hr.append(out[1])
    hl, hr = np.array(hl), np.array(hr)
    shift = np.clip((hl - hr) / 2, -SHC, SHC)
    shift = circ_smooth(circ_smooth(shift, 15), 15)
    X += Nn[:, 0] * shift; Z += Nn[:, 1] * shift
    for _ in range(2): X, Z = circ_smooth(X, 7), circ_smooth(Z, 7)
hw0 = np.clip((hl + hr) / 2, 4.0, 8.0); hw0 = circ_smooth(circ_smooth(hw0, 15), 15)
# --- scale up and resample every 4 m ---
X *= SCALE; Z *= SCALE; HWs = hw0 * SCALE
seg = np.r_[0, np.cumsum(np.hypot(np.diff(X), np.diff(Z)))]; Lt = seg[-1] + np.hypot(X[-1] - X[0], Z[-1] - Z[0])
n = int(round(Lt / 4.0)); S = np.linspace(0, Lt, n, endpoint=False)
cx = np.r_[X, X[:1]]; cz = np.r_[Z, Z[:1]]; cs = np.r_[seg, Lt]; ch = np.r_[HWs, HWs[:1]]
X = np.interp(S, cs, cx); Z = np.interp(S, cs, cz); HW = np.interp(S, cs, ch)
# start line: 45 % of the way down the main straight (the loop starts at the top of the straight)
st = int(round(n * 0)); 
print(f'scaled loop {Lt:.0f} m, {n} pts, hw {HW.min():.1f}-{HW.max():.1f}')
np.save(D + 'cl_xz.npy', np.c_[X, Z, HW])
