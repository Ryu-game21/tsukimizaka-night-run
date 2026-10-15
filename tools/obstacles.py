"""mark cells of the asphalt mask that are blocked by objects standing on it (pit walls, barriers...).
usage: obstacles.py model.glb road1,road2   (in a dir with asph.npy + grid.json) -> asph_drive.npy"""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, triangles
J, B = load(sys.argv[1]); road = set(sys.argv[2].split(','))
a = np.load('asph.npy'); x0, z0, R = json.load(open('grid.json')); H, W = a.shape
hm = np.full((H, W), np.nan)
tris = {m: [] for m in road}; other = []
for m, t, nn in triangles(J, B):
    (tris[m] if m in road else other).append(t)
im = Image.new('F', (W, H), -1e4); d = ImageDraw.Draw(im)
for m in road:
    for t in tris[m]:
        for tr in t: d.polygon([((v[0] - x0) / R, (v[2] - z0) / R) for v in tr], fill=float(tr[:, 1].mean()))
hm = np.asarray(im).copy(); hm[hm < -1e3] = np.nan
ob = Image.new('L', (W, H), 0); do = ImageDraw.Draw(ob)
T = np.concatenate(other); cen = T.mean(1)
j = ((cen[:, 0] - x0) / R).astype(int); i = ((cen[:, 2] - z0) / R).astype(int)
ok = (i >= 0) & (i < H) & (j >= 0) & (j < W)
rh = np.full(len(T), np.nan); rh[ok] = hm[i[ok], j[ok]]
# also consider triangles slightly off the asphalt: use a dilated height map
hd = hm.copy(); nanm = np.isnan(hd)
if nanm.any():
    idx = ndi.distance_transform_edt(nanm, return_distances=False, return_indices=True)
    hd = hm[idx[0], idx[1]]
rh2 = np.full(len(T), np.nan); rh2[ok] = hd[i[ok], j[ok]]
rh = np.where(np.isfinite(rh), rh, rh2)
nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); steep = np.abs(nrm[:, 1]) < 0.6 * (np.linalg.norm(nrm, axis=1) + 1e-12)
blk = np.isfinite(rh) & steep & (T[:, :, 1].max(1) - rh > 0.6) & (T[:, :, 1].min(1) - rh < 3.5)   # walls, posts, barriers (not terrain)
for tr in T[blk]: do.polygon([((v[0] - x0) / R, (v[2] - z0) / R) for v in tr], fill=1)
obs = ndi.binary_dilation(np.asarray(ob) > 0, iterations=1)
drive = a & ~obs
print('asphalt cells', a.sum(), 'blocked', (a & obs).sum())
np.save('asph_drive.npy', drive)
