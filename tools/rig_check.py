#!/usr/bin/env python3
"""Real-renderer check of the car motion rig (wheels cut out of the body, spin/steer, body roll).

usage: python3 tools/rig_check.py <car id>[,<car id>...] [out_dir]      (default out_dir: work/rig)

Needs Playwright with Chromium and three.js r128 on disk (the CDN is not reachable from the sandbox):
  git clone --depth 1 --branch r128 --filter=blob:none --sparse https://github.com/mrdoob/three.js work/three
  (cd work/three && git sparse-checkout set build examples/js/loaders)
  or set THREE_DIR to an existing copy.

For each car it prints JSON and writes <out_dir>/<id>.png:
  restDiff   pixels that differ between the original model and the rigged one at rest (wheels at the model's own
             angle) over 4 views - should be ~0 (a few anti-aliasing pixels at most)
  spinOutR/L pixels outside the wheel circles that change when the wheels spin 1 rad (side views) - must be 0
  spinInR/L  share of the wheel circle that changes (low = dark/plain rims, or spin materials missing - look)
  fixed      triangles of spinning materials kept still as brake calipers (connected piece covering a sector)
  mb         memory of the cut-out wheel meshes
The sheet: side rest / side spun / roll+pitch+steer, front-left rest / spun, rear-left spun, front wheel steered
both ways, and a tint (green = spins, orange = steers only). Look at every sheet: calipers must not turn with the
rim, no body panel or arch liner may move with a wheel.
"""
import asyncio, base64, functools, http.server, json, os, sys, threading
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
SITE = os.path.join(ROOT, 'site'); THREE = os.environ.get('THREE_DIR', os.path.join(ROOT, 'work', 'three'))


class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

    def guess_type(self, path):
        t = super().guess_type(path)
        return t + '; charset=utf-8' if t.startswith('text/') or t == 'application/javascript' else t

    def do_GET(self):
        if self.path.split('?')[0] == '/__rig.html':   # the game with a hook that evaluates inside its closure
            s = open(os.path.join(SITE, 'index.html'), encoding='utf8').read()
            a = '<script>\n(()=>{\n'; s = s.replace(a, a + 'window.__ev=s=>eval(s);\n', 1)
            b = s.encode(); self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b); return
        return super().do_GET()


async def main(ids, out):
    os.makedirs(out, exist_ok=True)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(H, directory=SITE))
    threading.Thread(target=srv.serve_forever, daemon=True).start(); port = srv.server_address[1]
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        pg = await b.new_page(viewport={'width': 1280, 'height': 720})

        async def route(r):
            u = r.request.url
            if 'three.min.js' in u: await r.fulfill(path=os.path.join(THREE, 'build', 'three.min.js'), content_type='application/javascript')
            elif 'GLTFLoader.js' in u: await r.fulfill(path=os.path.join(THREE, 'examples', 'js', 'loaders', 'GLTFLoader.js'), content_type='application/javascript')
            elif '127.0.0.1' in u: await r.continue_()
            else: await r.abort()
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:%d/__rig.html' % port); await pg.wait_for_timeout(4000)
        await pg.evaluate("s=>{window.__insp=__ev(s)}", open(os.path.join(HERE, 'rig_check.js'), encoding='utf8').read())
        for i in ids:
            r = await pg.evaluate("id=>window.__insp(id)", i)
            open(os.path.join(out, i + '.png'), 'wb').write(base64.b64decode(r.pop('sheet').split(',')[1]))
            print(json.dumps(r), flush=True)
        await b.close()


if __name__ == '__main__':
    if len(sys.argv) < 2: print(__doc__); sys.exit(1)
    asyncio.run(main(sys.argv[1].split(','), sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'work', 'rig')))
