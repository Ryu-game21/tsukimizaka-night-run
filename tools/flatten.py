"""Bake every node transform into the vertices and merge all primitives that share a material
(one mesh/node per material -> far fewer draw calls). Mirrored nodes get their winding flipped.
Every material is made double-sided (some rips have inconsistent winding).
usage: flatten.py in.glb out.glb [drop_mat,...]"""
import sys, os, json, struct
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, acc, node_matrix
src, dst = sys.argv[1], sys.argv[2]
drop = set(sys.argv[3].split(',')) if len(sys.argv) > 3 and sys.argv[3] else set()
J, B = load(src)
par = {c: i for i, n in enumerate(J['nodes']) for c in n.get('children', [])}
def world(i):
    ch = []
    while True:
        ch.append(i)
        if i in par: i = par[i]
        else: break
    M = np.eye(4)
    for k in ch[::-1]: M = M @ node_matrix(J['nodes'][k])
    return M
groups = {}
FIX = np.eye(4)
if os.environ.get('ZUP'):   # model is Z-up after its own transforms: rotate -90 deg about X  (x, y, z) -> (x, z, -y)
    FIX[:3, :3] = [[1, 0, 0], [0, 0, 1], [0, -1, 0]]
for i, n in enumerate(J['nodes']):
    if 'mesh' not in n: continue
    M = FIX @ world(i); R = M[:3, :3]; det = np.linalg.det(R)
    Nm = np.linalg.inv(R).T
    for p in J['meshes'][n['mesh']]['primitives']:
        if p.get('mode', 4) != 4: continue
        mi = p.get('material', -1)
        if mi >= 0 and J['materials'][mi].get('name') in drop: continue
        X = acc(J, B, p['attributes']['POSITION']).astype(np.float64)
        idx = (acc(J, B, p['indices']).ravel() if 'indices' in p else np.arange(len(X))).astype(np.int64).reshape(-1, 3)
        Xw = X @ R.T + M[:3, 3]
        Nw = None
        if 'NORMAL' in p['attributes']:
            Nn = acc(J, B, p['attributes']['NORMAL']).astype(np.float64) @ Nm.T
            Nw = Nn / np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-12)
        UV = acc(J, B, p['attributes']['TEXCOORD_0']).astype(np.float64) if 'TEXCOORD_0' in p['attributes'] else None
        if det < 0: idx = idx[:, [0, 2, 1]]
        key = (mi, UV is not None, Nw is not None)
        groups.setdefault(key, []).append((Xw, Nw, UV, idx))
out = bytearray(); views = []; accs = []
def add(arr, ctype, typ, target, mm=False):
    while len(out) % 4: out.append(0)
    views.append({'buffer': 0, 'byteOffset': len(out), 'byteLength': arr.nbytes, 'target': target}); out.extend(arr.tobytes())
    a = {'bufferView': len(views) - 1, 'componentType': ctype, 'count': len(arr), 'type': typ}
    if mm: a['min'] = arr.min(0).tolist(); a['max'] = arr.max(0).tolist()
    accs.append(a); return len(accs) - 1
meshes = []; nodes = []
for (mi, hasuv, hasn), parts in groups.items():
    off = 0; Xs, Ns, Us, Is = [], [], [], []
    for Xw, Nw, UV, idx in parts:
        Xs.append(Xw); Is.append(idx + off); off += len(Xw)
        if hasn: Ns.append(Nw)
        if hasuv: Us.append(UV)
    X = np.concatenate(Xs).astype(np.float32); I = np.concatenate(Is).astype(np.uint32)
    at = {'POSITION': add(X, 5126, 'VEC3', 34962, True)}
    if hasn: at['NORMAL'] = add(np.concatenate(Ns).astype(np.float32), 5126, 'VEC3', 34962)
    if hasuv: at['TEXCOORD_0'] = add(np.concatenate(Us).astype(np.float32), 5126, 'VEC2', 34962)
    prim = {'attributes': at, 'indices': add(I.ravel(), 5125, 'SCALAR', 34963)}
    if mi >= 0: prim['material'] = mi
    meshes.append({'primitives': [prim]}); nodes.append({'mesh': len(meshes) - 1})
for im in J.get('images', []):
    v = J['bufferViews'][im['bufferView']]; data = B[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']]
    while len(out) % 4: out.append(0)
    views.append({'buffer': 0, 'byteOffset': len(out), 'byteLength': len(data)}); out.extend(data); im['bufferView'] = len(views) - 1
for m in J['materials']: m['doubleSided'] = True
J['nodes'] = nodes; J['meshes'] = meshes; J['scenes'] = [{'nodes': list(range(len(nodes)))}]; J['scene'] = 0
J['bufferViews'] = views; J['accessors'] = accs
for k in ('skins', 'animations', 'cameras'): J.pop(k, None)
while len(out) % 4: out.append(0)
J['buffers'] = [{'byteLength': len(out)}]
js = json.dumps(J, separators=(',', ':')).encode()
while len(js) % 4: js += b' '
open(dst, 'wb').write(struct.pack('<III', 0x46546C67, 2, 28 + len(js) + len(out)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(out), 0x004E4942) + bytes(out))
print(f'{src}: {sum(1 for n in J["nodes"])} merged meshes, {sum(len(p[3]) for g in groups.values() for p in g)} tris')
