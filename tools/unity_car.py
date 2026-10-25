"""Turn one of the game's cars (site/cars/<id>/model.json + geo*.png) into a GLB for Unity with separate wheels.
usage: unity_car.py <id> <out.glb>
- the CARS model transform (s, off, rotY) is baked in: car space, metres, +z = nose, +x = left, ground at y = 0
  (glTF's own convention, so glTFast's import gives Unity +z forward, +x right)
- the RIGS wheels: every triangle of a "spin" material wholly inside a wheel cylinder goes to its wheel node
  (Wheel_FL / Wheel_FR / Wheel_RL / Wheel_RR, origin at the hub, so the wheel turns about its own centre);
  everything else (calipers included) stays in the Body node
- materials, textures and samplers are kept; quantized attributes are written back as plain floats"""
import json, re, struct, sys, os, zlib
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glblib import acc  # noqa: E402

CID, OUT = sys.argv[1], sys.argv[2]
SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'site')
html = open(os.path.join(SITE, 'index.html'), encoding='utf-8').read()
J = json.load(open(os.path.join(SITE, 'cars', CID, 'model.json')))

def png_bytes(path, n):
    b = open(path, 'rb').read(); o = 8; W = 0; idat = []
    while o < len(b):
        ln = struct.unpack('>I', b[o:o + 4])[0]; t = b[o + 4:o + 8]
        if t == b'IHDR': W = struct.unpack('>I', b[o + 8:o + 12])[0]
        elif t == b'IDAT': idat.append(b[o + 8:o + 8 + ln])
        elif t == b'IEND': break
        o += 12 + ln
    raw = zlib.decompress(b''.join(idat)); out = bytearray()
    r = 0
    while len(out) < n: out += raw[r * (W + 1) + 1:r * (W + 1) + 1 + min(W, n - len(out))]; r += 1
    return bytes(out)
B = b''.join(png_bytes(os.path.join(SITE, 'cars', CID, p['file']), p['bytes']) for p in J['extras']['geoPng'])

# model transform and rig from index.html
m = re.search(r"\{id:'%s'.*?model:\{url:'[^']*',s:([\d.]+),off:\[([-\d.,]+)\](?:,rotY:([-\d.]+))?" % CID, html, re.S)
S = float(m.group(1)); OFF = np.array([float(v) for v in m.group(2).split(',')]); ROT = float(m.group(3) or 0)
rg = re.search(r"\b%s:\{hubs:(\[\[.*?\]\]),spin:(\[[^\]]*\])" % CID, html)
HUBS = json.loads(rg.group(1)); SPIN = set(json.loads(rg.group(2)))
print('model s', S, 'off', OFF, 'rotY', ROT, 'spin', len(SPIN))

def mat_of(node):
    t = np.array(node.get('translation', [0, 0, 0])); r = node.get('rotation', [0, 0, 0, 1]); s = np.array(node.get('scale', [1, 1, 1]))
    if 'matrix' in node: return np.array(node['matrix']).reshape(4, 4).T
    x, y, z, w = r
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4); M[:3, :3] = R * s; M[:3, 3] = t; return M
c, s_ = np.cos(ROT), np.sin(ROT)
G = np.eye(4); G[:3, :3] = np.array([[c, 0, s_], [0, 1, 0], [-s_, 0, c]]) * S; G[:3, 3] = OFF   # game: scale, rotate Y, then offset
groups = {}                                       # (group, material) -> list of (pos, nrm, uv, idx)
def visit(ni, PM):
    node = J['nodes'][ni]; M = PM @ mat_of(node)
    if 'mesh' in node:
        for pr in J['meshes'][node['mesh']]['primitives']:
            a = pr['attributes']; P = acc(J, B, a['POSITION']).astype(np.float64); N = acc(J, B, a['NORMAL']).astype(np.float64)
            UV = acc(J, B, a['TEXCOORD_0']).astype(np.float32) if 'TEXCOORD_0' in a else np.zeros((len(P), 2), np.float32)
            I = acc(J, B, pr['indices']).ravel().astype(np.int64)
            W = (G @ M); P = P @ W[:3, :3].T + W[:3, 3]
            Nn = N @ np.linalg.inv(W[:3, :3]).T; Nn /= np.maximum(np.linalg.norm(Nn, axis=1), 1e-9)[:, None]
            mi = pr.get('material', -1); mname = J['materials'][mi]['name'] if mi >= 0 else ''
            T = I.reshape(-1, 3); grp = np.full(len(T), -1)
            if mname in SPIN:
                for w, (hx, hy, hz, r, x0, x1, _) in enumerate(HUBS):
                    v = P[T]; inside = ((v[:, :, 0] >= x0 - 0.01) & (v[:, :, 0] <= x1 + 0.01) & (np.hypot(v[:, :, 1] - hy, v[:, :, 2] - hz) <= r + 0.01)).all(1)
                    grp[inside & (grp < 0)] = w
            for gi in np.unique(grp):
                tt = T[grp == gi]; used, inv = np.unique(tt, return_inverse=True)
                pos = P[used].copy()
                if gi >= 0: pos -= np.array(HUBS[gi][:3])
                groups.setdefault((int(gi), mi), []).append((pos.astype(np.float32), Nn[used].astype(np.float32), UV[used], inv.reshape(-1, 3).astype(np.uint32)))
    for ch in node.get('children', []): visit(ch, M)
