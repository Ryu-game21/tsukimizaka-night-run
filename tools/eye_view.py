"""Perspective z-buffer render from the driver's eye at course index k (coloured by material, with names of big blockers).
usage: eye_view.py model.glb course.json k out.png [height] [back]"""
import sys, os, json, zlib
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, triangles
path, course, k, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
hgt = float(sys.argv[5]) if len(sys.argv) > 5 else 1.1
back = float(sys.argv[6]) if len(sys.argv) > 6 else 0
J, B = load(path)
c = json.load(open(course)); P = np.array(c['pts']); n = len(P)
f = P[(k + 5) % n] - P[(k - 5) % n]; f[1] = 0; f /= np.linalg.norm(f)
eye = P[k] + np.array([0, hgt, 0]) - f * back
fwd = P[(k + 12) % n] + np.array([0, 0.6 if back == 0 else 0, 0]) - eye; fwd /= np.linalg.norm(fwd)
rt = np.cross(fwd, [0, 1, 0]); rt /= np.linalg.norm(rt); up = np.cross(rt, fwd)
Wd, Hd, fov = 640, 360, np.radians(70)
fl = (Wd / 2) / np.tan(fov / 2)
img = np.full((Hd, Wd, 3), 200, np.uint8); zb = np.full((Hd, Wd), 1e9); owner = np.full((Hd, Wd), -1)
names = []
L = np.array([0.4, 0.8, 0.45]); L /= np.linalg.norm(L)
for m, t, nn in triangles(J, B):
    cen = t.mean(1)
    sel = np.linalg.norm(cen - eye, axis=1) < 400
    if not sel.any(): continue
    t = t[sel]
    names.append(m); mid = len(names) - 1
    col = np.array([(zlib.crc32(m.encode()) >> s) & 255 for s in (0, 8, 16)]) * 0.6 + 60
    if m == 'tentrail_32': col = np.array([90, 90, 95])
    N = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]); N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
    sh = 0.45 + 0.55 * np.abs(N @ L)
    rel = t - eye
    cx = rel @ rt; cy = rel @ up; cz = rel @ fwd
    for tri in range(len(t)):
        zz = cz[tri]
        if (zz < 0.2).any(): continue
        X = Wd / 2 + cx[tri] / zz * fl; Y = Hd / 2 - cy[tri] / zz * fl
        x0, x1 = int(max(0, np.floor(X.min()))), int(min(Wd - 1, np.ceil(X.max())))
        y0, y1 = int(max(0, np.floor(Y.min()))), int(min(Hd - 1, np.ceil(Y.max())))
        if x1 < x0 or y1 < y0: continue
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1] + 0.5
        a, b, cc = np.c_[X, Y]
        d = (b[1] - cc[1]) * (a[0] - cc[0]) + (cc[0] - b[0]) * (a[1] - cc[1])
        if abs(d) < 1e-9: continue
        l1 = ((b[1] - cc[1]) * (xx - cc[0]) + (cc[0] - b[0]) * (yy - cc[1])) / d
        l2 = ((cc[1] - a[1]) * (xx - cc[0]) + (a[0] - cc[0]) * (yy - cc[1])) / d
        l3 = 1 - l1 - l2; mk = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        z = 1 / (l1 / zz[0] + l2 / zz[1] + l3 / zz[2])
        yi, xi = yy[mk].astype(int), xx[mk].astype(int); z = z[mk]
        u = z < zb[yi, xi]; zb[yi[u], xi[u]] = z[u]; img[yi[u], xi[u]] = (col * sh[tri]).astype(np.uint8); owner[yi[u], xi[u]] = mid
im = Image.fromarray(img); d = ImageDraw.Draw(im)
# label the materials covering the most of the lower-middle of the frame
reg = owner[Hd // 2 - 40:Hd // 2 + 60, Wd // 4:3 * Wd // 4]
ids, cnt = np.unique(reg[reg >= 0], return_counts=True)
y = 4
for i_, c_ in sorted(zip(ids, cnt), key=lambda x: -x[1])[:6]:
    d.text((4, y), f'{names[i_]} {c_}', fill=(255, 255, 255)); y += 12
im.save(out)
