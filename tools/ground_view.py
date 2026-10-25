"""Top-down check of a ground scan: the model (grey = ground, red = steep / barriers), the centre line (yellow),
the band edges (white), the old symmetric wall (blue dashes) and the new per-side walls (green).
usage: python3 tools/ground_view.py <course id> k0 k1 out.png [ground.json]"""
import json, os, sys
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ground_scan as G

cid, k0, k1, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
c = json.load(open(os.path.join(G.ROOT, 'work/ground', cid + '.course.json')))
gpath = sys.argv[5] if len(sys.argv) > 5 else os.path.join(G.ROOT, 'site', os.path.dirname(c['model']), 'ground.json')
g = json.load(open(gpath))
P = np.array(c['pts']).reshape(-1, 3); n = len(P); hw = np.array(c['hw'])
rw = hw + c['runoff']
if c.get('rw'): rw = np.maximum(rw, np.array(c['rw']))
T = np.roll(P, -1, 0) - np.roll(P, 1, 0); T[:, 1] = 0; T /= np.linalg.norm(T, axis=1, keepdims=True); NR = np.c_[T[:, 2], -T[:, 0]]
ks = np.arange(k0, k1) % n; C = P[ks][:, [0, 2]]
x0, x1 = C[:, 0].min() - 50, C[:, 0].max() + 50; z0, z1 = C[:, 1].min() - 50, C[:, 1].max() + 50
V = G.load_model(c['model'])
m = (V[:, :, 0].max(1) > x0) & (V[:, :, 0].min(1) < x1) & (V[:, :, 2].max(1) > z0) & (V[:, :, 2].min(1) < z1)
V = V[m]; nrm = np.cross(V[:, 1] - V[:, 0], V[:, 2] - V[:, 0]); ny = np.abs(nrm[:, 1]) / np.maximum(np.linalg.norm(nrm, axis=1), 1e-9)
ymid = np.median(P[ks, 1])
fig, ax = plt.subplots(figsize=(14, 14 * (z1 - z0) / (x1 - x0) if x1 > x0 else 14))
flat = ny > 0.55
ax.add_collection(PolyCollection(V[flat][:, :, [0, 2]], facecolors=plt.cm.gray(np.clip((V[flat][:, :, 1].mean(1) - ymid + 8) / 16, 0, 1)), edgecolors='none'))
ax.add_collection(PolyCollection(V[~flat][:, :, [0, 2]], facecolors='none', edgecolors=(1, .2, .2, .8), linewidths=.6))
ax.plot(C[:, 0], C[:, 1], color='yellow', lw=1)
for sg in (1, -1):
    for arr, col, ls in ((hw[ks], 'white', '-'), (rw[ks], 'deepskyblue', '--'), (np.array(g['wp' if sg > 0 else 'wn'])[ks], 'lime', '-')):
        E = C + sg * arr[:, None] * NR[ks]; ax.plot(E[:, 0], E[:, 1], color=col, ls=ls, lw=1.4)
for k in range(k0, k1, 10):
    i = k % n; ax.text(P[i, 0], P[i, 2], str(i), color='yellow', fontsize=8)
ax.set_xlim(x0, x1); ax.set_ylim(z0, z1); ax.set_aspect('equal'); ax.set_facecolor('#203040')
ax.set_title(f'{cid} {k0}-{k1}: white band, blue old wall, green new wall, red = steep/barrier')
plt.savefig(out, dpi=60, bbox_inches='tight')
