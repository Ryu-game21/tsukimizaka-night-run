"""Where can the car really go, and how high is the ground there? Scan a scanned circuit's model across the track.

usage: python3 tools/ground_scan.py <course id> [out.json]
  reads work/ground/<id>.course.json (made by work/ground/export.js from site/index.html) and site/tracks/<id>/
  writes site/tracks/<id>/ground.json = {v, step, lat, wp[], wn[], dz:"<base64 zlib int8 rows>"} and prints a report.

Why: the game used to put the car on the road plane (centre height + bank x offset) all the way out to one wall
distance RW = max(hw + runoff, rw), the same on both sides. Off the asphalt the real ground is often lower (gravel
traps, grass slopes) or higher (kerbs, berms), so the car floated or sank, and a wall on one side and open run-off on
the other could not both be right: it drove through barriers on one side and hit an invisible wall on the other.

For every course point and lateral offset (every `lat` m out to +-MAXO) this casts a vertical ray into the model and
takes the top walkable surface (normal.y > 0.55; decal layers count as ground, fences/trees/glass as barriers) within [road plane - 4 m, + 2.5 m] - so a
bridge deck above the road is ignored and the road on a bridge stays the road. dy = ground - road plane.
Going outwards from the centre on each side, the first of these ends the drivable area (wl/wr = distance of the wall):
  - a barrier: a steep triangle (normal.y < 0.5) crossing the scan between 0.35 m and 1.2 m above the ground
  - a step up > 0.45 m or a drop > 1.2 m between neighbouring samples, or no ground at all (the edge of the model)
  - a slope steeper than ~35 degrees over 2 m
  - another part of the circuit closer than this one (hairpins, parallel straights)
The wall is never inside the band (hw + 0.3) - an obstacle inside the band is reported, not obeyed.
"""
import base64, json, os, sys, struct, zlib
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glblib import triangles  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
LAT = 0.5          # lateral sample step (m)
MAXO = 45.0        # furthest scan from the centre line (m)
GAP = 3.0          # longest crack between meshes that still counts as ground (m)
STORE = 1.0        # lateral step of the stored height grid (m)
CELL = 4.0


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


def load_model(url):
    d = os.path.join(ROOT, 'site', os.path.dirname(url)); J = json.load(open(os.path.join(ROOT, 'site', url)))
    B = b''.join(png_bytes(os.path.join(d, p['file']), p['bytes']) for p in J['extras']['geoPng'])
    parts = triangles(J, B)   # everything: decals on the asphalt are ground, fences / glass / trees are barriers
    names = sorted(set(m for m, _, _ in parts)); mid = np.concatenate([np.full(len(t), names.index(m)) for m, t, _ in parts])
    alpha = {m.get('name'): m.get('alphaMode', 'OPAQUE') for m in J['materials']}
    load_model.decal = {k for k, nm in enumerate(names) if alpha.get(nm, 'OPAQUE') != 'OPAQUE'}   # tyre marks, lines
    return np.concatenate([t for _, t, _ in parts]).astype(np.float64), mid, names


