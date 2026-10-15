"""Final bounds check of a course against its packed model.
usage: final_check.py model.glb course.json road1,road2 official_len_m
 - surface: every point of the band (12 lateral samples x every 2 m) must lie over an opaque road-material triangle
 - intrusion: non-road triangles inside 90% of the band between 0.3 m and 2.5 m above the road (walls/objects on track)
 - geometry: band edges must not fold (hw < turning radius), length and direction"""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, triangles
from scipy.spatial import cKDTree
from matplotlib.path import Path
path, course, roads, Loff = sys.argv[1], sys.argv[2], set(sys.argv[3].split(',')), float(sys.argv[4])
c = json.load(open(course)); P = np.array(c['pts']); hw = np.array(c['hw']); n = len(P)
C2 = P[:, [0, 2]]; T = np.roll(C2, -1, 0) - np.roll(C2, 1, 0); T /= np.linalg.norm(T, axis=1)[:, None]; N = np.c_[-T[:, 1], T[:, 0]]
L = np.sum(np.linalg.norm(np.roll(C2, -1, 0) - C2, axis=1))
sl = 0.5 * np.sum(C2[:, 0] * np.roll(C2[:, 1], -1) - np.roll(C2[:, 0], -1) * C2[:, 1])
a = np.roll(C2, 1, 0); b = C2; cc = np.roll(C2, -1, 0)
cr = np.abs((b[:, 0] - a[:, 0]) * (cc[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (cc[:, 0] - a[:, 0])) / 2
Rr = np.linalg.norm(a - b, axis=1) * np.linalg.norm(b - cc, axis=1) * np.linalg.norm(cc - a, axis=1) / np.maximum(4 * cr, 1e-9)
fold = np.nonzero(hw >= Rr)[0]
print(f'length {L:.0f} m (official {Loff:.0f}, {100*(L/Loff-1):+.1f}%), points {n}, direction', 'clockwise' if sl > 0 else 'anticlockwise')
print('hw', hw.min().round(1), np.median(hw).round(1), hw.max().round(1), '| folded edges at', fold.tolist()[:10])
# samples
S = []; K = []
for k in range(n):
    for f in np.linspace(0, 1, 2, endpoint=False):
        q = C2[k] * (1 - f) + C2[(k + 1) % n] * f; nn = N[k]
        for o in np.linspace(-0.95, 0.95, 12): S.append(q + o * hw[k] * nn); K.append(k)
S = np.array(S); K = np.array(K); cov = np.zeros(len(S), bool); soft = np.zeros(len(S), bool); kd = cKDTree(S)
J, B = load(path)
blend = {m.get('name') for m in J['materials'] if m.get('alphaMode') == 'BLEND'}
intr = {}
for m, t, nn_ in triangles(J, B):
    xz = t[:, :, [0, 2]]; lo = xz.min(1); hi = xz.max(1)
    cen = (lo + hi) / 2; rad = np.linalg.norm(hi - lo, axis=1) / 2 + 0.01
    isroad = m in roads and m not in blend
    nrm = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]); steep = np.abs(nrm[:, 1]) < 0.6 * (np.linalg.norm(nrm, axis=1) + 1e-12)
    flat_other = (m not in roads) and m not in blend
    for i in range(len(t)):
        idx = kd.query_ball_point(cen[i], rad[i])
        if not idx: continue
        idx = np.array(idx)
        pp = Path(xz[i]).contains_points(S[idx], radius=1e-6) | Path(xz[i][::-1]).contains_points(S[idx], radius=1e-6)
        if not pp.any(): continue
        hit = idx[pp]
        if isroad: cov[hit] = True
        elif flat_other and not steep[i]:
            ks0 = K[hit]; near = np.abs(t[i, :, 1].mean() - P[ks0, 1]) < 0.6
            soft[hit[near]] = True
        elif m not in roads and steep[i]:
            ks = K[hit]; inner = np.abs(np.dot(S[hit] - C2[ks], np.c_[N[ks]].T).diagonal()) if False else None
            # height of the triangle above the road at these samples
            yt = t[i, :, 1].mean(); yr = P[ks, 1]
            band = np.linalg.norm(S[hit] - C2[ks], axis=1) < 0.9 * hw[ks]
            ok = band & (t[i, :, 1].max() - yr > 0.3) & (t[i, :, 1].min() - yr < 2.5)
            if ok.any(): intr.setdefault(m, set()).update(ks[ok].tolist())
edge = ~cov & soft; miss = np.nonzero(~cov & ~soft)[0]
print(f'samples on flat non-road surface at road level (kerb/paint/verge): {edge.mean()*100:.2f}%; at |offset|<0.7hw: {(edge & (np.abs(np.tile(np.linspace(-0.95,0.95,12),len(S)//12))<0.7)).sum()}')
print(f'road-surface coverage {cov.mean()*100:.2f}% ; samples with no surface at all: {len(miss)} at indices', sorted(set(K[miss].tolist()))[:30])
print('objects inside the band:', {m: sorted(v)[:12] for m, v in intr.items()} if intr else 'none')
