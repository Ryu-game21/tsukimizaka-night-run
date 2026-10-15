"""Cut a circuit model down to a corridor around the racing line and thin out vegetation.
Rules (distance = horizontal distance from the triangle / tree to the track centre line):
  road & kerbs: always kept
  vegetation:   whole trees (connected pieces) kept only within VEG_KEEP m, and only a fraction of them
  dropped:      parked vehicles, cones, flag poles, marshal posts (tiny props, lots of triangles)
  everything else: kept within CORRIDOR m
Output is a GLB with compacted float attributes (optimize2.py then quantises/shrinks it).
usage: trim_track.py in.glb course.json out.glb"""
import sys, os, json, struct
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, acc, node_matrix

src, course, dst = sys.argv[1], sys.argv[2], sys.argv[3]
CFG = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
SC = CFG.get('scale', 1.0)
J, B = load(src)
C = np.array(json.load(open(course))['pts'])
dense = []
for a, b in zip(C, np.roll(C, -1, 0)):
    for t in np.linspace(0, 1, 4, endpoint=False): dense.append(a + (b - a) * t)
tree = cKDTree(np.array(dense)[:, [0, 2]])

ROAD = {'asph.001', 'asph_new.001', 'kerb_new.001', 'CURB_B.001', 'line.001', 'groove1.001', 'groove2.001', 'groove3.001',
        'groove_custom.001', 'carpet.001', 'carpet-full.001', 'carpet-blue.001', 'doted_line.001', 'asph_patch_joint.001', 'asph-grv.001'}
VEG = {'trees1_2022.001', 'trees2_2022.001', 'treesline.001', 'bushesB.001', 'hedge.001', 'ivy-wall.001'}
DROP = {'Vehicles.001', 'Cone.001', 'digitalflag_pole.001', 'marshal-post.001', 'Parking.001', 'stones_detail1.001'}
GROUND = {'GRASS.001', 'grass-ext-shad.001', 'grass-side1.001', 'grass-side1B.001', 'grass-side2.001', 'grass-side4.001',
          'sand.001', 'sand_new.001', 'road-ext-tile.001', 'sbancamento_D.001', 'construction_dirt.001', 'water.001'}
CORRIDOR, GROUND_KEEP, VEG_KEEP, VEG_FRACTION = 70.0, 110.0, 55.0, 0.35
if CFG:
    ROAD, VEG, DROP, GROUND = (set(CFG.get(k, [])) for k in ('road', 'veg', 'drop', 'ground'))
    CORRIDOR = CFG.get('corridor', CORRIDOR); GROUND_KEEP = CFG.get('ground_keep', GROUND_KEEP)
    VEG_KEEP = CFG.get('veg_keep', VEG_KEEP); VEG_FRACTION = CFG.get('veg_fraction', VEG_FRACTION)
rng = np.random.default_rng(7)

def world(node_idx_chain):
    M = np.eye(4)
    for i in node_idx_chain: M = M @ node_matrix(J['nodes'][i])
    return M
parent = {}
for i, n in enumerate(J['nodes']):
    for c in n.get('children', []): parent[c] = i
def chain(i):
    out = [i]
    while out[-1] in parent: out.append(parent[out[-1]])
    return out[::-1]

def components(tri):
    """connected pieces of a triangle list (shared vertex indices)"""
    p = np.arange(tri.max() + 1)
    def find(x):
        while p[x] != x:
            p[x] = p[p[x]]; x = p[x]
        return x
    for a, b, c in tri:
        ra, rb, rc = find(a), find(b), find(c)
        p[rb] = ra; p[find(rc)] = ra
    roots = np.array([find(a) for a in tri[:, 0]])
    return roots

out = bytearray(); views = []; accs = []
def add(arr, ctype, typ, target, minmax=False):
    while len(out) % 4: out.append(0)
    views.append({'buffer': 0, 'byteOffset': len(out), 'byteLength': arr.nbytes, 'target': target})
    out.extend(arr.tobytes())
    a = {'bufferView': len(views) - 1, 'componentType': ctype, 'count': len(arr), 'type': typ}
    if minmax: a['min'] = arr.min(0).tolist(); a['max'] = arr.max(0).tolist()
    accs.append(a); return len(accs) - 1

