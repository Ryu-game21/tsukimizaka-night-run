"""aerial (texture-average colours) + candidate-material map. usage: survey.py model.glb x0 z0 W H res mat1,mat2,..."""
import sys, os, io
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, triangles
J, B = load(sys.argv[1]); x0, z0, Wm, Hm, R = map(float, sys.argv[2:7]); cands = sys.argv[7].split(',')
avg = {}
for m in J['materials']:
    pb = m.get('pbrMetallicRoughness', {}); bc = pb.get('baseColorTexture'); f = np.array(pb.get('baseColorFactor', [1, 1, 1, 1])[:3])
    if bc:
        im = J['images'][J['textures'][bc['index']]['source']]; v = J['bufferViews'][im['bufferView']]
        I = Image.open(io.BytesIO(B[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']])).convert('RGB').resize((8, 8))
        c = np.asarray(I).reshape(-1, 3).mean(0) / 255 * f
    else: c = f
    avg[m.get('name')] = c
W, H = int(Wm / R), int(Hm / R)
al, cl, cand = [], [], {c: [] for c in cands}
for m, t, nn in triangles(J, B):
    al.append(t); cl.append(np.repeat(avg.get(m, np.ones(3))[None], len(t), 0))
    if m in cand: cand[m].append(t)
T = np.concatenate(al); Cc = np.concatenate(cl)
N = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
L = np.array([0.4, 0.8, 0.45]); L /= np.linalg.norm(L); sh = 0.4 + 0.6 * np.abs(N @ L)
cen = T.mean(1); s = (cen[:, 0] > x0) & (cen[:, 0] < x0 + Wm) & (cen[:, 2] > z0) & (cen[:, 2] < z0 + Hm)
T, Cc, sh = T[s], Cc[s], sh[s]
im = Image.new('RGB', (W, H), (30, 30, 40)); d = ImageDraw.Draw(im)
for i in np.argsort(T[:, :, 1].max(1)):
    d.polygon([((v[0] - x0) / R, (v[2] - z0) / R) for v in T[i]], fill=tuple((np.clip(Cc[i] * sh[i], 0, 1) * 255).astype(int)))
im.save('aerial.png')
pal = [(220, 40, 40), (40, 40, 220), (40, 180, 40), (200, 160, 0), (200, 0, 200), (0, 180, 180), (120, 60, 0), (90, 90, 90)]
im2 = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(im2)
for k, c in list(enumerate(cands))[::-1]:
    for t in cand[c]:
        for tr in t: d.polygon([((v[0] - x0) / R, (v[2] - z0) / R) for v in tr], fill=pal[k % len(pal)])
    d.text((5, 5 + 12 * k), c, fill=pal[k % len(pal)])
im2.save('cand.png')
