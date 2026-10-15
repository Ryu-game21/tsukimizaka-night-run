#!/usr/bin/env python3
"""Fetch every course's current weather from Open-Meteo and write the shared `weather/now` document.

usage: python3 tools/fetch_weather.py [out.json]      (default: weather_now.json)

The Claude build of the game cannot reach other sites, so a scheduled task runs this script hourly and
writes the output to the artifact's shared store (collection "weather", doc "now") with ArtifactData.
The course list and the mapping mirror REAL_LOC / parseOpenMeteo / wmoToWx in site/index.html.

The output always has `status`:
  ok     - courses filled
  limit  - Open-Meteo's request limit was hit (HTTP 429 or a "limit" reason)
  error  - any other failure (network, HTTP error, bad JSON)
On ok the file is the whole document (write it with "set"); on limit/error it holds only status, msg and
checked (write it with "update", so the last good courses and `at` stay in place).
Exit code: 0 ok, 2 limit, 1 error. Data: Open-Meteo.com (CC BY 4.0, non-commercial free tier).
"""
import json, re, sys, time, urllib.request, urllib.error

LOC = {  # same order as REAL_LOC in index.html
    'tsukimi': (35.232, 139.106), 'kirifuri': (36.773, 139.623), 'wangan': (35.619, 139.781), 'kaigan': (35.300, 139.480),
    'spa': (50.437, 5.971), 'suzuka': (34.843, 136.541), 'nurburgring': (50.335, 6.947), 'shanghai': (31.338, 121.220),
    'bahrain': (26.032, 50.511), 'albertpark': (-37.850, 144.968), 'hungaroring': (47.582, 19.250), 'bugatti': (47.956, 0.208),
    'monza': (45.620, 9.281), 'silverstone': (52.073, -1.014), 'catalunya': (41.570, 2.261), 'madring': (40.465, -3.616),
    'zandvoort': (52.389, 4.541), 'marinabay': (1.291, 103.864), 'yas': (24.467, 54.603),
}


def wmo_to_wx(code, cloud, precip):
    code = code or 0
    if code in (45, 48):
        return 'fog'
    if 51 <= code <= 67 or 71 <= code <= 86 or code >= 95 or (precip or 0) > 0.2:
        return 'rain'
    return 'cloudy' if (cloud or 0) >= 70 or code == 3 else 'clear'


def mins(s):
    m = re.search(r'T(\d+):(\d+)', s or '')
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def parse(arr):
    out = {}
    for k, cid in enumerate(LOC):
        r = arr[k] if k < len(arr) else None
        if not r or 'current' not in r:
            continue
        cu, dl = r['current'], r.get('daily') or {}
        t = mins(cu.get('time'))
        a = mins((dl.get('sunrise') or [None])[0])
        b = mins((dl.get('sunset') or [None])[0])
        if None not in (t, a, b) and (abs(t - a) <= 50 or abs(t - b) <= 50):
            tod = 'dusk'
        else:
            tod = 'day' if cu.get('is_day') else 'night'
        out[cid] = {'wx': wmo_to_wx(cu.get('weather_code'), cu.get('cloud_cover'), cu.get('precipitation')), 'time': tod,
                    'code': cu.get('weather_code'), 'temp': cu.get('temperature_2m'), 'wind': cu.get('wind_speed_10m'),
                    'dir': cu.get('wind_direction_10m'), 'gust': cu.get('wind_gusts_10m'), 'local': (cu.get('time') or '')[11:16]}
    return out


def main():
    dst = sys.argv[1] if len(sys.argv) > 1 else 'weather_now.json'
    lat = ','.join(str(v[0]) for v in LOC.values())
    lon = ','.join(str(v[1]) for v in LOC.values())
    url = ('https://api.open-meteo.com/v1/forecast?latitude=' + lat + '&longitude=' + lon +
           '&current=temperature_2m,precipitation,weather_code,cloud_cover,wind_speed_10m,wind_direction_10m,wind_gusts_10m,is_day'
           '&daily=sunrise,sunset&timezone=auto&wind_speed_unit=ms&forecast_days=1')
    doc = {'at': int(time.time() * 1000), 'src': 'open-meteo', 'courses': {}}
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            j = json.load(r)
        if isinstance(j, dict) and j.get('error'):
            raise ValueError(j.get('reason') or 'error')
        courses = parse(j if isinstance(j, list) else [j])
        if not courses:
            raise ValueError('no data')
        doc.update(status='ok', msg='', courses=courses)
    except urllib.error.HTTPError as e:
        reason = ''
        try:
            reason = json.loads(e.read().decode()).get('reason', '')
        except Exception:
            pass
        lim = e.code == 429 or 'limit' in reason.lower()
        doc.update(status='limit' if lim else 'error', msg=reason or ('HTTP %d' % e.code))
    except Exception as e:
        lim = 'limit' in str(e).lower()
        doc.update(status='limit' if lim else 'error', msg=str(e)[:200])
    if doc['status'] != 'ok':
        # a failed run keeps the last good courses/at in the shared doc: write it with ArtifactData "update"
        doc = {'status': doc['status'], 'msg': doc['msg'], 'checked': doc['at']}
    with open(dst, 'w') as f:
        json.dump(doc, f, ensure_ascii=False)
    print(doc['status'], doc['msg'], len(doc.get('courses', {})), 'courses ->', dst)
    sys.exit({'ok': 0, 'limit': 2}.get(doc['status'], 1))


if __name__ == '__main__':
    main()
