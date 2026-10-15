"""Find wheel contact points and propose the game fit transform.
usage: fit_car.py model.glb '{"drop":[...],"wb":2.665,"L":4.6,"nose":"+z"|"-z"}'
Prints axle positions, ground height, scale from wheelbase, and resulting length/height/width."""
import sys, json, os
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, triangles

path, cfg = sys.argv[1], json.loads(sys.argv[2])
J, B = load(path)
drop = [d.lower() for d in cfg.get('drop', [])]
P = np.concatenate([t.reshape(-1, 3) for m, t, nn in triangles(J, B)
                    if not any(d == m.lower() or d == nn.lower() for d in drop)])
lo, hi = P.min(0), P.max(0)
h = hi[1] - lo[1]
# contact patches: the lowest 2.5% of the height band
g = P[P[:, 1] < lo[1] + 0.025 * h]
zc = (lo[2] + hi[2]) / 2
front, rear = g[g[:, 2] > zc], g[g[:, 2] <= zc]
zf, zr = np.median(front[:, 2]), np.median(rear[:, 2])
wb_model = zf - zr
xc = (lo[0] + hi[0]) / 2
# wheel radius estimate from side silhouette of the low band near each axle
s = cfg['wb'] / wb_model
print(f'ground y={lo[1]:.4f}  axle z: +side {zf:.4f}  -side {zr:.4f}  model wb={wb_model:.4f}  x-centre={xc:.4f}')
print(f'scale from wheelbase s={s:.5f}')
print(f'-> length {(hi[2]-lo[2])*s:.3f} (target {cfg.get("L")})  width {(hi[0]-lo[0])*s:.3f}  height {h*s:.3f} (target {cfg.get("H")})')
mid = (zf + zr) / 2
print(f'overhangs: +z {(hi[2]-zf)*s:.3f}  -z {(zr-lo[2])*s:.3f}')
off = [-xc, -lo[1], -mid]
print('FIT', json.dumps({'s': round(s, 5), 'off': [round(v, 4) for v in off]}))
