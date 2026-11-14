"""Where are each car's tail / brake lamps? Find the red lamp surfaces at the back of the packed car models.

usage: python3 tools/brake_lamps.py [car id ...]
  reads site/cars/<id>/ (model.json + geo PNGs) and the CARS entries (model s/off/rotY) in site/index.html,
  prints one JS line per car for BRK in site/index.html: id:[[x,y,z,w,h],...]  (car space: +x left, +z nose, m;
  w/h = the lamp's width/height), and writes work/brk/<id>.png (the back of the car, lamps outlined) to check by eye.

How: every triangle's colour is its material's base colour times the texture at the triangle's UV centre. A lamp
triangle is red (r > 0.3, r > 1.7 g, r > 1.7 b), faces backwards (normal z < -0.25), sits in the back 0.45 m of the car
and above the ground, and belongs to a lamp-like material (name: light / lamp / glass / red / lens / led / tail /
brake / stop / rear, or an emissive or see-through material) - red body paint is not a lamp. The red area is split
into left / right (and a centre strip when one runs across the middle) and each part gives a box. Cars where nothing
is found get none (the game falls back to the generic glow).
"""
import io, json, os, re, struct, sys, zlib
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glblib import acc, node_matrix  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
NOTLAMP = re.compile(r'disc|disk|calip|bump|handbrake|interior|int_', re.I)
# cars whose lamps the colour test misses or mistakes (dark lenses, red paint, lamps in a shared atlas): the lamp
# materials by name (checked by eye on work/brk/<id>.png)
MATS = {'alfa33': 'rear_lights', 'vantage': 'light_red', 'gt500': 'rearlight', 'f40lb': 'tailight', 'p930': '930_lights$',
        'f458': 'tail_light', 'lfa': 'RED_GLASS', 'laferrari': 'break_lights_glasses|tail_lights', 'r34': '^Material.00[12]$', 'rx7': 'Material.019$', 's2000': '^Material$|Material.007$', 'a90': 'TOYOTA_SUPRA_MAIN_LIGHT',
        'model3': 'breaklight|rear_light', 'mclarenf1': 'brakelight|rear_lamp', 'imola': 'RED_GLASS|LightA', 's30z': 'Material.006|Material.001$'}
# read off the gridded back view by hand: [x, y, w, h] of the left lamp (z from the body there)
MANUAL = {'f458': [0.77, 0.855, 0.18, 0.18]}
LAMPY = re.compile(r'light|lamp|glass|red|lens|led|tail|brake|break|stop|rear|tembus|refl', re.I)


def png_bytes(path, n):
    b = open(path, 'rb').read(); o = 8; W = 0; idat = []
    while o < len(b):
        ln = struct.unpack('>I', b[o:o + 4])[0]; t = b[o + 4:o + 8]
        if t == b'IHDR': W = struct.unpack('>I', b[o + 8:o + 12])[0]
        elif t == b'IDAT': idat.append(b[o + 8:o + 8 + ln])
        elif t == b'IEND': break
        o += 12 + ln
    raw = zlib.decompress(b''.join(idat)); out = bytearray(); r = 0
    while len(out) < n:
        s = r * (W + 1) + 1; out += raw[s:s + min(W, n - len(out))]; r += 1
    return bytes(out)


def car_fits():
    s = open(os.path.join(ROOT, 'site/index.html')).read(); s = s[s.index('const CARS=['):]; s = s[:s.index('\n];')]; out = {}
    for blk in re.split(r'\n (?=\{id:)', s):
        mi = re.match(r"\{id:'([a-z0-9]+)'", blk); mm = re.search(r"model:\{url:'cars/[^']+',s:([\d.]+),off:\[([^\]]*)\](?:,rotY:([^,}]+))?", blk)
        mb = re.search(r'body:\{([^}]*)\}', blk)
        if not (mi and mm and mb): continue
        b = dict((k, float(v)) for k, v in re.findall(r'(\w+):([\d.]+)', mb.group(1)))
        out[mi.group(1)] = (float(mm.group(1)), [float(v) for v in mm.group(2).split(',')], bool(mm.group(3) and mm.group(3).strip() not in ('0', 'false')), b)
    return out


