"""Build a point-to-point course and its terrain from real map data (OpenStreetMap road + GSI elevation).

Input (work/<id>/, written from the browser with tools/osm_fetch.js, see its header):
  raw.json   nodes (local x,z in 0.1 m, origin = the first node, +x east, +z south, ",1" = bridge segment),
             ed (road elevation every 10 m along the nodes, 0.1 m deltas, int8 base64), xs (cross-sections every 40 m,
             offsets -400..400 step 25, relative to the road elevation in 4 m units)
  raw2.json  wide (250 m grid of the whole area in 16 m units, 0 = sea, deflate+base64),
             fine (cross-sections every 20 m at +-7..50 m, relative in 0.5 m units, deflate+base64)
Output:
  work/<id>/course.json          pts (x,y,z every 4 m incl. the run-off after the finish), hw, bank, fin (index of the finish)
  site/tracks/<id>/terrain.json  + terrain0.png: Float32 positions, Uint32 triangle indices, Float32 trees (x,y,z,s),
                                 Uint8 RGBA vertex colours (the game: terrainLoad)
usage: real_course.py <id> [hw=5.5]"""
import json, zlib, base64, math, struct, sys, os
import numpy as np
from scipy.spatial import Delaunay, cKDTree
from scipy.ndimage import gaussian_filter1d

ID = sys.argv[1]; HW = float(sys.argv[2]) if len(sys.argv) > 2 else 5.5
D = f'work/{ID}/'; OUT = f'site/tracks/{ID}/'
raw = json.load(open(D + 'raw.json')); raw2 = json.load(open(D + 'raw2.json'))
RUNOFF, RUNIN = 260.0, 300.0
rng = np.random.default_rng(7)

# ---- the road as OSM gave it, and the 10 m samples the browser measured the elevation on
nodes = [tuple(map(int, s.split(','))) for s in raw['nodes'].split(';')]
NX = np.array([[n[0] / 10, n[1] / 10] for n in nodes]); NB = np.array([len(n) > 2 for n in nodes])
seg = np.hypot(*np.diff(NX, axis=0).T); cum = np.concatenate([[0], np.cumsum(seg)])
def along(s):
    s = np.clip(s, 0, cum[-1]); k = np.clip(np.searchsorted(cum, s, side='right') - 1, 0, len(seg) - 1)
    t = (s - cum[k]) / np.maximum(seg[k], 1e-9); return NX[k] + (NX[k + 1] - NX[k]) * t[:, None], k
ed = np.frombuffer(base64.b64decode(raw['ed']), dtype=np.int8).astype(float)
E10 = (raw['e0'] + np.cumsum(ed)) / 10; S10, _ = along(np.arange(len(E10)) * 10.0)

# ---- centre line every 4 m, lightly smoothed (OSM bends at its nodes)
L = cum[-1]; s4 = np.arange(0, L, 4.0); XY, kseg = along(s4)
XY = np.stack([gaussian_filter1d(XY[:, 0], 1.5, mode='nearest'), gaussian_filter1d(XY[:, 1], 1.5, mode='nearest')], 1)
Y = np.interp(s4, np.arange(len(E10)) * 10.0, E10)
# bridges: the ground model is the valley floor under them -> a straight line between the abutments
br = NB[kseg + 1]; spans = []; i = 0
while i < len(br):
    if br[i]:
        j = i
        while j < len(br) and br[j]: j += 1
        spans.append((i, j)); i = j
    else: i += 1
for a, b in spans:
    a2, b2 = max(0, a - 5), min(len(Y) - 1, b + 5)
    Y[a2:b2 + 1] = np.linspace(Y[a2], Y[b2], b2 - a2 + 1)
Y = gaussian_filter1d(Y, 5, mode='nearest')
# run-off past the finish: straight on, flat
u = XY[-1] - XY[-10]; u /= np.linalg.norm(u); n_off = int(RUNOFF / 4)
XY = np.vstack([XY, XY[-1] + u[None] * (np.arange(1, n_off + 1) * 4.0)[:, None]]); Y = np.concatenate([Y, np.full(n_off, Y[-1])])
FIN = len(s4) - 1
isbr = np.zeros(len(Y), bool)
for a, b in spans: isbr[a:b] = True
# camber from the curvature, low on the inside, at most 7%
t = np.gradient(XY, axis=0); t /= np.linalg.norm(t, axis=1)[:, None]; dt = np.gradient(t, axis=0) / 4.0
k = t[:, 0] * dt[:, 1] - t[:, 1] * dt[:, 0]
NR = np.stack([t[:, 1], -t[:, 0]], 1)                      # the game's normal (t.z, -t.x)
inside = dt[:, 0] * NR[:, 0] + dt[:, 1] * NR[:, 1]
bank = -np.sign(inside) * np.minimum(0.07, np.abs(k) * 3.0); bank = gaussian_filter1d(bank, 4, mode='nearest')
bank[-n_off:] = 0
grade = np.diff(Y) / 4.0
print(f'route {L:.0f} m, climb {Y[0]:.0f} -> {Y[FIN]:.0f} m, max grade {grade.max()*100:.1f}% min {grade.min()*100:.1f}%, bridges {len(spans)}, '
      f'min radius {1/np.abs(k[:FIN]).max():.0f} m')

