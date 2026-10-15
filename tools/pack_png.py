"""Package a GLB for a host that only serves json/txt/jpg/png: model.json + geo*.png.
The binary buffer (geometry AND textures) is stored losslessly as 8-bit greyscale PNGs with filter 0 on
every row, so the page can inflate the IDAT stream itself (DecompressionStream) - no canvas colour handling.
usage: pack_png.py in.glb outdir"""
import json, os, struct, sys, zlib
src, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
b = open(src, 'rb').read()
jl = struct.unpack('<I', b[12:16])[0]; J = json.loads(b[20:20 + jl]); s = 20 + jl + 8
B = b[s:s + struct.unpack('<I', b[20 + jl:24 + jl])[0]]
W = 4096; RAW = 24 * 1024 * 1024
def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
parts = []
for k in range(0, len(B), RAW):
    piece = B[k:k + RAW]; H = (len(piece) + W - 1) // W
    padded = piece + bytes(H * W - len(piece))
    rows = b''.join(b'\x00' + padded[r * W:(r + 1) * W] for r in range(H))
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 0, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b'')
    name = f'geo{len(parts)}.png'; open(os.path.join(outdir, name), 'wb').write(png)
    parts.append({'file': name, 'bytes': len(piece)})
J['buffers'] = [{'byteLength': len(B), 'uri': 'geo.bin'}]
J.setdefault('extras', {}).pop('geoParts', None); J['extras']['geoPng'] = parts
open(os.path.join(outdir, 'model.json'), 'w').write(json.dumps(J, separators=(',', ':')))
sizes = {f: os.path.getsize(os.path.join(outdir, f)) for f in os.listdir(outdir)}
print(len(sizes), 'files', round(sum(sizes.values()) / 1e6, 2), 'MB; largest', max(sizes.items(), key=lambda x: x[1]))
