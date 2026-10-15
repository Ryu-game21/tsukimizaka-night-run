"""GLB -> smaller GLB for the game.
 - drops primitives by material name / meshes by node name
 - positions -> int16 normalized per mesh (KHR_mesh_quantization, dequantised by an inserted child node)
 - normals -> int8 normalized, UVs -> uint16 normalized when inside [0,1], tangents/colours/UV1 removed
 - indices -> uint16 when possible
 - textures resized to MAXTEX, JPEG unless they need alpha; unused materials/textures/images pruned
usage: optimize2.py in.glb out.glb '{"maxtex":1024,"drop_mat":[...],"drop_node":[...]}'"""
import io, json, struct, sys
import numpy as np
from PIL import Image

src, dst, cfg = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
MAXTEX = cfg.get('maxtex', 1024)
drop_mat = set(cfg.get('drop_mat', [])); drop_node = set(cfg.get('drop_node', []))
b = open(src, 'rb').read()
jl = struct.unpack('<I', b[12:16])[0]
J = json.loads(b[20:20 + jl]); s = 20 + jl + 8
BIN = b[s:s + struct.unpack('<I', b[20 + jl:24 + jl])[0]]
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}
DT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NORM = {5120: 127., 5121: 255., 5122: 32767., 5123: 65535.}

def read_acc(i):
    a = J['accessors'][i]; v = J['bufferViews'][a['bufferView']]
    n, dt = NC[a['type']], np.dtype(DT[a['componentType']])
    off = v.get('byteOffset', 0) + a.get('byteOffset', 0); st = v.get('byteStride', 0) or n * dt.itemsize
    raw = np.frombuffer(BIN, np.uint8, count=st * (a['count'] - 1) + n * dt.itemsize, offset=off)
    out = np.lib.stride_tricks.as_strided(raw, (a['count'], n * dt.itemsize), (st, 1)).copy().view(dt).reshape(a['count'], n)
    if a.get('normalized'): out = out.astype(np.float32) / NORM[a['componentType']]
    return out

out = bytearray(); views = []; accs = []
def add_view(data, target=None, stride=None):
    while len(out) % 4: out.append(0)
    v = {'buffer': 0, 'byteOffset': len(out), 'byteLength': len(data)}
    if target: v['target'] = target
    if stride: v['byteStride'] = stride
    out.extend(data); views.append(v); return len(views) - 1
def add_acc(count, data, ctype, typ, normalized=False, mn=None, mx=None, target=None, stride=None):
    a = {'bufferView': add_view(data, target, stride), 'componentType': ctype, 'count': count, 'type': typ}
    if normalized: a['normalized'] = True
    if mn is not None: a['min'] = mn; a['max'] = mx
    accs.append(a); return len(accs) - 1

# 1) drop unwanted geometry
mat_name = lambda i: J['materials'][i].get('name', '') if i is not None else ''
for n in J['nodes']:
    if n.get('name') in drop_node: n.pop('mesh', None)
for m in J['meshes']:
    m['primitives'] = [p for p in m['primitives'] if mat_name(p.get('material')) not in drop_mat and p.get('mode', 4) == 4]

# optional vertex-clustering decimation for over-detailed parts (e.g. wheels with 200k triangles)
cluster = cfg.get('cluster', {})
pending = {}
def decimate(P, p, cell):
    """merge vertices that fall in the same grid cell (and same UV patch, so texture seams survive)"""
    idx = read_acc(p['indices']).ravel().astype(np.int64)
    uv = read_acc(p['attributes']['TEXCOORD_0']).astype(np.float64) if 'TEXCOORD_0' in p['attributes'] else np.zeros((len(P), 2))
    nr = read_acc(p['attributes']['NORMAL']).astype(np.float64) if 'NORMAL' in p['attributes'] else None
    loose = isinstance(cell, (list, tuple))
    ymin = cell[1] if loose and len(cell) > 1 else None
    yax = cell[2] if loose and len(cell) > 2 else 1
    ysg = cell[3] if loose and len(cell) > 3 else 1
    if loose: cell = cell[0]
    key = np.floor(P / cell).astype(np.int64) if loose else np.c_[np.floor(P / cell).astype(np.int64), np.floor(uv * 32).astype(np.int64)]
    if ymin is not None:  # only merge above ymin (e.g. floodlight heads on thin poles); keep everything below as is
        low = P[:, yax] * ysg < ymin
        key[low] = np.c_[np.full(low.sum(), -(1 << 40)), np.arange(low.sum()), np.zeros(low.sum(), np.int64)]
    if nr is not None and not loose:  # keep hard edges: split clusters by normal direction octant
        key = np.c_[key, (nr > 0.35).astype(np.int64) * 1 + (nr < -0.35).astype(np.int64) * 2]
    _, rep, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.ravel(); n = len(rep)
    cnt = np.bincount(inv, minlength=n)[:, None]
    newP = np.zeros((n, 3)); np.add.at(newP, inv, P); newP /= cnt
    newUV = np.zeros((n, 2)); np.add.at(newUV, inv, uv); newUV /= cnt
    tri = inv[idx.reshape(-1, 3)]
    ok = (tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 0] != tri[:, 2])
    tri = tri[ok]
    tri = np.unique(np.sort(tri, 1), axis=0, return_index=True)[1]
    tri = inv[idx.reshape(-1, 3)][ok][np.sort(tri)]
    if nr is not None:
        newN = np.zeros((n, 3)); np.add.at(newN, inv, nr)
        newN /= np.maximum(np.linalg.norm(newN, axis=1, keepdims=True), 1e-9)
    pending[id(p)] = (newUV, newN if nr is not None else None, tri.ravel())
    print(f'   decimated {mat_name(p.get("material"))}: {len(idx)//3} -> {len(tri)} tris')
    return newP, p

