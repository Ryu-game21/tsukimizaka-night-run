"""Put a scanned circuit's centre line back between its white edge lines.

usage: python3 tools/recentre_lines.py <course id> [--write]
  reads work/ground/<id>.course.json (work/ground/export.js) and site/tracks/<id>/; writes
  work/ground/<id>.recentre.json = {pts, hw, bank, c (old offset of the new centre), how} and prints a report.
  --write also replaces <ID>_DATA in site/index.html (then: node work/ground/export.js, tools/ground_scan.py <id>,
  tools/tl_edges.py <id>).

Why (2026-11-01, Spa): the centre line was fitted to the rubbered groove decals and the paved band, and at several
corners it ran over the paved run-off instead of the track: Raidillon (up to 12 m over the asphalt run-off on the
outside), Bruxelles (the painted run-off on the inside), Pouhon (8-10 m inside, over the dark run-off) ...
The AI drove there, and the track-limit line (from the centre) was on the run-off while the real track was "outside".

For every point: a cross-section every 0.25 m (top opaque surface, as ground_scan.py) from -40 to +40 m; the white
lines (material name contains LINE) are found; candidates are pairs of neighbouring lines 7-24 m apart with the track's
own surface between them (>= 70 %), and a path search along the lap picks one per point (the rubbered groove decals - the
racing line - count most; at the top of Raidillon the pit-exit lane and the run-off are lined too).
Its middle c (offset along NR) is cleaned along the lap (a 7-point median; points off it by > 1.5 m, or wider than the
17-point median width + 2.5 m - a side road's line - dropped), gaps are
interpolated, and the new centre = old point + NR * c, smoothed and resampled every 4 m from the old start.
Height: the top surface at the new centre (within 2 m of the old height); bank: across +-40 % of the half-width;
hw = half the line-to-line width + 0.3 (capped 4.5-9, as the old fit; more put the pit wall next to the line inside it).
"""
import json, os, re, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ground_scan as gs  # noqa: E402
from tl_edges import classes  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
STEP = 0.25; MAXO = 40.0; DS = 4.0


def frame(P):
    n = len(P); T = np.roll(P, -1, 0) - np.roll(P, 1, 0); T[:, 1] = 0; T /= np.linalg.norm(T, axis=1, keepdims=True)
    return np.c_[T[:, 2], np.zeros(n), -T[:, 0]]


