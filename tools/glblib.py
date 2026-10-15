"""Small GLB reader: world-space triangles per material, with node transforms applied."""
import json, struct
import numpy as np

NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
DT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NORM = {5120: 127., 5121: 255., 5122: 32767., 5123: 65535.}


def load(path):
    b = open(path, 'rb').read()
    jl = struct.unpack('<I', b[12:16])[0]
    J = json.loads(b[20:20 + jl])
    s = 20 + jl + 8
    B = b[s:s + struct.unpack('<I', b[20 + jl:24 + jl])[0]] if len(b) > 20 + jl else b''
    return J, B


def acc(J, B, i):
    a = J['accessors'][i]
    v = J['bufferViews'][a['bufferView']]
    n, dt = NC[a['type']], np.dtype(DT[a['componentType']])
    off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
    st = v.get('byteStride', 0) or n * dt.itemsize
    raw = np.frombuffer(B, np.uint8, count=st * (a['count'] - 1) + n * dt.itemsize, offset=off)
    out = np.lib.stride_tricks.as_strided(raw, (a['count'], n * dt.itemsize), (st, 1)).copy().view(dt).reshape(a['count'], n)
    if a.get('normalized'):
        out = out.astype(np.float32) / NORM[a['componentType']]
    return out


def node_matrix(n):
    if 'matrix' in n:
        return np.array(n['matrix'], float).reshape(4, 4).T
    T = np.eye(4)
    T[:3, 3] = n.get('translation', [0, 0, 0])
    x, y, z, w = n.get('rotation', [0, 0, 0, 1])
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    T[:3, :3] = R @ np.diag(n.get('scale', [1, 1, 1]))
    return T


def triangles(J, B):
    """yield (material_name, world_tris[N,3,3], node_name) for every primitive (TRIANGLES mode only)"""
    out = []

    def walk(i, P):
        n = J['nodes'][i]
        W = P @ node_matrix(n)
        if 'mesh' in n:
            for p in J['meshes'][n['mesh']]['primitives']:
                if p.get('mode', 4) != 4:
                    continue
                X = acc(J, B, p['attributes']['POSITION']).astype(np.float64)
                X = (W @ np.c_[X, np.ones(len(X))].T).T[:, :3]
                idx = acc(J, B, p['indices']).ravel() if 'indices' in p else np.arange(len(X))
                tri = X[idx.reshape(-1, 3)]
                mt = J['materials'][p['material']].get('name', str(p['material'])) if 'material' in p else '?'
                out.append((mt, tri, n.get('name', '')))
        for c in n.get('children', []):
            walk(c, W)

    for r in J['scenes'][J.get('scene', 0)]['nodes']:
        walk(r, np.eye(4))
    return out
