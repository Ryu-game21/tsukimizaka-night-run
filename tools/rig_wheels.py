#!/usr/bin/env python3
"""Find a car model's four wheels and the materials that spin with them -> a RIGS entry for site/index.html.

usage: python3 tools/rig_wheels.py <car id> [<car id> ...]
       (reads site/cars/<id>/model.json + geo*.png and the car's model:{s,off,rotY} from CARS in site/index.html)

What the game does with it (rigModel in index.html): every triangle wholly inside a wheel cylinder is cut out of
the body. Triangles of a "spin" material turn with the wheel; other materials inside 80% of the tyre radius (brake
calipers, uprights) only steer. Cylinders: [x, y, z, r, x0, x1, yaw0] per wheel, order rear-left, rear-right,
front-left, front-right, in car space (metres, +z = nose, +x = left). yaw0 is the angle the model's front wheels
were modelled turned at; the game straightens them.

How it finds them:
  - hub: the ground-contact patch at each corner; the tyre = the material touching the ground there, its bounding
    box (after undoing a pre-turned front wheel, found from the tyre's least-spread axis) gives centre, radius, width.
  - spin materials: >= 90% of their triangles inside the wheel cylinders, minus caliper-like ones (a piece covering
    under 45% of the circle, away from the hub). Names containing "callip"/"caliper" are always treated as calipers.

It is a starting point: the configs in index.html were tuned from it (a material can be moved out of spin by hand).
Always check the result by eye in a real renderer (rest pose identical to the original, nothing outside the tyre
moves when the wheels spin, calipers stay put): see CLAUDE.md "車のモーション".
"""
import json, os, re, struct, sys, zlib
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glblib import triangles  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'site')


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


def load_packed(cid):
    d = os.path.join(ROOT, 'cars', cid)
    J = json.load(open(os.path.join(d, 'model.json')))
    B = b''.join(png_bytes(os.path.join(d, p['file']), p['bytes']) for p in J['extras']['geoPng'])
    return J, B


def model_cfg(cid):
    s = open(os.path.join(ROOT, 'index.html'), encoding='utf8').read()
    i = s.index("{id:'%s'" % cid)
    m = re.search(r"model:\{url:'[^']*',s:([-\d.e]+),off:\[([^\]]*)\](?:,rotY:(\w+))?", s[i:i + 4000])
    return float(m.group(1)), [float(x) for x in m.group(2).split(',')], m.group(3) in ('1', 'true')


def car_space(cid):
    s, off, rot = model_cfg(cid); J, B = load_packed(cid); out = []
    for m, t, _ in triangles(J, B):
        P = (t.reshape(-1, 3, 3) + np.array(off)) * s
        if rot: P = P * np.array([-1, 1, -1])
        out.append((m, P))
    return out


