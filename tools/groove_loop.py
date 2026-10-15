"""Racing-line loop from rubber/groove materials.
usage: groove_loop.py model.glb groove1,groove2 road1,road2 x0 z0 W H [dil_m]
-> groove.npy, road.npy, grid.json, loop.npy (ordered world xz of the skeleton cycle), loop.png"""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage.morphology import skeletonize, disk, binary_dilation, remove_small_holes
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, triangles
J, B = load(sys.argv[1]); gm = set(sys.argv[2].split(',')); rm = set(sys.argv[3].split(','))
x0, z0, Wm, Hm = map(float, sys.argv[4:8]); dil = float(sys.argv[8]) if len(sys.argv) > 8 else 2.5
R = 0.5; W, H = int(Wm / R), int(Hm / R)
ig = Image.new('L', (W, H), 0); ir = Image.new('L', (W, H), 0); dg = ImageDraw.Draw(ig); dr = ImageDraw.Draw(ir)
for m, t, nn in triangles(J, B):
    if m in gm or m in rm:
        for tr in t:
            poly = [((v[0] - x0) / R, (v[2] - z0) / R) for v in tr]
            if m in gm: dg.polygon(poly, fill=1)
            if m in rm: dr.polygon(poly, fill=1)
G = np.asarray(ig).astype(bool); A = np.asarray(ir).astype(bool) | G
if os.environ.get('MASK'):
    G = np.load(os.environ['MASK']); A = G.copy()
np.save('groove.npy', G); np.save('road.npy', A); json.dump([x0, z0, R], open('grid.json', 'w'))
M = binary_dilation(G, disk(int(dil / R))) & ndi.binary_dilation(A, iterations=2)
M = remove_small_holes(M, max_size=20000)
lab, n = ndi.label(M); s = ndi.sum(M, lab, range(1, n + 1)); M = lab == (np.argmax(s) + 1)
print('groove comps', n, 'largest share', round(s.max() / s.sum(), 3))
sk = skeletonize(M)
# prune spurs
K = np.ones((3, 3)); K[1, 1] = 0
for it in range(4000):
    deg = ndi.convolve(sk.astype(np.uint8), K.astype(np.uint8), mode='constant')
    end = sk & (deg <= 1)
    if not end.any(): break
    sk &= ~end
deg = ndi.convolve(sk.astype(np.uint8), K.astype(np.uint8), mode='constant')
print('skeleton px', sk.sum(), 'junction px', int((sk & (deg > 2)).sum()))
# trace: loop = shortest path A->B plus shortest path B->A avoiding the first one
import networkx as nx
ys, xs = np.nonzero(sk); S = list(zip(ys.tolist(), xs.tolist())); Sset = set(S)
Gx = nx.Graph()
for p in S:
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            q = (p[0] + dy, p[1] + dx)
            if (dy or dx) and q in Sset: Gx.add_edge(p, q, w=float(np.hypot(dy, dx)))
A0 = S[0]
dist = nx.single_source_dijkstra_path_length(Gx, A0, weight='w')
B0 = max(dist, key=dist.get)
p1 = nx.dijkstra_path(Gx, A0, B0, weight='w')
G2 = Gx.copy(); G2.remove_nodes_from(p1[1:-1])
# also block a small neighbourhood so the return path is distinct
for p in p1[3:-3]:
    for dy in (-2, -1, 0, 1, 2):
        for dx in (-2, -1, 0, 1, 2):
            q = (p[0] + dy, p[1] + dx)
            if q in G2 and q not in (A0, B0): G2.remove_node(q)
try:
    p2 = nx.dijkstra_path(G2, B0, A0, weight='w'); path = p1 + p2[1:-1]
except nx.NetworkXNoPath:
    # open curve (a gap somewhere): take the longest geodesic path and close it with a straight join
    d2 = nx.single_source_dijkstra_path_length(Gx, B0, weight='w'); C0 = max(d2, key=d2.get)
    path = nx.dijkstra_path(Gx, B0, C0, weight='w')
    print('open curve: closing gap between', B0, C0, 'px dist', round(float(np.hypot(B0[0]-C0[0], B0[1]-C0[1])), 1))
    # close the gap along the middle of the road surface instead of a straight chord
    from skimage.graph import route_through_array
    dt = ndi.distance_transform_edt(A)
    cost = np.where(A, 1.0 / (1.0 + dt) ** 2, 1e6)
    gp, _ = route_through_array(cost, C0, B0, fully_connected=True, geometric=True)
    path = path + [tuple(p) for p in gp[1:-1]]
    print('gap closed along road with', len(gp), 'px')
P = np.array(path, float); XZ = np.c_[P[:, 1] * R + x0 + R / 2, P[:, 0] * R + z0 + R / 2]
L = np.sum(np.linalg.norm(np.diff(XZ, axis=0), axis=1)); gap = np.linalg.norm(XZ[0] - XZ[-1])
print('traced', len(path), 'of', len(S), 'px; length', round(L), 'm; closing gap', round(gap, 1))
np.save('loop.npy', XZ)
img = np.zeros((H, W, 3), np.uint8); img[A] = (60, 60, 60); img[G] = (120, 40, 40); img[sk] = (255, 255, 0)
for p in path[::1]: img[p] = (0, 255, 255)
Image.fromarray(img).resize((W // 2, H // 2)).save('loop.png')
