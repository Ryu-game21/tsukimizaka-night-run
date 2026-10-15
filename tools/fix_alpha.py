"""BLEND materials whose texture has no real transparency -> OPAQUE; hard-edged cut-outs -> MASK.
Big transparent surfaces render without depth writes in three.js and look see-through. usage: fix_alpha.py in.glb out.glb"""
import sys, os, io, json, struct
import numpy as np
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
b = open(src, 'rb').read(); jl = struct.unpack('<I', b[12:16])[0]; J = json.loads(b[20:20 + jl]); s = 20 + jl + 8
B = b[s:s + struct.unpack('<I', b[20 + jl:24 + jl])[0]]
stats = {'opaque': [], 'mask': [], 'blend': []}
for m in J['materials']:
    if m.get('alphaMode') != 'BLEND': continue
    pb = m.get('pbrMetallicRoughness', {}); fa = pb.get('baseColorFactor', [1, 1, 1, 1])[3]
    if fa < 0.99: stats['blend'].append(m.get('name')); continue
    bc = pb.get('baseColorTexture')
    if not bc: m.pop('alphaMode'); stats['opaque'].append(m.get('name')); continue
    im = J['images'][J['textures'][bc['index']]['source']]; v = J['bufferViews'][im['bufferView']]
    I = Image.open(io.BytesIO(B[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']]))
    if 'A' not in I.getbands() and I.mode != 'P':
        m.pop('alphaMode'); stats['opaque'].append(m.get('name')); continue
    a = np.asarray(I.convert('RGBA'))[:, :, 3].astype(int)
    trans = (a < 250).mean(); soft = ((a > 20) & (a < 235)).mean()
    if trans < 0.002: m.pop('alphaMode'); stats['opaque'].append(m.get('name'))
    elif soft < 0.6 * trans: m['alphaMode'] = 'MASK'; m['alphaCutoff'] = 0.5; stats['mask'].append(m.get('name'))
    else: stats['blend'].append(m.get('name'))
js = json.dumps(J, separators=(',', ':')).encode()
while len(js) % 4: js += b' '
open(dst, 'wb').write(struct.pack('<III', 0x46546C67, 2, 28 + len(js) + len(B)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(B), 0x004E4942) + bytes(B))
print({k: len(v) for k, v in stats.items()}, 'still blended:', stats['blend'][:12])