def corridor(G, Gg, P, NR, bank, tr, li, ke):
    """the track's white-line corridor (A, B offsets along NR) per point, nan where none: candidates are pairs of
    neighbouring lines 7-24 m apart with track surface between them; one per point is chosen by a path search along the
    lap (dynamic programming, up to 60 points may be skipped) that prefers rubber (the groove decals = where the cars
    really drive), a usual width, little sideways jumping, and - weakly - the old centre"""
    n = len(P); offs = np.arange(-MAXO, MAXO + 1e-9, STEP); cands = []
    for k in range(n):
        xs = P[k, 0] + NR[k, 0] * offs; zs = P[k, 2] + NR[k, 2] * offs; yp = P[k, 1] + bank[k] * offs
        _, m = G.heights(xs, zs, yp - 3, yp + 2, mat=True)
        rub = ~np.isnan(Gg.heights(xs, zs, yp - 3, yp + 2)) if Gg is not None else np.zeros(len(offs), bool)
        isl = (m >= 0) & li[np.maximum(m, 0)]; ist = (m >= 0) & (tr[np.maximum(m, 0)] | ke[np.maximum(m, 0)])
        runs = []; j = 0
        while j < len(offs):
            if isl[j]:
                e = j
                while e + 1 < len(offs) and isl[e + 1]: e += 1
                runs.append((j, e)); j = e + 1
            else: j += 1
        cs = []
        for (a0, a1), (b0, b1) in zip(runs, runs[1:]):
            x, y = offs[a1], offs[b0]; w = y - x
            if not 7 <= w <= 24 or ist[a1 + 1:b0].mean() < 0.7: continue
            d = 0 if x <= 0 <= y else min(abs(x), abs(y))
            if d <= 14: cs.append((x, y, rub[a1 + 1:b0].mean(), d))
        cands.append(cs)
    # path search, unrolled from the point with the most rubber in a corridor around the old centre
    s0 = max(range(n), key=lambda k: max([c[2] for c in cands[k] if c[3] == 0] or [-1]))
    order = [(s0 + i) % n for i in range(n)]; J = 60
    node = lambda c: 0.15 * abs(c[1] - c[0] - 11) + 2.0 * (1 - c[2]) + 0.3 * c[3]
    cost = [[None] * len(cands[k]) for k in order]; back = [[None] * len(cands[k]) for k in order]
    for a, c in enumerate(cands[order[0]]): cost[0][a] = node(c)
    for i in range(1, n):
        k = order[i]
        for b, cb in enumerate(cands[k]):
            best = (4.0 * i + 6, None) if i <= J else (1e18, None)   # start here (only near the seed)
            for j in range(1, min(J, i) + 1):
                for a, ca in enumerate(cands[order[i - j]]):
                    if cost[i - j][a] is None: continue
                    t = cost[i - j][a] + abs((cb[0] + cb[1]) - (ca[0] + ca[1])) / 2 + 0.3 * abs((cb[1] - cb[0]) - (ca[1] - ca[0])) + 4.0 * (j - 1)
                    if t < best[0]: best = (t, (i - j, a))
            cost[i][b] = best[0] + node(cb); back[i][b] = best[1]
    # end: the cheapest state in the last J points
    end = None; eb = 1e18
    for i in range(max(0, n - J), n):
        for a, v in enumerate(cost[i]):
            if v is not None and v + 4.0 * (n - 1 - i) < eb: eb = v + 4.0 * (n - 1 - i); end = (i, a)
    A = np.full(n, np.nan); B = np.full(n, np.nan)
    while end is not None:
        i, a = end; c = cands[order[i]][a]; A[order[i]], B[order[i]] = c[0], c[1]; end = back[i][a]
    return A, B


def fill(v):
    """interpolate nans around the closed lap"""
    n = len(v); ok = ~np.isnan(v)
    if not ok.any(): return np.zeros(n)
    i = np.arange(n); xi = np.r_[i[ok] - n, i[ok], i[ok] + n]; yi = np.r_[v[ok], v[ok], v[ok]]
    return np.interp(i, xi, yi)