stats = {}
cleared = {}
_cd = json.load(open(course)); _cp = np.array(_cd['pts'])
CBK = np.array(_cd.get('bank', [0] * len(_cp)))
_T = np.roll(_cp, -1, 0) - np.roll(_cp, 1, 0); _T = _T[:, [0, 2]] / np.linalg.norm(_T[:, [0, 2]], axis=1, keepdims=True)
CNR = np.c_[_T[:, 1], -_T[:, 0]]
opaque_copy = {}; patches = [0]
# coverage raster of the real road materials (patches are only used where the road itself has a gap)
from PIL import Image as _Im, ImageDraw as _Dr
_rx0, _rz0 = _cp[:, 0].min() - 60, _cp[:, 2].min() - 60
_RW, _RH = int((_cp[:, 0].max() + 60 - _rx0) / 0.5) + 1, int((_cp[:, 2].max() + 60 - _rz0) / 0.5) + 1
_rim = _Im.new('L', (_RW, _RH), 0); _rd = _Dr.Draw(_rim)
for _ni, _n in enumerate(J['nodes']):
    if 'mesh' not in _n: continue
    _M = world(chain(_ni))
    for _p in J['meshes'][_n['mesh']]['primitives']:
        if 'material' not in _p or J['materials'][_p['material']].get('name', '') not in ROAD: continue
        _X = acc(J, B, _p['attributes']['POSITION']).astype(np.float64)
        _W = (_M @ np.c_[_X, np.ones(len(_X))].T).T[:, :3] * SC
        _idx = acc(J, B, _p['indices']).ravel().reshape(-1, 3)
        for _t in _W[_idx]: _rd.polygon([((v[0] - _rx0) / 0.5, (v[2] - _rz0) / 0.5) for v in _t], fill=1)
_rcov = np.asarray(_rim) > 0
def road_covered(xz):
    j = ((xz[:, 0] - _rx0) / 0.5).astype(int); i = ((xz[:, 1] - _rz0) / 0.5).astype(int)
    ok = (i >= 0) & (i < _RH) & (j >= 0) & (j < _RW); out = np.zeros(len(xz), bool); out[ok] = _rcov[i[ok], j[ok]]; return out
