"""Export a map-built course (tools/real_course.py) for Unity: a terrain heightmap and the road centre line.
usage: unity_export.py <id> <outdir> [size_m=12000] [res=2049]
Writes <outdir>/heights.bytes, far.bytes (the coarse horizon, 513 x 513 over the 250 m grid's area) (uint16 little-endian, res x res, row = Unity z from south to north, column = x from west
to east) and <outdir>/road.json (the road in Unity coordinates: x east, y up, z north, origin at the start line).
The ground under and beside the road is levelled to just under the road (a shelf out to hw+6 m, blended back to the
real ground by hw+22 m) so the coarse heightmap never pokes through the road mesh; on bridges it is left alone."""
import json, sys, os
import numpy as np
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial import cKDTree

ID, OUT = sys.argv[1], sys.argv[2]
SIZE = float(sys.argv[3]) if len(sys.argv) > 3 else 12000.0
RES = int(sys.argv[4]) if len(sys.argv) > 4 else 2049
m = np.load(f'work/{ID}/mesh.npz')
P, VX, VY, VB, VBR = m['P'], m['VX'], m['VY'], m['VB'], m['VBR']
st, fin, HW = int(m['start']), int(m['fin']), float(m['hw'])
x0, z0 = VX[st]                                  # the start line is the Unity origin
U = lambda x, z: (x - x0, -(z - z0))             # ours (x east, z south) -> Unity (x east, z north)
ux, uz = U(VX[:, 0], VX[:, 1])
cx, cz = (ux.min() + ux.max()) / 2, (uz.min() + uz.max()) / 2
X0, Z0 = round(cx - SIZE / 2), round(cz - SIZE / 2)
gx = X0 + np.arange(RES) * SIZE / (RES - 1); gz = Z0 + np.arange(RES) * SIZE / (RES - 1)
GX, GZ = np.meshgrid(gx, gz)                    # [row = z, col = x]
ox, oz = GX + x0, z0 - GZ                        # back to ours
print('interpolating', RES, 'x', RES, flush=True)
f = LinearNDInterpolator(P[:, :2], P[:, 2])
H = f(ox.ravel(), oz.ravel()).reshape(RES, RES)
H[np.isnan(H)] = -6.0
# level the ground along the road
tree = cKDTree(VX); d, k = tree.query(np.c_[ox.ravel(), oz.ravel()], distance_upper_bound=HW + 23)
d = d.reshape(RES, RES); k = k.reshape(RES, RES); near = np.isfinite(d)
kk = np.where(near, k, 0)
tx = np.gradient(VX[:, 0]); tz = np.gradient(VX[:, 1]); tl = np.hypot(tx, tz); nrx, nrz = tz / tl, -tx / tl   # the game's NR (left)
off = (ox - VX[kk, 0]) * nrx[kk] + (oz - VX[kk, 1]) * nrz[kk]
road = VY[kk] + VB[kk] * np.clip(off, -HW, HW) - 0.35
w = np.clip(1 - (d - (HW + 6)) / 16, 0, 1); w[~near] = 0; w[VBR[kk] & near] = 0
H = H * (1 - w) + road * w
hmin, hmax = float(np.floor(H.min())), float(np.ceil(H.max()))
q = np.round((H - hmin) / (hmax - hmin) * 65535).astype('<u2')
os.makedirs(OUT, exist_ok=True)
q.tofile(os.path.join(OUT, 'heights.bytes'))
# far land for the horizon (Mt Fuji ~37 km, Sagami Bay): a coarse 60 km terrain from the 250 m grid, 3 m lower, with a
# hole where the detailed terrain is (the game side: TurnpikeBuilder BuildFarTerrain)
import zlib, base64
from scipy.ndimage import map_coordinates
W2 = json.load(open(f'work/{ID}/raw2.json'))['wide']
wg = np.frombuffer(zlib.decompress(base64.b64decode(W2['b'])), dtype=np.uint8).astype(float).reshape(W2['nz'], W2['nx'])
wh = np.where(wg > 0, wg * W2['unit'], -25.0)
FR = 513                                       # exactly the area of the 250 m grid (~50 x 33 km): Fuji to Sagami Bay
fX0 = W2['x0'] - x0; fSX = (W2['nx'] - 1) * W2['step']
fSZ = (W2['nz'] - 1) * W2['step']; fZ0 = -(W2['z0'] + fSZ - z0)
fx = fX0 + np.arange(FR) * fSX / (FR - 1); fz = fZ0 + np.arange(FR) * fSZ / (FR - 1)
FX, FZ = np.meshgrid(fx, fz); ofx, ofz = FX + x0, z0 - FZ
FH = map_coordinates(wh, [(ofz - W2['z0']) / W2['step'], (ofx - W2['x0']) / W2['step']], order=1, mode='nearest') - 3.0
fmin, fmax = float(np.floor(FH.min())), float(np.ceil(FH.max()))
np.round((FH - fmin) / (fmax - fmin) * 65535).astype('<u2').tofile(os.path.join(OUT, 'far.bytes'))
print(f'far terrain {fSX:.0f} x {fSZ:.0f} m from ({fX0},{fZ0}), heights {fmin}..{fmax} m')
ry = VY; rx, rz = ux, uz
road_js = {'id': ID, 'x': [round(float(v), 2) for v in rx], 'y': [round(float(v), 2) for v in ry], 'z': [round(float(v), 2) for v in rz],
           # camber as the rise per metre towards the RIGHT of the direction of travel (the game stores it towards the left)
           'bankR': [round(float(-v), 4) for v in VB], 'bridge': [int(b) for b in VBR], 'hw': HW, 'start': st, 'fin': fin,
           'terrain': {'x0': X0, 'z0': Z0, 'size': SIZE, 'res': RES, 'hmin': hmin, 'hmax': hmax},
           'far': {'x0': float(fX0), 'z0': float(fZ0), 'sizeX': float(fSX), 'sizeZ': float(fSZ), 'res': FR, 'hmin': fmin, 'hmax': fmax},
           'credit': 'Road: (c) OpenStreetMap contributors (ODbL). Elevation: GSI Japan (国土地理院).'}
json.dump(road_js, open(os.path.join(OUT, 'road.json'), 'w'), separators=(',', ':'))
print(f'terrain {SIZE:.0f} m from ({X0},{Z0}), heights {hmin}..{hmax} m, road {len(rx)} points, start {st}, finish {fin}')