def main():
    cid = sys.argv[1]
    c = json.load(open(os.path.join(ROOT, 'work/ground', cid + '.course.json')))
    P = np.array(c['pts'], float).reshape(-1, 3); n = len(P); hw = np.array(c['hw'], float); bank = np.array(c['bank'], float)
    NR = frame(P)
    V, mid, names = gs.load_model(c['model']); G = gs.Grid(V, mid); tr, li, ke = classes(names)
    gi = [i for i, nm in enumerate(names) if 'groove' in nm.lower()]; sel = np.isin(mid, gi)
    Gg = gs.Grid(V[sel], mid[sel]) if sel.any() else None
    A, B = corridor(G, Gg, P, NR, bank, tr, li, ke)
    cc = (A + B) / 2; w = B - A
    st = np.stack([np.roll(cc, s) for s in range(-3, 4)]); med = np.nanmedian(st, 0)
    wm = np.nanmedian(np.stack([np.roll(w, s) for s in range(-8, 9)]), 0)
    bad = (np.abs(cc - med) > 1.5) | (w > wm + 2.5); cc[bad] = np.nan; w[bad] = np.nan   # a side road's line (La Source exit)
    how = np.where(np.isnan(cc), 'fill', 'lines')
    cf = fill(cc); wf = fill(w)
    # smooth the offset (a 9-point triangle) - a step in c would kink the line
    ker = np.array([1, 2, 3, 4, 5, 4, 3, 2, 1], float); ker /= ker.sum()
    cs = sum(ker[i] * np.roll(cf, i - 4) for i in range(9)); ws = sum(ker[i] * np.roll(wf, i - 4) for i in range(9))
    Q = P[:, [0, 2]] + NR[:, [0, 2]] * cs[:, None]
    for _ in range(2):                                   # light smoothing of the 2D line
        Q = 0.25 * np.roll(Q, 1, 0) + 0.5 * Q + 0.25 * np.roll(Q, -1, 0)
    # resample every DS m from the projection of the old start
    seg = np.linalg.norm(np.roll(Q, -1, 0) - Q, axis=1); s = np.r_[0, np.cumsum(seg)]; Ltot = s[-1]
    m = int(round(Ltot / DS)); su = np.arange(m) * Ltot / m
    Qc = np.r_[Q, Q[:1]]
    X = np.interp(su, s, Qc[:, 0]); Z = np.interp(su, s, Qc[:, 1])
    Wn = np.interp(su, s, np.r_[ws, ws[:1]]); Y0 = np.interp(su, s, np.r_[P[:, 1], P[:1, 1]])
    ccn = np.interp(su, s, np.r_[cs, cs[:1]])
    P2 = np.c_[X, Y0, Z]; NR2 = frame(P2)
    hw2 = np.clip(Wn / 2 + 0.3, 4.5, 9.0)
    # heights: top surface at the centre and across the band
    fr = np.array([-0.4, 0, 0.4]); Yc = np.full(m, np.nan); bk = np.zeros(m)
    for k in range(m):
        o = fr * hw2[k]; xs = X[k] + NR2[k, 0] * o; zs = Z[k] + NR2[k, 2] * o
        h = G.heights(xs, zs, np.full(3, Y0[k] - 2), np.full(3, Y0[k] + 2))
        Yc[k] = h[1] if not np.isnan(h[1]) else np.nanmean(h) if not np.isnan(h).all() else Y0[k]
        if not np.isnan(h[0]) and not np.isnan(h[2]): bk[k] = (h[2] - h[0]) / (o[2] - o[0])
        else: bk[k] = np.nan
    Yc = np.where(np.isnan(Yc), Y0, Yc); bk = fill(bk)
    for _ in range(3):
        Yc = 0.25 * np.roll(Yc, 1) + 0.5 * Yc + 0.25 * np.roll(Yc, -1)
        bk = 0.25 * np.roll(bk, 1) + 0.5 * bk + 0.25 * np.roll(bk, -1)
    bk = np.clip(bk, -0.12, 0.12)
    out = {'pts': np.round(np.c_[X, Yc, Z], 2).ravel().tolist(), 'hw': np.round(hw2, 1).tolist(), 'bank': np.round(bk, 3).tolist(),
           'c': np.round(ccn, 2).tolist()}
    json.dump(out, open(os.path.join(ROOT, 'work/ground', cid + '.recentre.json'), 'w'))
    oldL = np.linalg.norm(np.roll(P, -1, 0) - P, axis=1).sum()
    print(f'{cid}: {n} -> {m} pts, length {oldL:.0f} -> {Ltot:.0f} m | corridor from lines at {int((how == "lines").sum())}/{n} pts | '
          f'old centre off the lines\' middle by >1.5 m at {int((np.abs(cs) > 1.5).sum())} pts (max {np.abs(cs).max():.1f} m) | '
          f'height change max {np.abs(Yc - Y0).max():.2f} m | hw {hw2.min():.1f}-{hw2.max():.1f}')
    runs = []; on = np.abs(cs) > 1.5; k = 0
    while k < n:
        if on[k]:
            e = k
            while e + 1 < n and on[e + 1]: e += 1
            runs.append(f'{k}-{e} ({np.abs(cs[k:e + 1]).max():.1f} m)'); k = e + 1
        else: k += 1
    print('  moved:', ', '.join(runs))
    if '--write' in sys.argv:
        name = cid.upper() + '_DATA'; f = os.path.join(ROOT, 'site/index.html'); src = open(f).read()
        fmt = lambda a, d: ','.join(f'{v:.{d}f}' for v in a)
        line = f"const {name}={{pts:[{fmt(out['pts'], 2)}],hw:[{fmt(out['hw'], 1)}],bank:[{fmt(out['bank'], 3)}]}};"
        src2, k = re.subn(r'^const ' + name + r'=\{.*\};$', lambda _: line, src, flags=re.M)
        assert k == 1, name; open(f, 'w').write(src2); print('wrote', name, 'in site/index.html')


if __name__ == '__main__':
    main()