class Grid:
    def __init__(self, V, mid):
        self.V = V; e1 = V[:, 1] - V[:, 0]; e2 = V[:, 2] - V[:, 0]; n = np.cross(e1, e2)
        ln = np.linalg.norm(n, axis=1); ok = ln > 1e-9; self.V = V = V[ok]; self.mid = mid[ok]; n = n[ok] / ln[ok, None]
        self.ny = np.abs(n[:, 1]); self.ymin = V[:, :, 1].min(1); self.ymax = V[:, :, 1].max(1)
        lo = np.floor(V[:, :, [0, 2]].min(1) / CELL).astype(int); hi = np.floor(V[:, :, [0, 2]].max(1) / CELL).astype(int)
        span = (hi - lo + 1).prod(1); big = span > 400
        self.big = np.nonzero(big)[0]; self.cells = {}
        idx = np.nonzero(~big)[0]
        cnt = span[idx]; rep = np.repeat(idx, cnt)
        start = np.repeat(np.cumsum(cnt) - cnt, cnt); k = np.arange(len(rep)) - start
        w = (hi[rep, 0] - lo[rep, 0] + 1)
        cx = lo[rep, 0] + k % w; cz = lo[rep, 1] + k // w
        key = cx.astype(np.int64) * 1000003 + cz
        order = np.argsort(key, kind='stable'); key = key[order]; rep = rep[order]
        u, first = np.unique(key, return_index=True); last = np.r_[first[1:], len(key)]
        self.keys = dict(zip(u.tolist(), zip(first.tolist(), last.tolist()))); self.rep = rep

    def cand(self, xs, zs):
        """candidate triangle ids for points (pairs: point index, tri index)"""
        cx = np.floor(xs / CELL).astype(np.int64); cz = np.floor(zs / CELL).astype(np.int64); key = cx * 1000003 + cz
        pi, ti = [], []
        for j, k in enumerate(key.tolist()):
            r = self.keys.get(k)
            if r: t = self.rep[r[0]:r[1]]; ti.append(t); pi.append(np.full(len(t), j))
            if len(self.big): ti.append(self.big); pi.append(np.full(len(self.big), j))
        if not ti: return np.zeros(0, int), np.zeros(0, int)
        return np.concatenate(pi), np.concatenate(ti)

    def heights(self, xs, zs, lo, hi, mat=False, lowest=False):
        """top walkable surface height in [lo, hi] at each (x, z); nan where none (mat: also the material id there, -1)"""
        pi, ti = self.cand(xs, zs); out = np.full(len(xs), np.nan)
        if not len(pi): return (out, np.full(len(xs), -1)) if mat else out
        V = self.V[ti]; px = xs[pi]; pz = zs[pi]
        x0, z0 = V[:, 0, 0], V[:, 0, 2]; x1, z1 = V[:, 1, 0] - x0, V[:, 1, 2] - z0; x2, z2 = V[:, 2, 0] - x0, V[:, 2, 2] - z0
        d = x1 * z2 - x2 * z1; ok = np.abs(d) > 1e-12; d = np.where(ok, d, 1)
        qx, qz = px - x0, pz - z0; u = (qx * z2 - x2 * qz) / d; v = (x1 * qz - qx * z1) / d
        ins = ok & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6) & (self.ny[ti] > 0.55)
        y = V[:, 0, 1] + u * (V[:, 1, 1] - V[:, 0, 1]) + v * (V[:, 2, 1] - V[:, 0, 1])
        ins &= (y >= lo[pi]) & (y <= hi[pi])
        if ins.any():
            (np.fmin if lowest else np.fmax).at(out, pi[ins], y[ins])
        if mat:
            # the top opaque surface (tyre marks / lines are see-through decals on the asphalt)
            dec = np.isin(self.mid[ti], list(getattr(load_model, 'decal', ()))); i2 = ins & ~dec; o2 = np.full(len(xs), np.nan)
            if i2.any(): np.fmax.at(o2, pi[i2], y[i2])
            m = np.full(len(xs), -1); top = i2 & (y >= o2[pi] - 1e-9); m[pi[top]] = self.mid[ti[top]]
            return out, m
        return out

    def barrier(self, ax, az, bx, bz, ga, gb):
        """does a steep triangle cross the segment a->b (xz) between ground+0.35 and ground+1.2? per segment bool"""
        mx, mz = (ax + bx) / 2, (az + bz) / 2
        pi, ti = self.cand(mx, mz); hit = np.zeros(len(ax), bool)
        if not len(pi): return hit
        st = self.ny[ti] < 0.5; pi, ti = pi[st], ti[st]
        g = np.maximum(ga, gb)[pi]; lo = np.minimum(ga, gb)[pi]
        keep = (self.ymax[ti] > lo + 0.35) & (self.ymin[ti] < g + 1.2); pi, ti = pi[keep], ti[keep]
        if not len(pi): return hit
        V = self.V[ti][:, :, [0, 2]]
        A = np.c_[ax[pi], az[pi]]; Bp = np.c_[bx[pi], bz[pi]]
        def seg(p, q, r, s):
            d1 = q - p; d2 = s - r; den = d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]; den = np.where(np.abs(den) < 1e-12, 1e-12, den)
            w = r - p; t = (w[:, 0] * d2[:, 1] - w[:, 1] * d2[:, 0]) / den; u = (w[:, 0] * d1[:, 1] - w[:, 1] * d1[:, 0]) / den
            return (t >= 0) & (t <= 1) & (u >= 0) & (u <= 1)
        x = seg(A, Bp, V[:, 0], V[:, 1]) | seg(A, Bp, V[:, 1], V[:, 2]) | seg(A, Bp, V[:, 2], V[:, 0])
        hit[np.unique(pi[x])] = True
        return hit


