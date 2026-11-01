"""Where is the edge of the track for the track-limit rule? Read it off the model's own markings.

usage: python3 tools/tl_edges.py <course id> [--dry]
  reads work/ground/<id>.course.json (work/ground/export.js) and site/tracks/<id>/, adds "tl" to
  site/tracks/<id>/ground.json (0.25 m units, uint8 pairs (+NR, -NR) per scan point, base64; 255 = no limit there)
  and writes work/ground/<id>.tl.npy (edges in m, nan = none) for tools/tl_view.py.

Why (2026-11-01, the user at Spa: "offences near the corners are odd - the model's road changes colour a lot"):
the game's line used to be the fitted half-width HW (capped at 9 m, and the centre line is not always in the middle
of the tarmac) widened by the paved distance pv (every opaque surface that makes up >= 3 % of the band: the run-off
asphalt too). At Raidillon the track is 17 m wide on one side (HW 9: offences on the track itself), elsewhere a
resurfaced patch, a painted run-off or a pit-exit lane sits right next to the white line.

For every scan point and side, walk out from the centre line (every 0.25 m, top opaque surface as ground_scan.py) over
the track's own surfaces (asphalt, resurfaced patches, drain grilles, cracks <= 0.5 m) until the first marker:
  - a white edge line: the edge is its outer side, and a kerb right after it (within 0.5 m) is still track
  - a kerb (without a line): its outer side
  - anything else (grass, gravel, painted run-off, walls, the end of the model): where the track surfaces ended
A line within hw - 2 m of the centre (a lane marking inside the track: pit-exit lines, a merging road; at least the first
metre) and a kerb in the first metre (the apex kerb of a hairpin) are stepped over.
Where no line or kerb ended the walk (a gap in the paint) and line-based edges are within 8 points on both sides, the edge
is interpolated from them.
Then the edges are tidied along the lap: a running median over 5 points (dashed lines, single gaps), and an edge
that is much narrower than both neighbours' is lifted to them (a stray marking).
Material classes come from the names (TRACK / LINE / KERB substrings below, override with env TRACK=,LINE=,KERB=).
"""
import base64, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ground_scan as gs  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
STEP = 0.25; MAXO = 40.0
TRACK = os.environ.get('TRACK', 'asph,road,grilles,groove').split(',')
NOT_TRACK = os.environ.get('NOT_TRACK', 'pitlane,road-ext').split(',')
LINE = os.environ.get('LINE', 'line').split(',')
KERB = os.environ.get('KERB', 'kerb,curb').split(',')


def classes(names):
    low = [n.lower() for n in names]
    line = np.array([any(k in s for k in LINE) for s in low])
    kerb = np.array([any(k in s for k in KERB) for s in low]) & ~line
    track = np.array([any(k in s for k in TRACK) and not any(k in s for k in NOT_TRACK) for s in low]) & ~line & ~kerb
    return track, line, kerb


def walk(m, tr, li, ke, inner=1.0):
    """m: material ids outwards (index j = (j+1)*STEP m); returns the edge distance and what ended it"""
    no = len(m); j = 0; last = 0.0; gap = 0
    isT = lambda q: q >= 0 and tr[q]
    while j < no:
        q = m[j]; d = (j + 1) * STEP
        if q >= 0 and li[q] and d > inner:
            e = j
            while e + 1 < no and m[e + 1] >= 0 and li[m[e + 1]]: e += 1
            edge = (e + 1) * STEP; k = e + 1; miss = 0
            while k < no and miss <= 2:                      # a kerb right after the line is still track
                if m[k] >= 0 and ke[m[k]]: edge = (k + 1) * STEP; miss = 0
                elif edge > (e + 1) * STEP: break
                else: miss += 1
                k += 1
            return edge, 'line'
        if q >= 0 and ke[q] and d > min(inner, 1.0):
            e = j
            while e + 1 < no and ((m[e + 1] >= 0 and (ke[m[e + 1]] or li[m[e + 1]]))): e += 1
            return (e + 1) * STEP, 'kerb'
        if isT(q) or (q >= 0 and (li[q] or ke[q])): last = d; gap = 0
        else:
            gap += 1
            if gap * STEP > 0.5: return last, 'surface'
        j += 1
    return np.nan, 'none'


