#!/usr/bin/env python3
"""List course records (overall No.1 of each course, any car) that were set recently, from the shared ranking.

usage: python3 tools/course_records.py <dump dir> [minutes]      (default: 62)

<dump dir> holds the artifact's records documents as JSON files, as ArtifactData action "list" with out_dir writes
them (<dump dir>/records/<uid>.json, each {"id":..,"data":{"players":[...]}} or the bare document).
Prints one line per course whose No.1 time was set within the last <minutes>; nothing when there is none.
Ranking rules follow the game (rankFor in site/index.html): valid times 5-3600 s, known course and car ids,
fastest time first, earlier record wins a tie. Used by the hourly scheduled task that pushes a phone notification.
"""
import glob, json, os, re, sys, time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'site', 'index.html')


def names():
    s = open(ROOT, encoding='utf8').read()
    cars = dict(re.findall(r"\{id:'([^']+)'(?:,[a-z]+:\d)*,maker:'[^']*',name:'([^']*)'", s))
    courses = {}
    i = s.index('const COURSES=[')
    for m in re.finditer(r"\{id:'([^']+)',name:'([^']*)'", s[i:]):
        courses.setdefault(m.group(1), m.group(2))
    return courses, cars


def fmt(t):
    m, sec = divmod(t, 60)
    return '%d:%06.3f' % (m, sec) if m else '%.3f' % sec


def main():
    d = sys.argv[1]; minutes = float(sys.argv[2]) if len(sys.argv) > 2 else 62
    courses, cars = names(); best = {}
    for f in glob.glob(os.path.join(d, '**', '*.json'), recursive=True):
        try:
            j = json.load(open(f, encoding='utf8'))
        except Exception:
            continue
        doc = j.get('data', j) if isinstance(j, dict) else None
        if not isinstance(doc, dict) or not isinstance(doc.get('players'), list):
            continue
        for p in doc['players'][:20]:
            name = str((p or {}).get('name') or '').strip()[:16]
            if not name or not isinstance(p.get('best'), dict):
                continue
            for k, r in p['best'].items():
                if '__' not in k or not isinstance(r, dict):
                    continue
                cid, car = k.split('__', 1); t = r.get('t'); at = r.get('at') or 0
                if cid not in courses or car not in cars or not isinstance(t, (int, float)) or not 5 < t < 3600:
                    continue
                cur = best.get(cid)
                if cur is None or (t, at) < (cur[0], cur[1]):
                    best[cid] = (t, at, name, car)
    since = (time.time() - minutes * 60) * 1000
    for cid, (t, at, name, car) in sorted(best.items(), key=lambda x: -x[1][1]):
        if at >= since:
            print('%s：%s さんが %s（%s）でコースレコード' % (courses[cid], name, fmt(t), cars[car]))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    main()
