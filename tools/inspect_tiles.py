"""Bounds inspection: top-down tiles along the whole lap, only geometry near road height (no roofs/trees),
road materials dark, with the course centre (yellow) and edges (red = right, blue = left).
usage: inspect_tiles.py model.glb course.json outprefix road1,road2 [step_pts] [half_size]"""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, triangles
path, course, outp, roads = sys.argv[1], sys.argv[2], sys.argv[3], set(sys.argv[4].split(','))
step = int(sys.argv[5]) if len(sys.argv) > 5 else 60; hs = float(sys.argv[6]) if len(sys.argv) > 6 else 80
c = json.load(open(course)); P = np.array(c['pts']); hw = np.array(c['hw']); n = len(P)
C2 = P[:, [0, 2]]
T = np.roll(C2, -1, 0) - np.roll(C2, 1, 0); T /= np.linalg.norm(T, axis=1)[:, None]; Nn = np.c_[-T[:, 1], T[:, 0]]
J, B = load(path)
rng = np.random.default_rng(1)
tris = []; cols = []
for m, t, nn in triangles(J, B):
    ml = m.lower()
    col = (np.array([0.3, 0.3, 0.33]) if m in roads else np.array([0.25, 0.6, 0.3]) if any(k in ml for k in ('grass', 'tree', 'bush', 'hedge', 'top', 'background', 'cypress', 'maple'))
           else np.array([0.85, 0.75, 0.5]) if any(k in ml for k in ('sand', 'gravel')) else rng.uniform(0.55, 0.95, 3))
    tris.append(t); cols.append(np.repeat(col[None], len(t), 0))
T3 = np.concatenate(tris); CO = np.concatenate(cols); cen = T3.mean(1)
S = 400; px = S / (2 * hs)
light = np.array([0.35, 0.85, 0.4]); light /= np.linalg.norm(light)
Nm = np.cross(T3[:, 1] - T3[:, 0], T3[:, 2] - T3[:, 0]); Nm /= np.linalg.norm(Nm, axis=1, keepdims=True) + 1e-12
SH = 0.45 + 0.55 * np.abs(Nm @ light)
ks = [int(v) for v in os.environ['KS'].split(',')] if os.environ.get('KS') else list(range(0, n, step)); tiles = []
for k in ks:
    cx, cz = C2[k]; near = np.abs(np.arange(n) - k); near = np.minimum(near, n - near) < step * 2
    ymax = P[near, 1].max() + 1.5
    sel = (np.abs(cen[:, 0] - cx) < hs + 30) & (np.abs(cen[:, 2] - cz) < hs + 30) & (T3[:, :, 1].min(1) < ymax)
    img = np.full((S, S, 3), 245, np.uint8); zb = np.full((S, S), -1e9)
    for tr, col, s_ in zip(T3[sel], CO[sel], SH[sel]):
        X = (tr[:, 0] - cx) * px + S / 2; Y = (tr[:, 2] - cz) * px + S / 2; D = np.minimum(tr[:, 1], ymax)
        x0, x1 = int(max(0, np.floor(X.min()))), int(min(S - 1, np.ceil(X.max()))); y0, y1 = int(max(0, np.floor(Y.min()))), int(min(S - 1, np.ceil(Y.max())))
        if x1 < x0 or y1 < y0: continue
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1] + 0.5
        a, b, cc = np.c_[X, Y]
        d = (b[1] - cc[1]) * (a[0] - cc[0]) + (cc[0] - b[0]) * (a[1] - cc[1])
        if abs(d) < 1e-9: continue
        l1 = ((b[1] - cc[1]) * (xx - cc[0]) + (cc[0] - b[0]) * (yy - cc[1])) / d; l2 = ((cc[1] - a[1]) * (xx - cc[0]) + (a[0] - cc[0]) * (yy - cc[1])) / d
        l3 = 1 - l1 - l2; mk = (l1 >= 0) & (l2 >= 0) & (l3 >= 0); z = l1 * D[0] + l2 * D[1] + l3 * D[2]
        yi, xi = yy[mk].astype(int), xx[mk].astype(int); zz = z[mk]; up = zz > zb[yi, xi]
        zb[yi[up], xi[up]] = zz[up]; img[yi[up], xi[up]] = (col * s_ * 255).astype(np.uint8)
    im = Image.fromarray(img); dr = ImageDraw.Draw(im)
    f = lambda q: ((q[0] - cx) * px + S / 2, (q[1] - cz) * px + S / 2)
    for sgn, colr in ((1, (220, 0, 0)), (-1, (0, 90, 255)), (0, (255, 200, 0))):
        pts = [f(C2[j] + sgn * hw[j] * Nn[j]) for j in range(n)] + [f(C2[0] + sgn * hw[0] * Nn[0])]
        dr.line(pts, fill=colr, width=2)
    for j in range(0, n, 10):
        q = f(C2[j])
        if 0 < q[0] < S and 0 < q[1] < S: dr.text((q[0] + 3, q[1]), str(j), fill=(0, 0, 0))
    dr.rectangle((0, 0, 60, 14), fill=(0, 0, 0)); dr.text((3, 2), f'#{k}', fill=(255, 255, 0))
    tiles.append(im)
per = 12
for p in range(0, len(tiles), per):
    sh = Image.new('RGB', (S * 4, S * 3), (255, 255, 255))
    for i, im in enumerate(tiles[p:p + per]): sh.paste(im, ((i % 4) * S, (i // 4) * S))
    sh.save(f'{outp}_{p // per}.png')
print('tiles', len(tiles), 'sheets', (len(tiles) + per - 1) // per)
