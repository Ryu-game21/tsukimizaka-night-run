"""asphalt mask + skeleton graph. usage: graph.py model.glb mat1,mat2 x0 z0 W H  -> asph.npy edges.json graph.png"""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage.morphology import skeletonize, closing, disk, remove_small_holes
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, triangles
a = np.load(sys.argv[1]); x0, z0, R = json.load(open(sys.argv[2])); H, W = a.shape
from skimage.morphology import closing, disk, remove_small_holes
a = closing(a, disk(2)); a = remove_small_holes(a, max_size=400)
lab, n = ndi.label(a); s = ndi.sum(a, lab, range(1, n + 1)); a = lab == (np.argmax(s) + 1)
sk = skeletonize(a); dt = ndi.distance_transform_edt(a) * R
print('components', n, 'median width', np.median(dt[sk]) * 2)
np.save('asph.npy', a); json.dump([x0, z0, R], open('grid.json', 'w'))
ys, xs = np.nonzero(sk); P = set(zip(ys.tolist(), xs.tolist()))
def nb(p): return [(p[0] + dy, p[1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy or dx) and (p[0] + dy, p[1] + dx) in P]
deg = {p: len(nb(p)) for p in P}; Jn = [p for p in P if deg[p] != 2]
m = np.zeros(sk.shape, bool)
for p in Jn: m[p] = True
lab, n = ndi.label(ndi.binary_dilation(m, iterations=3)); node = {p: lab[p] for p in Jn}
edges = []; seen = set()
for p in Jn:
    for q in nb(p):
        if q in node or (p, q) in seen: continue
        path = [p, q]; prev = p; cur = q
        while cur not in node:
            nx = [r for r in nb(cur) if r != prev and r not in path[-3:]]
            if not nx: break
            prev, cur = cur, nx[0]; path.append(cur)
        seen.add((path[-1], path[-2]))
        if (cur in node and node[cur] != node[p]) or len(path) > 20:
            L = np.sum(np.linalg.norm(np.diff(np.array(path), axis=0), axis=1)) * R
            edges.append((int(node[p]), int(node.get(cur, -1)), float(L), [list(map(int, x)) for x in path]))
uniq = {}
for e in edges: uniq[(min(e[0], e[1]), max(e[0], e[1]), round(e[2]))] = e
edges = list(uniq.values()); json.dump(edges, open('edges.json', 'w'))
img = Image.fromarray((a * 70).astype(np.uint8)).convert('RGB'); dd = ImageDraw.Draw(img)
rng = np.random.default_rng(3)
for i, (a_, b_, L, path) in enumerate(edges):
    c = tuple(int(x) for x in rng.integers(80, 255, 3))
    for p in path: img.putpixel((p[1], p[0]), c)
    mid = path[len(path) // 2]; dd.text((mid[1] + 5, mid[0] - 5), f'{i}', fill=(255, 255, 255))
    w = np.median(dt[tuple(np.array(path).T)]) * 2
    print(i, a_, b_, round(L), 'w', round(float(w), 1), 'ends', [(round(q[1] * R + x0), round(q[0] * R + z0)) for q in (path[0], path[-1])])
cent = ndi.center_of_mass(lab > 0, lab, range(1, n + 1))
for k, (cy, cx) in enumerate(cent): dd.text((cx - 4, cy + 6), 'N%d' % (k + 1), fill=(255, 80, 80))
img.save('graph.png')
