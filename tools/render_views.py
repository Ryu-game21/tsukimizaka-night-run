"""Z-buffered triangle rasterizer (numpy) for checking a car model's fit.
Renders side / top / front / 3-quarter views after applying the game's fit transform,
with the ground line, expected axle positions and expected length drawn in.

usage: render_views.py model.glb out.png '{"s":1,"off":[0,0,0],"rotY":0,"drop":["floor"],"L":4.3,"wb":2.5,"H":1.3,"W":1.8}'
"""
import sys, json, os
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, triangles

path, out, cfg = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
J, B = load(path)
tris = []; mats = []
drop = [d.lower() for d in cfg.get('drop', [])]
names = []
for m, t, nn in triangles(J, B):
    if any(d == m.lower() or d == nn.lower() for d in drop):
        continue
    tris.append(t); mats.append(np.full(len(t), len(names))); names.append(m)
T = np.concatenate(tris); MI = np.concatenate(mats)
s = cfg.get('s', 1.0); off = np.array(cfg.get('off', [0, 0, 0]), float)
T = (T + off) * s
if cfg.get('rotY'):
    T[..., 0] *= -1; T[..., 2] *= -1

# a stable pseudo-colour per material, so different parts read apart
rng = np.random.default_rng(3)
pal = rng.uniform(0.35, 0.95, (len(names), 3))
for k, n in enumerate(names):
    nl = n.lower()
    if any(w in nl for w in ('tire', 'tyre', 'rubber')): pal[k] = (0.15, 0.15, 0.17)
    if any(w in nl for w in ('glass', 'window', 'vitre', 'windo')): pal[k] = (0.45, 0.65, 0.85)

def raster(P, D, N, W, H, flipx=False):
    """P: (n,3,2) pixel coords, D: (n,3) depth (larger = nearer), returns rgb image"""
    img = np.full((H, W, 3), 245, np.uint8); zb = np.full((H, W), -1e9)
    light = np.array([0.4, 0.75, 0.55]); light /= np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.abs(N @ light)
    col = (pal[MI] * shade[:, None] * 255).astype(np.uint8)
    x0 = np.floor(P[:, :, 0].min(1)).astype(int); x1 = np.ceil(P[:, :, 0].max(1)).astype(int)
    y0 = np.floor(P[:, :, 1].min(1)).astype(int); y1 = np.ceil(P[:, :, 1].max(1)).astype(int)
    ok = (x1 >= 0) & (x0 < W) & (y1 >= 0) & (y0 < H)
    for i in np.nonzero(ok)[0]:
        a, b, c = P[i]
        xs = np.arange(max(x0[i], 0), min(x1[i], W - 1) + 1); ys = np.arange(max(y0[i], 0), min(y1[i], H - 1) + 1)
        if len(xs) == 0 or len(ys) == 0: continue
        X, Y = np.meshgrid(xs + .5, ys + .5)
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        l1 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / d
        l2 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / d
        l3 = 1 - l1 - l2
        m = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
        if not m.any(): continue
        z = l1 * D[i, 0] + l2 * D[i, 1] + l3 * D[i, 2]
        yy, xx = Y[m].astype(int), X[m].astype(int); zz = z[m]
        sub = zz > zb[yy, xx]
        zb[yy[sub], xx[sub]] = zz[sub]; img[yy[sub], xx[sub]] = col[i]
    return img

N = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
L, wb, Hc, Wc = cfg.get('L', 4.5), cfg.get('wb', 2.6), cfg.get('H', 1.3), cfg.get('W', 1.9)
PX = 90  # pixels per metre
def view(name, u, v, depth, W_m, H_m, ox, oy, guides):
    Wp, Hp = int(W_m * PX), int(H_m * PX)
    P = np.stack([(T[..., u[0]] * u[1] + ox) * PX, (oy - T[..., v[0]] * v[1]) * PX], -1)
    D = T[..., depth[0]] * depth[1]
    img = Image.fromarray(raster(P, D, N, Wp, Hp)); dr = ImageDraw.Draw(img)
    for g in guides(lambda a, b: ((a + ox) * PX, (oy - b) * PX)):
        dr.line(g[0], fill=g[1], width=1)
    dr.text((6, 4), name, fill=(20, 20, 20))
    return img

W_m = max(L, 4.0) + 1.6
# side view from +x: screen right = +z (front if facing +z)
side = view('SIDE (+z to the right)', (2, 1), (1, 1), (0, 1), W_m, 2.0, W_m / 2, 1.7,
            lambda p: [([p(-L / 2, 0), p(L / 2, 0)], (200, 0, 0)), ([p(-wb / 2, 0), p(-wb / 2, 0.9)], (0, 140, 0)),
                       ([p(wb / 2, 0), p(wb / 2, 0.9)], (0, 140, 0)), ([p(-L / 2, Hc), p(L / 2, Hc)], (0, 0, 200)),
                       ([p(-L / 2, 0), p(-L / 2, Hc)], (200, 0, 0)), ([p(L / 2, 0), p(L / 2, Hc)], (200, 0, 0))])
top = view('TOP (+z right, +x up)', (2, 1), (0, 1), (1, 1), W_m, 3.0, W_m / 2, 1.5,
           lambda p: [([p(-L / 2, -Wc / 2), p(L / 2, -Wc / 2)], (200, 0, 0)), ([p(-L / 2, Wc / 2), p(L / 2, Wc / 2)], (200, 0, 0)),
                      ([p(-wb / 2, -1.2), p(-wb / 2, 1.2)], (0, 140, 0)), ([p(wb / 2, -1.2), p(wb / 2, 1.2)], (0, 140, 0))])
front = view('FROM +z (front if nose is +z)', (0, -1), (1, 1), (2, 1), 3.0, 2.0, 1.5, 1.7,
             lambda p: [([p(-Wc / 2, 0), p(Wc / 2, 0)], (200, 0, 0)), ([p(-Wc / 2, Hc), p(Wc / 2, Hc)], (0, 0, 200))])
canvas = Image.new('RGB', (side.width + front.width, side.height + top.height), (255, 255, 255))
canvas.paste(side, (0, 0)); canvas.paste(top, (0, side.height)); canvas.paste(front, (side.width, 0))
ImageDraw.Draw(canvas).text((side.width + 6, side.height + 6),
    f"{os.path.basename(path)}\ns={s} rotY={cfg.get('rotY',0)}\nred: target L/W  green: axles\nblue: target height", fill=(0, 0, 0))
ext = T.reshape(-1, 3)
canvas.save(out)
print('fitted bbox', ext.min(0).round(3), ext.max(0).round(3), 'size', (ext.max(0) - ext.min(0)).round(3))