def tris(cid):
    d = os.path.join(ROOT, 'site/cars', cid); J = json.load(open(os.path.join(d, 'model.json')))
    B = b''.join(png_bytes(os.path.join(d, p['file']), p['bytes']) for p in J['extras']['geoPng'])
    imgs = {}
    def tex(i):
        if i not in imgs:
            im = J['images'][J['textures'][i]['source']]; v = J['bufferViews'][im['bufferView']]
            o = v.get('byteOffset', 0); imgs[i] = np.asarray(Image.open(io.BytesIO(B[o:o + v['byteLength']])).convert('RGB').resize((256, 256))) / 255.
        return imgs[i]
    out = []
    def walk(i, P):
        n = J['nodes'][i]; W = P @ node_matrix(n)
        if 'mesh' in n:
            for p in J['meshes'][n['mesh']]['primitives']:
                if p.get('mode', 4) != 4: continue
                X = acc(J, B, p['attributes']['POSITION']).astype(float); X = (W @ np.c_[X, np.ones(len(X))].T).T[:, :3]
                idx = acc(J, B, p['indices']).ravel() if 'indices' in p else np.arange(len(X)); T = X[idx.reshape(-1, 3)]
                m = J['materials'][p['material']] if 'material' in p else {}
                pb = m.get('pbrMetallicRoughness', {}); f = np.array(pb.get('baseColorFactor', [1, 1, 1, 1])[:3])
                col = np.repeat(f[None], len(T), 0)
                bt = pb.get('baseColorTexture')
                if bt and 'TEXCOORD_%d' % bt.get('texCoord', 0) in p['attributes']:
                    uv = acc(J, B, p['attributes']['TEXCOORD_%d' % bt.get('texCoord', 0)]).astype(float)[idx.reshape(-1, 3)].mean(1)
                    t = tex(bt['index']); u = (uv[:, 0] % 1 * 255).astype(int); v = (uv[:, 1] % 1 * 255).astype(int); col = col * t[v, u]
                em = np.array(m.get('emissiveFactor', [0, 0, 0])); lampy = not NOTLAMP.search(m.get('name', '')) and bool(LAMPY.search(m.get('name', ''))) or em.max() > 0.05 or m.get('alphaMode', 'OPAQUE') != 'OPAQUE'
                out.append((m.get('name', ''), T, col, lampy))
        for c in n.get('children', []): walk(c, W)
    for r in J['scenes'][J.get('scene', 0)]['nodes']: walk(r, np.eye(4))
    return out