def hubs_of(parts):
    allP = np.concatenate([p for _, p in parts]).reshape(-1, 3)
    ymin = allP[:, 1].min(); lo = allP[allP[:, 1] < ymin + 0.03]; zc = np.median(lo[:, 2]); hubs = []
    for q in range(4):
        sx = 1 if q % 2 else -1; front = q >= 2
        sel = lo[((lo[:, 0] > 0) == (sx > 0)) & ((lo[:, 2] > zc) == front)]
        if len(sel) < 3: raise SystemExit('no ground contact at wheel %d' % q)
        hx, hz = np.median(sel[:, 0]), np.median(sel[:, 2]); cand = {}
        for m, P in parts:
            c = P.mean(1); s2 = (abs(c[:, 0] - hx) < 0.45) & (abs(c[:, 2] - hz) < 0.6) & (c[:, 1] < 0.9)
            if s2.any() and (P[s2][:, :, 1].min(1) < ymin + 0.02).sum() > 0: cand.setdefault(m, []).append(P[s2])
        found = None
        for m in sorted(cand, key=lambda m: -sum(len(x) for x in cand[m])):
            Q = np.concatenate(cand[m]).reshape(-1, 3); c0 = (Q.min(0) + Q.max(0)) / 2
            ev, evec = np.linalg.eigh(np.cov((Q - c0).T)); ax = evec[:, 0] * np.sign(evec[0, 0] or 1)
            yaw0 = float(np.arctan2(-ax[2], ax[0])) if abs(ax[1]) < 0.3 else 0.0
            if abs(yaw0) < np.radians(2.5) or not front: yaw0 = 0.0
            cs, sn = np.cos(-yaw0), np.sin(-yaw0); D = Q - c0
            R = np.c_[D[:, 0] * cs + D[:, 2] * sn, D[:, 1], -D[:, 0] * sn + D[:, 2] * cs] + c0
            l3, h3 = R.min(0), R.max(0); sz = h3 - l3
            if 0.45 < sz[1] < 0.9 and abs(sz[1] - sz[2]) < 0.08 * sz[1] and l3[1] < ymin + 0.02 and sz[0] < 0.45:
                r = sz[1] / 2; found = [(l3[0] + h3[0]) / 2, l3[1] + r, (l3[2] + h3[2]) / 2, r, l3[0], h3[0], yaw0, m]; break
        if not found:   # no clean tyre material: fit a circle to the profile around the contact patch
            near = allP[(abs(allP[:, 0] - hx) < 0.18) & (abs(allP[:, 2] - hz) < 0.55) & (allP[:, 1] < 1.0)]; best = (-1e9, 0)
            for r in np.arange(0.25, 0.41, 0.003):
                d = np.hypot(near[:, 1] - (ymin + r), near[:, 2] - hz)
                score = (abs(d - r) < 0.012).sum() - 2.0 * ((d > r + 0.02) & (d < r + 0.07) & (near[:, 1] > ymin + r * 0.6)).sum()
                if score > best[0]: best = (score, r)
            r = best[1]; d = np.hypot(allP[:, 1] - ymin - r, allP[:, 2] - hz)
            tread = allP[(abs(d - r) < 0.02) & (abs(allP[:, 0] - hx) < 0.25)]
            x0, x1 = (tread[:, 0].min(), tread[:, 0].max()) if len(tread) else (hx - 0.12, hx + 0.12)
            found = [hx, ymin + r, hz, r, x0, x1, 0.0, '(circle fit)']
        hubs.append(found)
    return hubs


def inside(P, h, lim):
    x, y, z, r, x0, x1, yaw = h[:7]; cs, sn = np.cos(-yaw), np.sin(-yaw); dx = P[..., 0] - x; dz = P[..., 2] - z
    xx = x + dx * cs + dz * sn; zz = -dx * sn + dz * cs; yy = P[..., 1] - y
    ok = (np.hypot(yy, zz) <= r * lim) & (xx >= x0 - (0.12 if x < 0 else 0.04)) & (xx <= x1 + (0.12 if x > 0 else 0.04))
    return ok, np.arctan2(yy, zz), np.hypot(yy, zz) / r


def main():
    for cid in sys.argv[1:]:
        parts = car_space(cid); H = hubs_of(parts); spin = []; notes = []; agg = {}
        for m, P in parts:   # a material can come in several pieces: judge it as a whole
            e = agg.setdefault(m, [0, 0, [], []]); e[0] += len(P)
            for h in H:
                ok, ang, rr = inside(P, h, 1.05); a = ok.all(1); e[1] += int(a.sum())
                if a.any():
                    e[2].append(len(set((np.floor((ang[a] + np.pi) / (2 * np.pi) * 36) % 36).astype(int).ravel())) / 36)
                    e[3].append(float(rr[a].mean()))
        for m, (n, ni, cov, rad) in agg.items():
            if 0.3 * n <= ni < 0.9 * n and ni > 200: notes.append('%s: %d%% inside the wheels - decide by eye' % (m, ni * 100 // n))
            if ni < 0.9 * n: continue
            c, rm = float(np.mean(cov)), float(np.mean(rad))
            if re.search(r'call?iper', m, re.I) or (c <= 0.45 and 0.35 <= rm <= 0.8):
                notes.append('%s: looks like a brake caliper (covers %d%% of the circle at %.2f r) -> steers only' % (m, c * 100, rm)); continue
            spin.append(m)
        hubs = ','.join('[' + ','.join('%g' % round(float(v), 4) for v in h[:7]) + ']' for h in H)
        print('  %s:{hubs:[%s],spin:%s},' % (cid, hubs, json.dumps(sorted(spin), ensure_ascii=False, separators=(',', ':'))))
        for h, nm in zip(H, ('RL', 'RR', 'FL', 'FR')):
            print('    // %s tyre %s r %.3f width %.2f%s' % (nm, h[7], h[3], h[5] - h[4], ' turned %.0f deg in the model' % np.degrees(h[6]) if h[6] else ''))
        for s in notes: print('    //', s)


if __name__ == '__main__':
    if len(sys.argv) < 2: print(__doc__); sys.exit(1)
    main()