# run-in before the start (the game adds the same straight line behind the start, 300 m)
u0 = XY[10] - XY[0]; g0 = (Y[10] - Y[0]) / np.linalg.norm(u0); u0 /= np.linalg.norm(u0)
din = np.arange(int(RUNIN / 4), 0, -1) * 4.0
RX = XY[0] - u0[None] * din[:, None]; RY = Y[0] - g0 * din
VX = np.vstack([RX, XY]); VY = np.concatenate([RY, Y]); VB = np.concatenate([np.zeros(len(RY)), bank])
VBR = np.concatenate([np.zeros(len(RY), bool), isbr])
tv = np.gradient(VX, axis=0); tv /= np.linalg.norm(tv, axis=1)[:, None]; VN = np.stack([tv[:, 1], -tv[:, 0]], 1)
road = cKDTree(VX)

# ---- height samples from the map
P = []                                  # x, z, y
def sec_normals(idx):
    a = S10[np.maximum(0, idx - 2)]; b = S10[np.minimum(len(S10) - 1, idx + 2)]; d = b - a; d /= np.linalg.norm(d, axis=1)[:, None]
    return np.stack([-d[:, 1], d[:, 0]], 1)
fine = np.frombuffer(zlib.decompress(base64.b64decode(raw2['fine']['b'])), dtype=np.int8).astype(float)
offs = raw2['fine']['offs']; fo = np.array([-o for o in offs[::-1]] + offs, float)
fi = np.arange(raw2['fine']['n']) * 2; fn = sec_normals(fi); fine = fine.reshape(len(fi), len(fo))
for r, i in enumerate(fi):
    for c, o in enumerate(fo):
        q = S10[i] + fn[r] * o; P.append((q[0], q[1], E10[i] + fine[r, c] * 0.5, 1))
xs = np.frombuffer(base64.b64decode(raw['xs']), dtype=np.int8).astype(float)
o0, ost, on = raw['off']; xo = o0 + ost * np.arange(on); xi = np.arange(raw['nXs']) * 4; xn = sec_normals(xi); xs = xs.reshape(len(xi), on)
for r, i in enumerate(xi):
    for c, o in enumerate(xo):
        if abs(o) < 60: continue
        q = S10[i] + xn[r] * o; P.append((q[0], q[1], E10[i] + xs[r, c] * 4, 2))
W = raw2['wide']; wg = np.frombuffer(zlib.decompress(base64.b64decode(W['b'])), dtype=np.uint8).astype(float).reshape(W['nz'], W['nx'])
for j in range(W['nz']):
    for i in range(W['nx']):
        v = wg[j, i]; P.append((W['x0'] + i * W['step'], W['z0'] + j * W['step'], v * W['unit'] if v else -6.0, 3))
P = np.array(P)
d, _ = road.query(P[:, :2])
keep = ((P[:, 3] == 1) & (d > HW + 3.6)) | ((P[:, 3] == 2) & (d > 45)) | ((P[:, 3] == 3) & (d > 420))
P = P[keep]
# thin the 40 m sections where they overlap each other (hairpins): one sample per 14 m
mid = P[:, 3] == 2; kept = []
if mid.any():
    Q = P[mid]; tree = cKDTree(Q[:, :2]); taken = np.zeros(len(Q), bool); ok = np.zeros(len(Q), bool)
    for q in range(len(Q)):
        if taken[q]: continue
        ok[q] = True
        for z in tree.query_ball_point(Q[q, :2], 14): taken[z] = True
    P = np.vstack([P[~mid], Q[ok]])
# the corridor: flat shoulders just under the road out past the guard rail (none on bridges: the valley shows)
C = []
for q in range(0, len(VX)):
    if VBR[q]: continue
    for o in (HW + 0.6, HW + 2.9):
        for s in (1, -1):
            off = s * o; x, z = VX[q] + VN[q] * off
            # never on another stretch of road (hairpins): only where this sample is the nearest road
            dd, kk = road.query((x, z))
            if abs(kk - q) > 12 and dd < HW + 3: continue
            C.append((x, z, VY[q] + VB[q] * off - (0.9 if o < HW + 1 else 0.35), 0))
P = np.vstack([np.array(C), P])
print('vertices', len(P), {k: int((P[:, 3] == k).sum()) for k in range(4)})