# 2) rewrite geometry
quant = {}  # mesh index -> (centre, half-extent)
for mi, m in enumerate(J['meshes']):
    if not m['primitives']: continue
    morph = any('targets' in p for p in m['primitives'])
    pos = [read_acc(p['attributes']['POSITION']).astype(np.float64) for p in m['primitives']]
    allp = np.concatenate(pos); lo, hi = allp.min(0), allp.max(0)
    c = (lo + hi) / 2; e = np.maximum((hi - lo) / 2, 1e-6)
    q_ok = not morph
    if q_ok: quant[mi] = (c, e)
    for p, P in zip(m['primitives'], pos):
        at = {}
        cell = cluster.get(mat_name(p.get('material')), cfg.get('cluster_default'))
        if cell and 'indices' in p:
            P, p = decimate(P, p, cell)
        if q_ok:
            q = np.clip(np.round((P - c) / e * 32767), -32767, 32767).astype(np.int16)
            q4 = np.concatenate([q, np.zeros((len(q), 1), np.int16)], 1)  # 8-byte stride
            at['POSITION'] = add_acc(len(q), q4.tobytes(), 5122, 'VEC3', True, (q.min(0) / 32767).tolist(), (q.max(0) / 32767).tolist(), 34962, 8)
        else:
            f = P.astype(np.float32)
            at['POSITION'] = add_acc(len(f), f.tobytes(), 5126, 'VEC3', False, f.min(0).tolist(), f.max(0).tolist(), 34962)
        if 'NORMAL' in p['attributes']:
            nrm = (pending[id(p)][1] if id(p) in pending else read_acc(p['attributes']['NORMAL'])).astype(np.float32)
            nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
            qn = np.clip(np.round(nrm * 127), -127, 127).astype(np.int8)
            qn4 = np.concatenate([qn, np.zeros((len(qn), 1), np.int8)], 1)
            at['NORMAL'] = add_acc(len(qn), qn4.tobytes(), 5120, 'VEC3', True, target=34962, stride=4)
        if 'TEXCOORD_0' in p['attributes']:
            uv = (pending[id(p)][0] if id(p) in pending else read_acc(p['attributes']['TEXCOORD_0'])).astype(np.float32)
            if uv.min() >= 0 and uv.max() <= 1:
                qu = np.round(uv * 65535).astype(np.uint16)
                at['TEXCOORD_0'] = add_acc(len(qu), qu.tobytes(), 5123, 'VEC2', True, target=34962)
            else:
                at['TEXCOORD_0'] = add_acc(len(uv), uv.tobytes(), 5126, 'VEC2', target=34962)
        p['attributes'] = at
        if 'indices' in p:
            ix = (pending[id(p)][2] if id(p) in pending else read_acc(p['indices']).ravel()).astype(np.uint32)
            if ix.max() < 65535:
                d = ix.astype(np.uint16).tobytes(); p['indices'] = add_acc(len(ix), d, 5123, 'SCALAR', target=34963)
            else:
                p['indices'] = add_acc(len(ix), ix.tobytes(), 5125, 'SCALAR', target=34963)
        p.pop('targets', None)