def main():
    fits = car_fits(); ids = sys.argv[1:] or sorted(fits); os.makedirs(os.path.join(ROOT, 'work/brk'), exist_ok=True); lines = []
    for cid in ids:
        if cid not in fits or len(fits[cid]) < 4: print('//', cid, 'no fit'); continue
        s, off, rot, body = fits[cid]
        allT = []; allC = []; lamp = []
        for name, T, col, lampy in tris(cid):
            X = (T + np.array(off)) * s
            if rot: X = X * np.array([-1, 1, -1])
            allT.append(X); allC.append(col)
            nrm = np.cross(X[:, 1] - X[:, 0], X[:, 2] - X[:, 0]); ar = np.linalg.norm(nrm, axis=1); nz = nrm[:, 2] / np.maximum(ar, 1e-12)
            red = (col[:, 0] > 0.18) & (col[:, 0] > 2.6 * col[:, 1]) & (col[:, 0] > 2.2 * col[:, 2])
            if cid in MATS: hit = np.full(len(X), bool(re.search(MATS[cid], name))) & (nz < -0.25)
            else: hit = (red & (nz < -0.25)) if lampy else np.zeros(len(X), bool)
            lamp.append((X, hit, ar / 2))
        A = np.concatenate(allT); AC = np.concatenate(allC); zmin = max(A[:, :, 2].min(), -body['l'] / 2 - 0.15); ymin = max(A[:, :, 1].min(), -0.05)
        keep = (A[:, :, 2].min(1) > zmin - 0.3) & (np.abs(A[:, :, 0]).max(1) < body['w'] / 2 + 0.3); A = A[keep]; AC = AC[keep]   # not a showroom floor
        C = []; Wt = []
        for X, ok, ar in lamp:
            c = X.mean(1); ok = ok & (c[:, 2] < zmin + 0.45) & (c[:, 1] > ymin + 0.25)
            C.append(c[ok]); Wt.append(ar[ok])
        C = np.concatenate(C); Wt = np.concatenate(Wt); boxes = []
        if Wt.sum() > 0.002:
            parts = [C[:, 0] > 0.25, C[:, 0] < -0.25, np.abs(C[:, 0]) <= 0.25]
            for sel in parts:
                if Wt[sel].sum() < 0.0015: continue
                p = C[sel]; w = Wt[sel]; m = (p * w[:, None]).sum(0) / w.sum()
                lo = np.percentile(p, 10, axis=0); hi = np.percentile(p, 90, axis=0)
                boxes.append([round(float(m[0]), 3), round(float(m[1]), 3), round(float(lo[2]), 3), round(float(max(0.06, hi[0] - lo[0])), 2), round(float(max(0.04, hi[1] - lo[1])), 2)])
        # left / right the same (mirror image, averaged); a centre part only as a thin strip (a third brake light)
        sides = [b for b in boxes if abs(b[0]) > 0.25]; mid = [b for b in boxes if abs(b[0]) <= 0.25 and b[4] < 0.08]
        if len(sides) == 2:
            a, c = sides; m = [round((abs(a[0]) + abs(c[0])) / 2, 3), round((a[1] + c[1]) / 2, 3), round(max(a[2], c[2]), 3), round((a[3] + c[3]) / 2, 2), round((a[4] + c[4]) / 2, 2)]
            sides = [m, [-m[0]] + m[1:]]
        elif len(sides) == 1: a = sides[0]; sides = [[abs(a[0])] + a[1:], [-abs(a[0])] + a[1:]]
        if cid in MANUAL:
            x, y, w, h = MANUAL[cid]; near = A[(np.abs(A[:, :, 0].mean(1) - x) < 0.15) & (np.abs(A[:, :, 1].mean(1) - y) < 0.15)]
            z = float(near[:, :, 2].min()) if len(near) else zmin; sides = [[x, y, round(z, 3), w, h], [-x, y, round(z, 3), w, h]]; mid = []
        boxes = sides + mid
        lines.append(f'{cid}:{json.dumps(boxes, separators=(",", ":"))}')
        print(f'// {cid}: red lamp area {Wt.sum() * 1e4:.0f} cm2, {len(boxes)} part(s)')
        # the back of the car, lamps outlined
        S = 120; im = Image.new('RGB', (int(2.4 * S), int(1.6 * S)), (235, 235, 235)); dr = ImageDraw.Draw(im)
        sel = A[:, :, 2].mean(1) < zmin + 0.6; back = A[sel]; bc = AC[sel]
        for k in np.argsort(-back[:, :, 2].mean(1)):
            t = back[k]; dr.polygon([(1.2 * S - v[0] * S, 1.5 * S - (v[1] - ymin) * S) for v in t], fill=tuple(int(c) for c in np.clip(bc[k] * 255, 0, 255)))
        for b in boxes:
            x, y, z, w, h = b; dr.rectangle([1.2 * S - (x + w / 2) * S, 1.5 * S - (y - ymin + h / 2) * S, 1.2 * S - (x - w / 2) * S, 1.5 * S - (y - ymin - h / 2) * S], outline=(255, 0, 0), width=2)
        im.save(os.path.join(ROOT, 'work/brk', cid + '.png'))
    print('const BRK={' + ','.join(lines) + '};')


if __name__ == '__main__':
    main()