tri = Delaunay(P[:, :2]); T = tri.simplices.astype(np.uint32).copy()
# wind every triangle so its normal points up in the game (x, y up, z): (b-a)x(c-a) has y = dz1*dx2 - dx1*dz2 > 0
e1 = P[T[:, 1], :2] - P[T[:, 0], :2]; e2 = P[T[:, 2], :2] - P[T[:, 0], :2]
flip = (e1[:, 1] * e2[:, 0] - e1[:, 0] * e2[:, 1]) < 0; T[flip] = T[flip][:, [0, 2, 1]]
# check: the ground must stay under the road everywhere on the band
bad = 0; probe = []
for q in range(0, len(VX), 2):
    if VBR[q]: continue
    for off in np.linspace(-HW, HW, 7):
        x, z = VX[q] + VN[q] * off; probe.append((x, z, VY[q] + VB[q] * off))
probe = np.array(probe); si = tri.find_simplex(probe[:, :2]); okp = si >= 0
Tm = tri.transform[si[okp], :2]; r = probe[okp, :2] - tri.transform[si[okp], 2]
bc = np.einsum('ijk,ik->ij', Tm, r); bc = np.c_[bc, 1 - bc.sum(1)]
hz = (P[T[si[okp]], 2] * bc).sum(1); over = hz - probe[okp, 2]
print(f'road probes {okp.sum()}, ground above road: {(over > 0.02).sum()} (max {over.max():.2f} m)')
for idx in np.where(over > 0.02)[0][:20]:
    pr = probe[okp][idx]; dd, kk = road.query(pr[:2]); print('  above at', np.round(pr, 1), 'sample', kk, 'over', round(float(over[idx]), 2), 'tri types', P[T[si[okp][idx]], 3])
fixv = set()
for idx in np.where(over > 0.02)[0]:
    for v in T[si[okp][idx]]:
        if P[v, 3] != 0: fixv.add(int(v))
# lower any offending map vertex to the road level (rare: a bank sample right at the road)
for v in fixv:
    dd, kk = road.query(P[v, :2]); P[v, 2] = min(P[v, 2], VY[kk] - 0.5)
if fixv: print('lowered', len(fixv), 'vertices')
# for other engines (tools/unity_export.py): the ground samples in real coordinates and the drawn road
np.savez(D + 'mesh.npz', P=P, VX=VX, VY=VY, VB=VB, VBR=VBR, start=len(RY), fin=len(RY) + FIN, hw=HW)

# the ground just beside the road (for the game's roadside scenery: bushes, trees, grass, signs): height above (+) or below
# the road plane at fixed offsets both sides, every course point (route + run-off), 0.25 m units, int8
SOFF = [8.5, 9.5, 10.5, 12, 14, 16.5, 19.5, 23, 27]
q_pts = []
for qi in range(len(XY)):
    t2 = (XY[min(qi + 1, len(XY) - 1)] - XY[max(qi - 1, 0)]); t2 /= np.linalg.norm(t2); nl = np.array([t2[1], -t2[0]])   # NR (left)
    for sd in (1, -1):
        for o in SOFF: q_pts.append(XY[qi] + nl * sd * o)
q_pts = np.array(q_pts); si2 = tri.find_simplex(q_pts); okq = si2 >= 0
r2 = q_pts[okq] - tri.transform[si2[okq], 2]; bc2 = np.einsum('ijk,ik->ij', tri.transform[si2[okq], :2], r2); bc2 = np.c_[bc2, 1 - bc2.sum(1)]
gh = np.full(len(q_pts), np.nan); gh[okq] = (P[T[si2[okq]], 2] * bc2).sum(1)
gh = gh.reshape(len(XY), 2, len(SOFF))
ref = Y[:, None, None] + bank[:, None, None] * (np.array([1, -1])[None, :, None] * np.array(SOFF)[None, None, :])
side = np.clip(np.round(np.nan_to_num(gh - ref, nan=0) * 4), -127, 127).astype(np.int8)
side_b64 = base64.b64encode(side.tobytes()).decode()
print('roadside ground: median |dy|', round(float(np.median(np.abs(gh - ref)[np.isfinite(gh)])), 2), 'm')
# trees: forest in a band beside the road, on the ground
trees = []
interp_simplex = tri
cand = np.c_[rng.uniform(VX[:, 0].min() - 600, VX[:, 0].max() + 600, 260000), rng.uniform(VX[:, 1].min() - 600, VX[:, 1].max() + 600, 260000)]
dd, kk = road.query(cand)
# candidates out to 450 m (thinning with distance); the game keeps the ones on forest in the aerial photo, or every 3rd without it
w = (dd > HW + 4.5) & (dd < 450) & (rng.random(len(cand)) < np.clip(1.3 - dd / 450, 0, 1))
cand = cand[w]
si = tri.find_simplex(cand); cand = cand[si >= 0]; si = si[si >= 0]
r = cand - tri.transform[si, 2]; bc = np.einsum('ijk,ik->ij', tri.transform[si, :2], r); bc = np.c_[bc, 1 - bc.sum(1)]
hy = (P[T[si], 2] * bc).sum(1)
for (x, z), y in zip(cand, hy):
    if y < 2: continue
    trees.append((x, y, z, rng.uniform(0.75, 1.6)))
