"""Inverse of pack_png.py: site/<cars|tracks>/<id>/model.json + geo*.png -> one .glb (for inspecting a published model
when the original GLB is not at hand). usage: unpack_png.py site/tracks/<id> out.glb"""
import json, os, struct, sys, zlib
d, out = sys.argv[1], sys.argv[2]
J = json.load(open(os.path.join(d, 'model.json')))
B = b''
for p in J['extras']['geoPng']:
    png = open(os.path.join(d, p['file']), 'rb').read(); i = 8; idat = b''; W = H = 0
    while i < len(png):
        n = struct.unpack('>I', png[i:i + 4])[0]; t = png[i + 4:i + 8]; data = png[i + 8:i + 8 + n]
        if t == b'IHDR': W, H = struct.unpack('>II', data[:8])
        elif t == b'IDAT': idat += data
        i += 12 + n
    raw = zlib.decompress(idat); rows = b''.join(raw[r * (W + 1) + 1:(r + 1) * (W + 1)] for r in range(H))
    B += rows[:p['bytes']]
J['buffers'] = [{'byteLength': len(B)}]; J.get('extras', {}).pop('geoPng', None)
js = json.dumps(J, separators=(',', ':')).encode(); js += b' ' * ((4 - len(js) % 4) % 4); B += b'\0' * ((4 - len(B) % 4) % 4)
glb = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(B)) + struct.pack('<I', len(js)) + b'JSON' + js + struct.pack('<I', len(B)) + b'BIN\0' + B
open(out, 'wb').write(glb); print(out, round(len(glb) / 1e6, 1), 'MB')