# 3) dequantisation nodes
for n in list(J['nodes']):  # snapshot: the loop appends nodes
    mi = n.get('mesh')
    if mi is None or mi not in quant: continue
    if not J['meshes'][mi]['primitives']: n.pop('mesh'); continue
    c, e = quant[mi]
    J['nodes'].append({'name': (n.get('name') or 'm') + '_q', 'mesh': mi, 'translation': c.tolist(), 'scale': e.tolist()})
    n.setdefault('children', []).append(len(J['nodes']) - 1); n.pop('mesh')
for n in J['nodes']:
    if 'mesh' in n and not J['meshes'][n['mesh']]['primitives']: n.pop('mesh')

# 4) prune materials / textures / images
used_m = sorted({p['material'] for m in J['meshes'] for p in m['primitives'] if 'material' in p})
mremap = {o: k for k, o in enumerate(used_m)}
for m in J['meshes']:
    for p in m['primitives']:
        if 'material' in p: p['material'] = mremap[p['material']]
J['materials'] = [J['materials'][i] for i in used_m]
def tex_refs(o, acc):
    if isinstance(o, dict):
        for k, v in o.items():
            if k.endswith('Texture') and isinstance(v, dict) and 'index' in v: acc.append(v)
            else: tex_refs(v, acc)
    elif isinstance(o, list):
        for v in o: tex_refs(v, acc)
refs = []; tex_refs(J['materials'], refs)
used_t = sorted({r['index'] for r in refs}); tremap = {o: k for k, o in enumerate(used_t)}
for r in refs: r['index'] = tremap[r['index']]
J['textures'] = [J['textures'][i] for i in used_t] if used_t else []
used_i = sorted({t['source'] for t in J['textures']}); iremap = {o: k for k, o in enumerate(used_i)}
for t in J['textures']: t['source'] = iremap[t['source']]
alpha_imgs = set()
for mt in J['materials']:
    if mt.get('alphaMode') in ('BLEND', 'MASK'):
        for key in (('pbrMetallicRoughness', 'baseColorTexture'), ('extensions', 'KHR_materials_pbrSpecularGlossiness', 'diffuseTexture')):
            o = mt
            for k in key: o = o.get(k, {}) if isinstance(o, dict) else {}
            if 'index' in o: alpha_imgs.add(J['textures'][o['index']]['source'])
new_images = []; tex_bytes = 0
for ni, oi in enumerate(used_i):
    im = J['images'][oi]; v = J['bufferViews'][im['bufferView']]
    img = Image.open(io.BytesIO(BIN[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']])); img.load()
    sc = MAXTEX / max(img.size)
    if sc < 1: img = img.resize((max(4, round(img.width * sc)), max(4, round(img.height * sc))), Image.LANCZOS)
    buf = io.BytesIO()
    if ni in alpha_imgs and img.mode in ('RGBA', 'LA', 'P', 'PA'):
        img.convert('RGBA').save(buf, 'PNG', optimize=True); mime = 'image/png'
    else:
        img.convert('RGB').save(buf, 'JPEG', quality=84, optimize=True); mime = 'image/jpeg'
    d = buf.getvalue(); tex_bytes += len(d)
    new_images.append({'bufferView': add_view(d), 'mimeType': mime})
J['images'] = new_images
for t in J['textures']: t.pop('extensions', None)
for mt in J['materials']:
    mt.get('extensions', {}).pop('KHR_materials_specular', None)
J['bufferViews'] = views; J['accessors'] = accs
while len(out) % 4: out.append(0)
J['buffers'] = [{'byteLength': len(out)}]
ext = set(J.get('extensionsUsed', [])) | {'KHR_mesh_quantization'}; ext.discard('KHR_materials_specular')
J['extensionsUsed'] = sorted(ext)
req = set(J.get('extensionsRequired', [])) | {'KHR_mesh_quantization'}
J['extensionsRequired'] = sorted(req & ext)
J.pop('samplers', None) if not J.get('textures') else None
js = json.dumps(J, separators=(',', ':')).encode()
while len(js) % 4: js += b' '
glb = struct.pack('<III', 0x46546C67, 2, 28 + len(js) + len(out)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(out), 0x004E4942) + bytes(out)
open(dst, 'wb').write(glb)
ntri = sum(J['accessors'][p['indices']]['count'] // 3 for m in J['meshes'] for p in m['primitives'] if 'indices' in p)
print(f'{dst}: {len(glb)/1e6:.2f}MB (tex {tex_bytes/1e6:.2f}, geo {(len(out)-tex_bytes)/1e6:.2f}) tris {ntri} mats {len(J["materials"])} imgs {len(new_images)}')