for root in J['scenes'][J.get('scene', 0)]['nodes']: visit(root, np.eye(4))

# write the new GLB: images first (as they were), then the geometry
buf = bytearray(); views = []; accs = []
def add_view(data, target=None):
    while len(buf) % 4: buf.append(0)
    v = {'buffer': 0, 'byteOffset': len(buf), 'byteLength': len(data)}
    if target: v['target'] = target
    buf.extend(data); views.append(v); return len(views) - 1
images = []
for im in J.get('images', []):
    v = J['bufferViews'][im['bufferView']]; data = B[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']]
    images.append({'bufferView': add_view(data), 'mimeType': im['mimeType']})
def add_acc(arr, typ, comp, target, minmax=False):
    a = {'bufferView': add_view(arr.tobytes(), target), 'componentType': comp, 'count': len(arr), 'type': typ}
    if minmax: a['min'] = arr.min(0).tolist(); a['max'] = arr.max(0).tolist()
    accs.append(a); return len(accs) - 1
NAMES = {}
for w, h in enumerate(HUBS): NAMES[w] = 'Wheel_' + ('F' if h[2] > 0 else 'R') + ('L' if h[0] > 0 else 'R')
meshes = []; nodes = [{'name': CID, 'children': []}]
for g in sorted({k[0] for k in groups}):
    prims = []
    for (gg, mi), parts in sorted(groups.items()):
        if gg != g: continue
        pos = np.vstack([p[0] for p in parts]); nrm = np.vstack([p[1] for p in parts]); uv = np.vstack([p[2] for p in parts])
        idx = []; base = 0
        for p in parts: idx.append(p[3] + base); base += len(p[0])
        idx = np.vstack(idx).ravel()
        pa = {'attributes': {'POSITION': add_acc(pos, 'VEC3', 5126, 34962, True), 'NORMAL': add_acc(nrm, 'VEC3', 5126, 34962), 'TEXCOORD_0': add_acc(uv, 'VEC2', 5126, 34962)},
              'indices': add_acc(idx.astype(np.uint32), 'SCALAR', 5125, 34963), 'mode': 4}
        if mi >= 0: pa['material'] = mi
        prims.append(pa)
    meshes.append({'name': 'Body' if g < 0 else NAMES[g], 'primitives': prims})
    nd = {'name': 'Body' if g < 0 else NAMES[g], 'mesh': len(meshes) - 1}
    if g >= 0: nd['translation'] = HUBS[g][:3]
    nodes.append(nd); nodes[0]['children'].append(len(nodes) - 1)
out = {'asset': {'version': '2.0', 'generator': 'tsukimizaka unity_car.py'}, 'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': nodes, 'meshes': meshes,
       'materials': J['materials'], 'textures': J.get('textures', []), 'images': images, 'samplers': J.get('samplers', []),
       'accessors': accs, 'bufferViews': views, 'buffers': [{'byteLength': len(buf)}]}
js = json.dumps(out, separators=(',', ':')).encode()
while len(js) % 4: js += b' '
while len(buf) % 4: buf.append(0)
glb = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(buf)) + struct.pack('<I4s', len(js), b'JSON') + js + struct.pack('<I4s', len(buf), b'BIN\0') + bytes(buf)
open(OUT, 'wb').write(glb)
print('wrote', OUT, round(len(glb) / 1e6, 1), 'MB;', {n['name']: len(meshes[n['mesh']]['primitives']) for n in nodes[1:]})
print('hubs (car space, +x left):', {NAMES[w]: [round(v, 3) for v in h[:4]] for w, h in enumerate(HUBS)})
