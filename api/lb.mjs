/* Shared ranking for the Vercel build (2026-11-12). The Claude build keeps its own board in Claude's shared
   database; this one is only for https://tsukimizaka-night-run.vercel.app.

   Storage: Upstash Redis (Vercel Marketplace) through its REST API - env KV_REST_API_URL / KV_REST_API_TOKEN
   (or UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN).
     recs          hash  uid -> records doc, the same shape as the Claude build's records/<uid>
                         ({players:[{name,best:{'<course>__<car>':{t,w,r,s,at}},prof}],updated})
     nm:<key>      uid that owns a player name (key = NFKC, lower case, no spaces): a name belongs to one player only
     un:<uid>      set of the names that uid registered
     tk:<sha256>   uid of a device token (the token itself never stored)
     rl:<uid|ip>:<minute>  write counter

   Who may write (the user: no tools, only the game): every POST
     - must come from a real browser session of the page: Vercel BotID (checkBotId; the page calls initBotId for
       POST /api/lb), so curl, scripts and headless automation are refused
     - must come from this site (Origin header) and carry the device token issued at registration
     - is rate limited (20 a minute per player, 10 registrations an hour per address)
     - and every lap time is checked: course and car must exist, and the time may not be faster than 80 % of the
       game's own gold time for that course x car (api/_gold.mjs, tools/gold_times.js) */
import { createHash, randomBytes } from 'node:crypto';
import { checkBotId } from 'botid/server';
import GOLD from './_gold.mjs';

const FLOOR = 0.8, MAX_NAMES = 5, NAME_MAX = 16, DOC_MAX = 60000;
const RURL = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
const RTOK = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;

async function redis(...cmds) {   // pipeline; returns the results in order
  const r = await fetch(RURL + '/pipeline', { method: 'POST', headers: { Authorization: 'Bearer ' + RTOK, 'Content-Type': 'application/json' }, body: JSON.stringify(cmds) });
  if (!r.ok) throw new Error('redis ' + r.status);
  const j = await r.json();
  return j.map(x => { if (x.error) throw new Error(x.error); return x.result; });
}
const json = (o, status = 200, extra = {}) => new Response(JSON.stringify(o), { status, headers: Object.assign({ 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }, extra) });
const sha = s => createHash('sha256').update(s).digest('hex');
const cleanName = v => String(v == null ? '' : v).replace(/[\u0000-\u001f\u007f]/g, '').replace(/\s+/g, ' ').trim().slice(0, NAME_MAX);
const nameKey = n => cleanName(n).normalize('NFKC').toLowerCase().replace(/\s+/g, '');
const num = v => typeof v === 'number' && isFinite(v);

export async function GET() {
  if (!RURL) return json({ error: 'storage' }, 503);
  const [h] = await redis(['HGETALL', 'recs']);
  const docs = {};
  for (let i = 0; i + 1 < (h || []).length; i += 2) { try { docs[h[i]] = JSON.parse(h[i + 1]); } catch (e) { } }
  return json({ docs }, 200, { 'Cache-Control': 'public, s-maxage=10, stale-while-revalidate=30' });
}