trees = np.array(trees[:24000], np.float32)   # random order: any prefix is an even sample
print('trees', len(trees))

# far land (beyond 7 km of the middle of the road) drawn closer and lower so it stays inside the camera range
cx, cz = (VX[:, 0].min() + VX[:, 0].max()) / 2, (VX[:, 1].min() + VX[:, 1].max()) / 2
R0, KF, YV = 7000.0, 0.11, 1000.0   # heights above YV shrink with the distance (Fuji seen from the summit ~ its real angle)
dx, dz = P[:, 0] - cx, P[:, 1] - cz; rr = np.hypot(dx, dz); f = np.where(rr > R0, (R0 + (rr - R0) * KF) / np.maximum(rr, 1), 1.0)
pos = np.c_[cx + dx * f, np.where(P[:, 2] > YV, YV + (P[:, 2] - YV) * f, P[:, 2]), cz + dz * f].astype(np.float32)
pos[P[:, 2] < -1, 1] = -6
print('far radius', round(float((rr * f).max())), 'm')

# colours by the real height and slope: forest, cut slopes / rock, the shoulders, beach, and Fuji's dark lava and snow
fnrm = np.cross(P[T[:, 1], :3][:, [0, 2, 1]] - P[T[:, 0], :3][:, [0, 2, 1]], P[T[:, 2], :3][:, [0, 2, 1]] - P[T[:, 0], :3][:, [0, 2, 1]])
vn = np.zeros((len(P), 3))
for q in range(3): np.add.at(vn, T[:, q], fnrm)
vn /= np.maximum(np.linalg.norm(vn, axis=1), 1e-9)[:, None]; up = np.abs(vn[:, 1])
hh = P[:, 2]; nz = rng.random(len(P))
col = np.zeros((len(P), 3))
forest = np.array([0.17, 0.27, 0.15]); grass = np.array([0.33, 0.40, 0.22]); rock = np.array([0.42, 0.39, 0.33])
col[:] = forest * (0.8 + 0.4 * nz[:, None])
col[(hh > 1000) & (hh < 2400)] = grass * (0.85 + 0.3 * nz[(hh > 1000) & (hh < 2400), None])
st = up < 0.72; col[st] = rock * (0.8 + 0.3 * nz[st, None])
col[hh > 2400] = np.array([0.30, 0.26, 0.25]); col[hh > 3250] = np.array([0.88, 0.9, 0.93])
col[P[:, 3] == 0] = np.array([0.36, 0.34, 0.30]); col[hh < 3] = np.array([0.55, 0.50, 0.38])
cols = np.zeros((len(P), 4), np.uint8); cols[:, :3] = np.clip(col * 255, 0, 255)
os.makedirs(OUT, exist_ok=True)
blob = pos.tobytes() + T.ravel().tobytes() + trees.tobytes() + cols.tobytes()
Wd = 4096; Hh = (len(blob) + Wd - 1) // Wd; pad = blob + bytes(Hh * Wd - len(blob))
rows = b''.join(b'\x00' + pad[r * Wd:(r + 1) * Wd] for r in range(Hh))
def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', Wd, Hh, 8, 0, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b'')
open(OUT + 'terrain0.png', 'wb').write(png)
json.dump({'file': 'terrain0.png', 'bytes': len(blob), 'nv': len(pos), 'ni': int(T.size), 'nt': len(trees), 'sea': 0, 'sideOffs': SOFF, 'side': side_b64,
           'src': 'OpenStreetMap contributors (ODbL); GSI elevation tiles'}, open(OUT + 'terrain.json', 'w'))
print('terrain', round(len(png) / 1e6, 2), 'MB png,', len(pos), 'verts', len(T), 'tris')
r1 = lambda a, n=1: [round(float(v), n) for v in a]
pts = []
for q in range(len(XY)): pts += [round(float(XY[q, 0]), 1), round(float(Y[q]), 1), round(float(XY[q, 1]), 1)]
json.dump({'pts': pts, 'hw': [HW] * len(XY), 'bank': r1(bank, 3), 'fin': FIN, 'runin': RUNIN}, open(D + 'course.json', 'w'), separators=(',', ':'))
print('course points', len(XY), 'fin', FIN)
