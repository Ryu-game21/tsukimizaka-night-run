/* Fetch a real road and the land around it for tools/real_course.py (2026-10-25, 箱根ターンパイク).
   The sandbox cannot reach OpenStreetMap or GSI, so this runs in a browser: open https://overpass-api.de/ , paste this into
   the console (or run it with the browser tool), then save the two JSON texts it prints into the page as
   work/<id>/raw.json and work/<id>/raw2.json (each line starts with BEGIN / ends with END; also offered as downloads).
   Set the four values below first: the way name (regex), a bounding box around it, and the end the course starts from.
   Data: road shape (c) OpenStreetMap contributors (ODbL); elevation: GSI tiles (dem5a z15, dem z14, wide area dem z12).
   Bridges (OSM bridge=yes) are flagged so the builder can lay the road over the valley the elevation model sees. */
const CFG = {name: 'ターンパイク', highway: 'tertiary', bbox: [35.17, 139.02, 35.27, 139.17], start: '35.2423553,139.1398212',
  wide: [138.70, 35.10, 139.25, 35.40]};   // wide: lon0, lat0, lon1, lat1 of the land drawn far away (250 m grid)
(async () => {
  const q = `[out:json][timeout:60];way["highway"](${CFG.bbox.join(',')})["name"~"${CFG.name}"];out tags geom;`;
  const J = await (await fetch('/api/interpreter', {method: 'POST', body: 'data=' + encodeURIComponent(q)})).json();
  const W = J.elements.filter(e => e.tags.highway === CFG.highway && e.tags.oneway !== 'yes');
  const k = p => p.lat.toFixed(7) + ',' + p.lon.toFixed(7), adj = {};
  W.forEach(w => {const a = k(w.geometry[0]), b = k(w.geometry[w.geometry.length - 1]); (adj[a] = adj[a] || []).push([w, b, 0]); (adj[b] = adj[b] || []).push([w, a, 1]);});
  let cur = CFG.start, used = new Set(), P = [];
  while (true) {const nx = (adj[cur] || []).find(z => !used.has(z[0].id)); if (!nx) break; used.add(nx[0].id);
    let g = nx[0].geometry.map(p => ({lat: p.lat, lon: p.lon, br: nx[0].tags.bridge ? 1 : 0})); if (nx[2]) g.reverse(); P.push(...(P.length ? g.slice(1) : g)); cur = nx[1];}
  const lat0 = P[0].lat, lon0 = P[0].lon, CX = Math.cos(lat0 * Math.PI / 180) * 111320, CZ = 110574, loc = p => [(p.lon - lon0) * CX, -(p.lat - lat0) * CZ];
  const L = P.map(loc); const S = [{x: L[0][0], z: L[0][1]}]; let acc = 0, need = 10;
  for (let i = 1; i < L.length; i++) {const [ax, az] = L[i - 1], [bx, bz] = L[i], d = Math.hypot(bx - ax, bz - az); let t0 = 0;
    while (acc + d * (1 - t0) >= need - 1e-9) {const t = t0 + (need - acc) / d; S.push({x: ax + (bx - ax) * t, z: az + (bz - az) * t}); acc = 0; need = 10; t0 = t; if (t0 >= 1) break;} acc += d * (1 - t0);}
  const C = {}, tile = (kind, z, x, y) => {const key = kind + z + '/' + x + '/' + y; if (!(key in C)) C[key] = fetch(`https://cyberjapandata.gsi.go.jp/xyz/${kind}/${z}/${x}/${y}.txt`)
      .then(r => r.ok ? r.text() : null).then(t => t && t.trim().split('\n').map(l => l.split(',').map(v => v === 'e' ? NaN : +v))); return C[key];};
  const px = (lon, z) => (lon + 180) / 360 * 2 ** z * 256, py = (lat, z) => {const r = lat * Math.PI / 180; return (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * 2 ** z * 256;};
  const val = async (kind, z, gx, gy) => {const t = await tile(kind, z, Math.floor(gx / 256), Math.floor(gy / 256)); return t ? t[gy % 256][gx % 256] : NaN;};
  const samp = async (kind, z, lat, lon) => {const X = px(lon, z) - .5, Y = py(lat, z) - .5, x0 = Math.floor(X), y0 = Math.floor(Y), fx = X - x0, fy = Y - y0;
    const v = await Promise.all([val(kind, z, x0, y0), val(kind, z, x0 + 1, y0), val(kind, z, x0, y0 + 1), val(kind, z, x0 + 1, y0 + 1)]); return v[0] * (1 - fx) * (1 - fy) + v[1] * fx * (1 - fy) + v[2] * (1 - fx) * fy + v[3] * fx * fy;};
  const H = async (x, z) => {const lat = lat0 - z / CZ, lon = lon0 + x / CX; let h = await samp('dem5a', 15, lat, lon); if (isNaN(h)) h = await samp('dem', 14, lat, lon); return h;};
  const batch = async (arr, f, n = 40) => {const out = []; for (let i = 0; i < arr.length; i += n) out.push(...await Promise.all(arr.slice(i, i + n).map(f))); return out;};
  const E = await batch(S, s => H(s.x, s.z));
  const nrm = i => {const a = S[Math.max(0, i - 2)], b = S[Math.min(S.length - 1, i + 2)], dx = b.x - a.x, dz = b.z - a.z, l = Math.hypot(dx, dz); return [-dz / l, dx / l];};
  const b64 = a => {let s = ''; for (const v of a) s += String.fromCharCode(v & 255); return btoa(s);};
  const def = async u8 => {const ab = await new Response(new Blob([u8]).stream().pipeThrough(new CompressionStream('deflate'))).arrayBuffer(); let s = ''; new Uint8Array(ab).forEach(v => s += String.fromCharCode(v)); return btoa(s);};
  // coarse sections every 40 m, -400..400 m, 4 m units relative to the road
  const XI = []; for (let i = 0; i < S.length; i += 4) XI.push(i); const OFF = []; for (let o = -400; o <= 400; o += 25) OFF.push(o);
  const xs = []; for (const i of XI) {const [nx, nz] = nrm(i); const row = await batch(OFF, o => H(S[i].x + nx * o, S[i].z + nz * o)); row.forEach(h => xs.push(Math.max(-127, Math.min(127, Math.round((isNaN(h) ? 0 : h - E[i]) / 4)))));}
  const ed = [0]; let prev = Math.round(E[0] * 10); for (let i = 1; i < E.length; i++) {let d = Math.max(-127, Math.min(127, Math.round(E[i] * 10) - prev)); ed.push(d); prev += d;}
  const nodes = P.map(p => {const [x, z] = loc(p); return Math.round(x * 10) + ',' + Math.round(z * 10) + (p.br ? ',1' : '');}).join(';');
  const raw = {lat0, lon0, e0: Math.round(E[0] * 10), nodes, ed: b64(ed), xsStep: 40, off: [-400, 25, 33], xs: b64(xs), nXs: XI.length};
  // fine sections every 20 m, +-7..50 m, 0.5 m units
  const FO = [7, 10, 14, 19, 25, 32, 40, 50], FA = [...FO.map(o => -o).reverse(), ...FO], fine = [];
  for (let i = 0; i < S.length; i += 2) {const [nx, nz] = nrm(i); const row = await batch(FA, o => H(S[i].x + nx * o, S[i].z + nz * o)); row.forEach(h => fine.push(Math.max(-127, Math.min(127, Math.round((h - E[i]) * 2)))));}
  // the wide area, 250 m grid, 16 m units, 0 = sea
  const [la, ba, lb, bb] = CFG.wide, x0 = Math.round((la - lon0) * CX / 250) * 250, x1 = Math.round((lb - lon0) * CX / 250) * 250, z0 = Math.round(-(bb - lat0) * CZ / 250) * 250, z1 = Math.round(-(ba - lat0) * CZ / 250) * 250;
  const nx = (x1 - x0) / 250 + 1, nz = (z1 - z0) / 250 + 1, g = new Uint8Array(nx * nz), v12 = async (lat, lon) => {const X = Math.floor(px(lon, 12)), Y = Math.floor(py(lat, 12)); return val('dem', 12, X, Y);};
  for (let j = 0; j < nz; j++) {const row = await batch(Array.from({length: nx}, (_, i) => i), i => v12(lat0 - (z0 + j * 250) / CZ, lon0 + (x0 + i * 250) / CX), 100);
    row.forEach((h, i) => g[j * nx + i] = isNaN(h) || h <= 0 ? 0 : Math.max(1, Math.min(255, Math.round(h / 16))));}
  const raw2 = {wide: {x0, z0, nx, nz, step: 250, unit: 16, b: await def(g)}, fine: {every: 20, offs: FO, unit: 0.5, n: Math.ceil(S.length / 2), b: await def(new Uint8Array(fine.map(v => v & 255)))}};
  document.body.innerHTML = ''; for (const [n, o] of [['raw.json', raw], ['raw2.json', raw2]]) {
    const t = JSON.stringify(o), pre = document.createElement('pre'); pre.textContent = 'BEGIN' + t + 'END'; document.body.appendChild(pre);
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([t], {type: 'application/json'})); a.download = n; a.textContent = n; document.body.appendChild(a);}
  console.log('route', (S.length - 1) * 10, 'm, nodes', P.length, ', climb', E[0].toFixed(0), '->', E[E.length - 1].toFixed(0));
})();