export async function POST(request) {
  if (!RURL) return json({ error: 'storage' }, 503);
  const host = request.headers.get('host'), origin = request.headers.get('origin') || '';
  if (!origin || new URL(origin).host !== host) return json({ error: 'origin' }, 403);
  const bot = await checkBotId({ advancedOptions: { headers: Object.fromEntries(request.headers) } }).catch(() => ({ isBot: true }));
  if (bot.isBot) return json({ error: 'bot' }, 403);
  let body; try { body = await request.json(); } catch (e) { return json({ error: 'body' }, 400); }
  if (!body || typeof body !== 'object') return json({ error: 'body' }, 400);
  const ip = (request.headers.get('x-forwarded-for') || '').split(',')[0].trim() || 'x';
  const minute = Math.floor(Date.now() / 60000);
  const tok = typeof body.token === 'string' && body.token.length >= 32 && body.token.length <= 64 ? body.token : null;
  let uid = null;
  if (tok) { [uid] = await redis(['GET', 'tk:' + sha(tok)]); if (!uid) return json({ error: 'token' }, 401); }

  if (body.op === 'register') {
    const name = cleanName(body.name), key = nameKey(name);
    if (!name || !key) return json({ error: 'name' }, 400);
    const [n] = await redis(['INCR', 'rl:reg:' + ip + ':' + Math.floor(minute / 60)], ['EXPIRE', 'rl:reg:' + ip + ':' + Math.floor(minute / 60), 3700]);
    if (n > 10) return json({ error: 'rate' }, 429);
    const [owner] = await redis(['GET', 'nm:' + key]);
    if (owner && owner !== uid) return json({ error: 'taken' }, 409);
    let token = tok;
    if (!uid) { uid = 'v' + randomBytes(12).toString('base64url'); token = randomBytes(32).toString('base64url'); }
    if (!owner) {
      const [cnt] = await redis(['SCARD', 'un:' + uid]);
      if (cnt >= MAX_NAMES) return json({ error: 'names' }, 409);
      const [okSet] = await redis(['SET', 'nm:' + key, uid, 'NX']);
      if (okSet !== 'OK') return json({ error: 'taken' }, 409);   // someone took it a moment ago
    }
    await redis(['SADD', 'un:' + uid, name], ['SET', 'tk:' + sha(token), uid]);
    return json({ uid, token: token === tok ? undefined : token, name });
  }

  if (body.op === 'save') {
    if (!uid) return json({ error: 'token' }, 401);
    const [n] = await redis(['INCR', 'rl:' + uid + ':' + minute], ['EXPIRE', 'rl:' + uid + ':' + minute, 120]);
    if (n > 20) return json({ error: 'rate' }, 429);
    const d = body.doc;
    if (!d || typeof d !== 'object' || !Array.isArray(d.players) || d.players.length > MAX_NAMES) return json({ error: 'doc' }, 400);
    if (JSON.stringify(d).length > DOC_MAX) return json({ error: 'size' }, 413);
    const [names, prevRaw] = await redis(['SMEMBERS', 'un:' + uid], ['HGET', 'recs', uid]);
    const mine = new Set((names || []).map(nameKey));
    let prev = null; try { prev = prevRaw ? JSON.parse(prevRaw) : null; } catch (e) { }
    const now = Date.now(), out = { players: [], updated: now };
    for (const p of d.players) {
      const name = cleanName(p && p.name);
      if (!name || !mine.has(nameKey(name))) return json({ error: 'name', name }, 403);
      const best = {}, pp = prev && Array.isArray(prev.players) ? prev.players.find(x => x && x.name === name) : null;
      for (const k in (p.best || {})) {
        const r = p.best[k], [cid, car] = String(k).split('__'), gold = GOLD[cid] && GOLD[cid][car];
        if (!gold || !r || !num(r.t) || r.t >= 3600) return json({ error: 'record', k }, 400);
        const old = pp && pp.best && pp.best[k];
        if (old && num(old.t) && old.t <= r.t) { best[k] = old; continue; }   // never replaced by a slower one
        if (r.t < gold * FLOOR) return json({ error: 'time', k }, 422);
        best[k] = { t: Math.round(r.t * 1000) / 1000, w: typeof r.w === 'string' ? r.w.slice(0, 12) : null, r: r.r === 1 ? 1 : 0,
          s: Array.isArray(r.s) ? r.s.slice(0, 8).map(v => num(v) ? Math.round(v * 1000) / 1000 : null) : null,
          at: num(r.at) ? Math.min(r.at, now) : now };
      }
      const q = { name, best };
      if (p.prof && typeof p.prof === 'object' && JSON.stringify(p.prof).length < 3000) q.prof = p.prof;
      out.players.push(q);
    }
    await redis(['HSET', 'recs', uid, JSON.stringify(out)]);
    return json({ ok: true, doc: out });
  }
  return json({ error: 'op' }, 400);
}