ROAD_MAT_IDX = next(i for i, m in enumerate(J['materials']) if m.get('name') == CFG.get('patch_mat', sorted(ROAD)[0]))
ctree = cKDTree(_cp[:, [0, 2]]); CY = _cp[:, 1]; CHW = np.array(_cd['hw'])
for ni, n in enumerate(J['nodes']):
    if 'mesh' not in n: continue
    M = world(chain(ni))
    mesh = J['meshes'][n['mesh']]
    newp = []
    for p in mesh['primitives']:
        mat = J['materials'][p['material']].get('name', '') if 'material' in p else ''
        if mat in DROP or p.get('mode', 4) != 4: continue
        X = acc(J, B, p['attributes']['POSITION']).astype(np.float64)
        idx = (acc(J, B, p['indices']).ravel() if 'indices' in p else np.arange(len(X))).astype(np.int64)
        tri = idx.reshape(-1, 3)
        Wp = (M @ np.c_[X, np.ones(len(X))].T).T[:, :3] * SC
        cen = Wp[tri].mean(1)
        d, _ = tree.query(cen[:, [0, 2]])
        if mat in ROAD: keep = np.ones(len(tri), bool)
        elif mat in VEG:
            roots = components(tri)
            ur, inv = np.unique(roots, return_inverse=True)
            cd = np.zeros(len(ur)); np.maximum.at(cd, inv, 0); cd = np.array([d[inv == k].mean() for k in range(len(ur))]) if len(ur) < 4000 else None
            if cd is None:  # many pieces: average distance per piece via bincount
                cd = np.bincount(inv, weights=d) / np.bincount(inv)
            lucky = rng.random(len(ur)) < VEG_FRACTION
            keep_piece = (cd < VEG_KEEP) & lucky
            keep = keep_piece[inv]
            # merged atlases sometimes carry patches of the racing surface: never thin those, and draw them opaque
            Wt = Wp[tri]; nrm = np.cross(Wt[:, 1] - Wt[:, 0], Wt[:, 2] - Wt[:, 0])
            flat = np.abs(nrm[:, 1]) > 0.9 * (np.linalg.norm(nrm, axis=1) + 1e-12)
            dd2, ii2 = ctree.query(cen[:, [0, 2]])
            roadpatch = flat & (dd2 < CHW[ii2] + 2.0) & (np.abs(cen[:, 1] - CY[ii2]) < 0.6) & ~road_covered(cen[:, [0, 2]])
            keep |= roadpatch
            patch_mask = roadpatch
        elif mat in GROUND: keep = d < GROUND_KEEP
        else: keep = d < CORRIDOR
        if CFG.get('clear') and mat not in ROAD:
            # keep the driving corridor clear: nothing may stand on the racing surface between 0.25 m and 3.5 m up
            dd_, ii_ = ctree.query(cen[:, [0, 2]])
            lat_ = (cen[:, 0] - _cp[ii_, 0]) * CNR[ii_, 0] + (cen[:, 2] - _cp[ii_, 2]) * CNR[ii_, 1]
            base_ = CY[ii_] + CBK[ii_] * lat_
            ylo = Wp[tri][:, :, 1].min(1) - base_; yhi = Wp[tri][:, :, 1].max(1) - base_
            block = (dd_ < CHW[ii_] * 0.5) & (yhi > 0.6) & (ylo < 2.2)
            cleared[mat] = cleared.get(mat, 0) + int((keep & block).sum())
            keep &= ~block
        stats[mat] = (stats.get(mat, (0, 0))[0] + len(tri), stats.get(mat, (0, 0))[1] + int(keep.sum()))
        if not keep.any(): continue
        pm = patch_mask[keep] if mat in VEG else np.zeros(int(keep.sum()), bool)
        tri_all = tri[keep]
        for tri, is_patch in ((tri_all[~pm], False), (tri_all[pm], True)):
          if not len(tri): continue
          used, remap = np.unique(tri, return_inverse=True)
          tri2 = remap.reshape(-1, 3).astype(np.uint32)
          at = {}
          for k, ai in p['attributes'].items():
              if k not in ('POSITION', 'NORMAL', 'TEXCOORD_0'): continue
              v = acc(J, B, ai).astype(np.float32)[used]
              if k == 'TEXCOORD_0' and is_patch:  # planar asphalt mapping (atlas UVs point at a transparent texel)
                  v = (Wp[used][:, [0, 2]] / 6.0).astype(np.float32)
              at[k] = add(v, 5126, {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3'}[v.shape[1]], 34962, minmax=(k == 'POSITION'))
          np_ = {'attributes': at, 'indices': add(tri2.ravel(), 5125, 'SCALAR', 34963)}
          if 'material' in p: np_['material'] = p['material']
          if is_patch:
              np_['material'] = ROAD_MAT_IDX
              if 'TEXCOORD_0' not in at:
                  at['TEXCOORD_0'] = add((Wp[used][:, [0, 2]] / 6.0).astype(np.float32), 5126, 'VEC2', 34962)
              patches[0] += len(tri)
          newp.append(np_)
    mesh['primitives'] = newp
    if not newp: n.pop('mesh')

# images: copy through unchanged (optimize2 resizes them)
for im in J.get('images', []):
    v = J['bufferViews'][im['bufferView']]
    data = B[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']]
    while len(out) % 4: out.append(0)
    views.append({'buffer': 0, 'byteOffset': len(out), 'byteLength': len(data)}); out.extend(data)
    im['bufferView'] = len(views) - 1
J['bufferViews'] = views; J['accessors'] = accs
if SC != 1.0:  # bake the uniform scale into a new root node
    sc = J['scenes'][J.get('scene', 0)]
    J['nodes'].append({'name': 'scale_root', 'scale': [SC, SC, SC], 'children': sc['nodes']})
    sc['nodes'] = [len(J['nodes']) - 1]
while len(out) % 4: out.append(0)
J['buffers'] = [{'byteLength': len(out)}]
js = json.dumps(J, separators=(',', ':')).encode()
while len(js) % 4: js += b' '
open(dst, 'wb').write(struct.pack('<III', 0x46546C67, 2, 28 + len(js) + len(out)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(out), 0x004E4942) + bytes(out))
tot0 = sum(v[0] for v in stats.values()); tot1 = sum(v[1] for v in stats.values())
print('road patches moved out of blended atlases:', patches[0])
print('cleared from the racing surface:', {k: v for k, v in cleared.items() if v})
print(f'triangles {tot0} -> {tot1}  ({len(out)/1e6:.1f}MB)')
for m, (a, b) in sorted(stats.items(), key=lambda kv: -kv[1][1])[:22]: print(f'  {m:26s} {a:7d} -> {b:7d}')