def main():
    cid = sys.argv[1]; dry = '--dry' in sys.argv
    c = json.load(open(os.path.join(ROOT, 'work/ground', cid + '.course.json')))
    P = np.array(c['pts'], float).reshape(-1, 3); n = len(P); hw = np.array(c['hw'], float); bank = np.array(c['bank'], float)
    T = np.roll(P, -1, 0) - np.roll(P, 1, 0); T[:, 1] = 0; T /= np.linalg.norm(T, axis=1, keepdims=True)
    NRm = np.c_[T[:, 2], np.zeros(n), -T[:, 0]]
    V, mid, names = gs.load_model(c['model']); G = gs.Grid(V, mid)
    tr, li, ke = classes(names)
    print('track:', [names[i] for i in np.nonzero(tr)[0]]); print('line:', [names[i] for i in np.nonzero(li)[0]]); print('kerb:', [names[i] for i in np.nonzero(ke)[0]])
    offs = np.arange(STEP, MAXO + 1e-9, STEP)
    E = np.full((n, 2), np.nan); why = np.empty((n, 2), object)
    for k in range(n):
        for sd, sg in ((0, 1), (1, -1)):
            o = sg * offs; xs = P[k, 0] + NRm[k, 0] * o; zs = P[k, 2] + NRm[k, 2] * o; yp = P[k, 1] + bank[k] * o
            _, m = G.heights(xs, zs, yp - 3, yp + 2, mat=True)
            E[k, sd], why[k, sd] = walk(m, tr, li, ke, max(1.0, hw[k] - 2.0))
    # where no line or kerb ended the walk (a gap in the paint), take the line-based edges around it (within 8 points)
    for sd in range(2):
        ok = np.isin(why[:, sd], ('line', 'kerb')); idx = np.arange(n)
        if ok.sum() > 2:
            xi = np.r_[idx[ok] - n, idx[ok], idx[ok] + n]; yi = np.tile(E[ok, sd], 3)
            for k in np.nonzero(~ok)[0]:
                a = xi[xi < k].max(); b = xi[xi > k].min()
                if b - a <= 16: E[k, sd] = np.interp(k, xi, yi)
    # tidy along the lap
    for sd in range(2):
        e = E[:, sd]; st = np.stack([np.roll(e, s) for s in range(-2, 3)]); med = np.nanmedian(st, 0)
        lo = np.minimum(np.roll(med, 1), np.roll(med, -1)); med = np.where(med < lo - 1.5, lo, med)
        # a short bulge (a side road or the paddock entrance breaks the line, the walk ends at the next one): back to the
        # median of the 17 points around
        big = np.nanmedian(np.stack([np.roll(med, s) for s in range(-8, 9)]), 0); med = np.where(med > big + 2.5, big, med)
        E[:, sd] = med
    np.save(os.path.join(ROOT, 'work/ground', cid + '.tl.npy'), E)
    from collections import Counter
    print(cid, n, 'pts | ended by', dict(Counter(why.ravel())), '| no edge', int(np.isnan(E).sum()),
          '| edge-hw median %.2f, <hw-2: %d, >hw+2: %d side-points' % (np.nanmedian(E - hw[:, None]), int(np.nansum(E < hw[:, None] - 2)), int(np.nansum(E > hw[:, None] + 2))))
    if dry: return
    dst = os.path.join(ROOT, 'site', os.path.dirname(c['model']), 'ground.json'); g = json.load(open(dst))
    q = np.where(np.isnan(E), 255, np.clip(np.round(E / 0.25), 0, 254)).astype(np.uint8)
    g['tl'] = base64.b64encode(q.tobytes()).decode()       # 0.25 m, pairs (+NR, -NR), 255 = no edge found
    json.dump(g, open(dst, 'w'), separators=(',', ':'))
    print('wrote', dst)


if __name__ == '__main__':
    main()