def main():
    cid = sys.argv[1]; c = json.load(open(os.path.join(ROOT, 'work/ground', cid + '.course.json')))
    P = np.array(c['pts'], float).reshape(-1, 3); n = len(P); hw = np.array(c['hw'], float); bank = np.array(c['bank'], float)
    rw_old = hw + c['runoff']
    if c.get('rw'): rw_old = np.maximum(rw_old, np.array(c['rw'], float))
    T = np.roll(P, -1, 0) - np.roll(P, 1, 0); T[:, 1] = 0; T /= np.linalg.norm(T, axis=1, keepdims=True)
    NRm = np.c_[T[:, 2], np.zeros(n), -T[:, 0]]           # same as the game: NR = (t.z, 0, -t.x)
    V, mid, names = load_model(c['model']); G = Grid(V, mid); kd = cKDTree(P[:, [0, 2]])
    offs = np.arange(LAT, MAXO + 1e-9, LAT); no = len(offs)
    S = int(MAXO / STORE); wl = np.zeros(n); wr = np.zeros(n); dyg = np.zeros((n, 2 * S + 1)); flg = np.full((n, 2 * S + 1), np.nan); rep = {'inband': [], 'dyband': []}
    for k in range(n):
        for side, sg in ((0, 1), (1, -1)):
            o = sg * offs; xs = P[k, 0] + NRm[k, 0] * o; zs = P[k, 2] + NRm[k, 2] * o; yp = P[k, 1] + bank[k] * o
            # the ground at the centre too (start of the scan)
            g = G.heights(np.r_[P[k, 0], xs], np.r_[P[k, 2], zs], np.r_[P[k, 1] - 1.5, yp - 4], np.r_[P[k, 1] + 1.0, yp + 2.5])
            g0, g = g[0], g[1:]
            # a short run of missing samples (up to GAP m) with ground at about the same height on both sides is a crack
            # between meshes of the (simplified) model, not the edge of the world (Suzuka turn 1: the asphalt and the
            # grass don't meet - the game fills the crack with a dark sheet, groundUnder)
            nanm = np.isnan(g); j = 0
            while j < no:
                if not nanm[j]: j += 1; continue
                e = j
                while e < no and nanm[e]: e += 1
                a = g[j - 1] if j > 0 else g0
                if e < no and (e - j) * LAT <= GAP and not np.isnan(a) and abs(g[e] - a) < 0.3:
                    g[j:e] = a + (g[e] - a) * (np.arange(j, e) - j + 1) / (e - j + 1)
                j = e
            if np.isnan(g0): g0 = P[k, 1]
            # another stretch of the circuit closer than this one?
            dd, jj = kd.query(np.c_[xs, zs]); di = np.minimum(np.abs(jj - k), n - np.abs(jj - k))
            other = (di > 12) & (dd < np.abs(o) - 0.5)
            gp = np.r_[g0, g[:-1]]; ax = np.r_[P[k, 0], xs[:-1]]; az = np.r_[P[k, 2], zs[:-1]]
            bar = G.barrier(ax, az, xs, zs, np.nan_to_num(gp, nan=g0), np.nan_to_num(g, nan=g0))
            step = np.nan_to_num(g - gp, nan=0)
            g2 = np.r_[np.full(4, np.nan), g][:-4]; slope = np.nan_to_num(np.abs(g - g2) / 2.0, nan=0) > 0.7
            stop = np.isnan(g) | bar | (step > 0.45) | (step < -1.2) | slope | other
            band = hw[k] + 0.3
            first = np.argmax(stop) if stop.any() else no
            dist = offs[first] - LAT if first < no else MAXO
            if dist < band:
                rep['inband'].append((k, int(sg), round(float(offs[first]), 1), 'void' if np.isnan(g[first]) else 'bar' if bar[first] else 'step' if abs(step[first]) > .45 else 'slope' if slope[first] else 'other'))
                dist = band
            (wl if side == 0 else wr)[k] = dist
            dy = np.nan_to_num(g - yp, nan=0); dy[offs > dist + 1] = 0
            if first < no: dy[first:] = 0          # the top of a barrier / kerb wall is not ground
            inb = (offs <= hw[k]) & (np.arange(no) < first)
            if inb.any() and np.abs(dy[inb]).max() > 0.25: rep['dyband'].append((k, int(sg), round(float(np.abs(dy[inb]).max()), 2)))
            # store at 1 m: index S is the centre, +j = this side's offset j m
            # floor for the game's crack sheet (groundUnder): the LOWEST surface at each offset out to MAXO, walls or not,
            # short gaps bridged like above; nan where there is nothing (the end of the model: no sheet there)
            fl = G.heights(xs, zs, yp - 6, yp + 6, lowest=True) - yp; nm = np.isnan(fl); j = 0
            while j < no:
                if not nm[j]: j += 1; continue
                e = j
                while e < no and nm[e]: e += 1
                a = fl[j - 1] if j > 0 else 0.0
                if e < no and (e - j) * LAT <= GAP and not np.isnan(a) and abs(fl[e] - a) < 0.3: fl[j:e] = np.minimum(a, fl[e])
                j = e
            flg[k, S] = 0.0 if np.isnan(flg[k, S]) else flg[k, S]
            for j in range(1, S + 1):
                m = np.abs(offs - j * STORE) < 1e-6
                if m.any():
                    dyg[k, S + sg * j] = dy[m][0]
                    # lowest of the samples within +-1 m, so the sheet between stored points stays under the ground
                    w = np.abs(offs - j * STORE) <= 1.0 + 1e-6; flg[k, S + sg * j] = np.min(fl[w]) if not np.isnan(fl[w]).any() else np.nan
    # the points are 4 m apart: a barrier seen at one point also holds at its neighbours (no slipping through between)
    band = hw + 0.3
    wl = np.maximum(band, np.minimum.reduce([np.roll(wl, -1), wl, np.roll(wl, 1)]))
    wr = np.maximum(band, np.minimum.reduce([np.roll(wr, -1), wr, np.roll(wr, 1)]))
    # walls are on the +NR side (wl) and -NR side (wr): + offset = NR = left/right as the game's pl.off sign
    q = np.clip(np.round(dyg / 0.05), -127, 127).astype(np.int8)
    # the floor rows: also the lowest of the neighbouring points (4 m apart), in 0.05 m; -128 = no floor / out of range
    fm = np.fmin(np.fmin(np.roll(flg, 1, 0), np.roll(flg, -1, 0)), flg); bad = np.isnan(fm) | (fm < -6.3) | (fm > 6.3)
    fq = np.where(bad, -128, np.clip(np.floor(np.nan_to_num(fm) / 0.05), -127, 127)).astype(np.int8)
    # the asphalt: the most common top surface across the band (the game lays the crack-filling sheet in it)
    ks = np.arange(0, n, 3); fr = np.array([-0.6, -0.3, 0, 0.3, 0.6])
    o = (hw[ks, None] * fr[None]).ravel(); kk = np.repeat(ks, len(fr))
    _, mm = G.heights(P[kk, 0] + NRm[kk, 0] * o, P[kk, 2] + NRm[kk, 2] * o, P[kk, 1] + bank[kk] * o - 0.5, P[kk, 1] + bank[kk] * o + 0.5, mat=True)
    cnt = np.bincount(mm[mm >= 0], minlength=len(names)); cnt[list(load_model.decal)] = 0; road = names[int(cnt.argmax())]
    # and what lies just outside it (grass, mostly): the sheet takes this beyond the band, so a crack at the edge of the
    # asphalt reads as the grass running up to it
    fr2 = np.array([2.0, 3.5, 5.0]); o2 = np.r_[(hw[ks, None] + fr2[None]).ravel(), -(hw[ks, None] + fr2[None]).ravel()]; k2 = np.r_[np.repeat(ks, 3), np.repeat(ks, 3)]
    _, m2 = G.heights(P[k2, 0] + NRm[k2, 0] * o2, P[k2, 2] + NRm[k2, 2] * o2, P[k2, 1] + bank[k2] * o2 - 1.5, P[k2, 1] + bank[k2] * o2 + 0.5, mat=True)
    c2 = np.bincount(m2[m2 >= 0], minlength=len(names)); c2[list(load_model.decal)] = 0; c2[names.index(road)] = 0; side = names[int(c2.argmax())]
    out = {'v': 1, 'step': STORE, 'road': road, 'side': side, 'lat': S, 'wp': np.round(wl, 1).tolist(), 'wn': np.round(wr, 1).tolist(),
           'dz': base64.b64encode(zlib.compress(q.tobytes(), 9)).decode(),
           'fl': base64.b64encode(zlib.compress(np.ascontiguousarray(fq[:, 1::2]).tobytes(), 9)).decode()}   # every 2 m: offsets -(S-1)..S-1   # zlib (deflate) of the int8 rows
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'site', os.path.dirname(c['model']), 'ground.json')
    json.dump(out, open(dst, 'w'), separators=(',', ':'))
    # report against the old symmetric wall
    thr = np.minimum(wl, wr)
    pass_p = int(np.sum(rw_old - 1.05 > wl + 0.5)); pass_n = int(np.sum(rw_old - 1.05 > wr + 0.5))
    inv_p = int(np.sum(wl > rw_old + 3)); inv_n = int(np.sum(wr > rw_old + 3))
    S0 = S; within = []
    for k in range(n):
        for sg, w in ((1, rw_old[k]), (-1, rw_old[k])):
            js = np.arange(1, int(min(w, wl[k] if sg > 0 else wr[k])) + 1)
            if len(js): within.append(np.abs(dyg[k, S0 + sg * js]).max())
    within = np.array(within)
    print(f'{cid}: {n} pts | old wall drove through a barrier/edge at {pass_p}+{pass_n} side-points, '
          f'blocked open ground >3 m early at {inv_p}+{inv_n} | height off by >0.3 m inside the old wall at {int(np.sum(within > .3))} side-points (max {within.max():.2f} m) '
          f'| road {road} ({cnt.max() / max(1, cnt.sum()):.0%}) side {side} | obstacles inside the band {len(rep["inband"])} | band height off >0.25 m {len(rep["dyband"])} | {os.path.getsize(dst)/1e3:.0f} kB')
    if rep['inband']: print('  inside band:', rep['inband'][:12])
    if rep['dyband']: print('  band height:', rep['dyband'][:12])


if __name__ == '__main__':
    main()
