"""Top-down (and oblique) z-buffer render of a region of a track model, coloured by material.
usage: render_region.py model.glb out.png cx cz half_size [course.json] [oblique]"""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, triangles

path, out, cx, cz, hs = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
course = sys.argv[6] if len(sys.argv) > 6 else None
oblique = len(sys.argv) > 7
J, B = load(path)
S = 700; px = S / (2 * hs)
img = np.full((S, S, 3), 235, np.uint8); zb = np.full((S, S), -1e9)
rng = np.random.default_rng(1); pal = {}
light = np.array([0.35, 0.85, 0.4]); light /= np.linalg.norm(light)
for m, t, nn in triangles(J, B):
    c = t.mean(1)
    sel = (np.abs(c[:, 0] - cx) < hs + 5) & (np.abs(c[:, 2] - cz) < hs + 5)
    if not sel.any(): continue
    t = t[sel]
    if m not in pal:
        ml = m.lower()
        pal[m] = (np.array([0.35, 0.35, 0.38]) if 'asph' in ml else np.array([0.2, 0.55, 0.25]) if ('tree' in ml or 'bush' in ml or 'grass' in ml or 'hedge' in ml)
                  else np.array([0.85, 0.85, 0.85]) if 'line' in ml else rng.uniform(0.4, 0.95, 3))
    N = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]); N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
    sh = 0.35 + 0.65 * np.abs(N @ light)
    for tr, s_ in zip(t, sh):
        if oblique:  # look from the south-east at 35 degrees
            X = (tr[:, 0] - cx) * px + S / 2; Y = (-(tr[:, 2] - cz) * 0.82 - tr[:, 1] * 0.57) * px + S / 2 + 60; D = tr[:, 2] * 0.57 - tr[:, 1] * 0.82 * -1
        else:
            X = (tr[:, 0] - cx) * px + S / 2; Y = (tr[:, 2] - cz) * px + S / 2; D = tr[:, 1]
        x0, x1 = int(max(0, np.floor(X.min()))), int(min(S - 1, np.ceil(X.max())))
        y0, y1 = int(max(0, np.floor(Y.min()))), int(min(S - 1, np.ceil(Y.max())))
        if x1 < x0 or y1 < y0: continue
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1] + 0.5
        a, b, c = np.c_[X, Y]
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-9: continue
        l1 = ((b[1] - c[1]) * (xx - c[0]) + (c[0] - b[0]) * (yy - c[1])) / d
        l2 = ((c[1] - a[1]) * (xx - c[0]) + (a[0] - c[0]) * (yy - c[1])) / d
        l3 = 1 - l1 - l2; mk = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        z = l1 * D[0] + l2 * D[1] + l3 * D[2]
        yi, xi = yy[mk].astype(int), xx[mk].astype(int); zz = z[mk]
        up = zz > zb[yi, xi]; zb[yi[up], xi[up]] = zz[up]; img[yi[up], xi[up]] = (pal[m] * s_ * 255).astype(np.uint8)
im = Image.fromarray(img)
if course and not oblique:
    C = np.array(json.load(open(course))['pts']); d = ImageDraw.Draw(im)
    pts = [((p[0] - cx) * px + S / 2, (p[2] - cz) * px + S / 2) for p in C]
    d.line(pts, fill=(255, 200, 0), width=1)
im.save(out)
