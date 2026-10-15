"""find holes in the drivable surface: cells inside the road (|lat|<hw-0.3) not covered by any OPAQUE surface near road height.
usage: holes.py model.glb course.json [k0 k1]"""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, triangles
J, B = load(sys.argv[1]); c = json.load(open(sys.argv[2]))
P = np.array(c['pts']); hw = np.array(c['hw']); n = len(P)
k0, k1 = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (0, n)
blend = {m.get('name') for m in J['materials'] if m.get('alphaMode') in ('BLEND', 'MASK')}
X, Y, Z = P.T
T = np.c_[np.roll(X, -1) - np.roll(X, 1), np.roll(Z, -1) - np.roll(Z, 1)]; T /= np.linalg.norm(T, axis=1, keepdims=True); NR = np.c_[T[:, 1], -T[:, 0]]
RES = 0.25
ks = np.arange(k0, k1) % n
x0, x1 = X[ks].min() - 15, X[ks].max() + 15; z0, z1 = Z[ks].min() - 15, Z[ks].max() + 15
W, H = int((x1 - x0) / RES) + 1, int((z1 - z0) / RES) + 1
cov = np.zeros((H, W), np.int16); top = np.full((H, W), -1e9)
from matplotlib.path import Path
import matplotlib
from PIL import ImageDraw
im = Image.new('I', (W, H), 0); d = ImageDraw.Draw(im)
mats = {}
for m, t, nn in triangles(J, B):
    if m in blend: continue
    cen = t.mean(1)
    s = (t[:, :, 0].max(1) > x0) & (t[:, :, 0].min(1) < x1) & (t[:, :, 2].max(1) > z0) & (t[:, :, 2].min(1) < z1)
    for tr in t[s]:
        d.polygon([((v[0] - x0) / RES, (v[2] - z0) / RES) for v in tr], fill=1)
cov = np.asarray(im) > 0
# road cells
road = np.zeros((H, W), bool)
rd = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(rd)
for k in ks:
    k2 = (k + 1) % n
    q = [(X[k] + NR[k, 0] * s * (hw[k] - 0.3), Z[k] + NR[k, 1] * s * (hw[k] - 0.3)) for s in (1, -1)] + [(X[k2] + NR[k2, 0] * s * (hw[k2] - 0.3), Z[k2] + NR[k2, 1] * s * (hw[k2] - 0.3)) for s in (-1, 1)]
    dr.polygon([((x - x0) / RES, (z - z0) / RES) for x, z in q], fill=1)
road = np.asarray(rd) > 0
holes = road & ~cov
print('road cells', road.sum(), 'holes', holes.sum(), f'({holes.sum() * RES * RES:.1f} m2)')
if holes.any():
    from scipy import ndimage as ndi
    lab, nl = ndi.label(holes); sz = ndi.sum(holes, lab, range(1, nl + 1))
    for i in np.argsort(-sz)[:8]:
        yy, xx = np.nonzero(lab == i + 1); cx, cz = xx.mean() * RES + x0, yy.mean() * RES + z0
        k = ks[np.argmin((X[ks] - cx) ** 2 + (Z[ks] - cz) ** 2)]
        print(f'  hole {sz[i] * RES * RES:.1f} m2 at ({cx:.0f},{cz:.0f}) near idx {k}')
