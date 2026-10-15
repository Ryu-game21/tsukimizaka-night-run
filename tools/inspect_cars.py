import sys, json, os
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from glblib import load, triangles

for path in sys.argv[1:]:
    J, B = load(path)
    a = J.get('asset', {}).get('extras', {})
    tris = triangles(J, B)
    ntri = sum(len(t) for _, t, _ in tris)
    print('=' * 70)
    print(os.path.basename(path), f'{os.path.getsize(path)/1e6:.1f}MB', 'tris', ntri, 'images', len(J.get('images', [])))
    print(' title:', a.get('title'), '| author:', a.get('author'), '| license:', a.get('license'))
    print(' ext:', J.get('extensionsUsed'), 'req:', J.get('extensionsRequired'))
    imgs = J.get('images', [])
    big = 0
    for im in imgs:
        if 'bufferView' in im:
            big += J['bufferViews'][im['bufferView']]['byteLength']
    print(f' image bytes {big/1e6:.1f}MB')
    allp = np.concatenate([t.reshape(-1, 3) for _, t, _ in tris])
    print(' bbox min', allp.min(0).round(3), 'max', allp.max(0).round(3), 'size', (allp.max(0) - allp.min(0)).round(3))
    per = {}
    for m, t, nn in tris:
        per.setdefault(m, []).append(t.reshape(-1, 3))
    for m, v in sorted(per.items(), key=lambda kv: -sum(len(x) for x in kv[1])):
        v = np.concatenate(v)
        print(f'  {m[:28]:28s} n{len(v)//3:7d} min{v.min(0).round(2)} max{v.max(0).round(2)}')
