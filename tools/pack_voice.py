"""Commentary voice: cut one long take (every line of the script read in order) into clips and pack them.

usage: python3 tools/pack_voice.py take.mp3 [key=fix.mp3 ...]
  take.mp3     the whole script (CM_LINES in this file, same order) read in one go, any pause between lines
  key=fix.mp3  replace one clip with a separate recording of just that line (re-read, better take)
writes site/audio/voice.png + site/audio/voice.json = {file, bytes, clips:{key:[t0,t1]}} and work/voice/<key>.wav
for listening. Prints every clip's length against what its text predicts - check the table: a cut in the wrong
place shows up as one clip much too long next to one much too short.

How the cuts are found: ffmpeg silencedetect gives every pause; a DP picks N-1 of them so that each clip's
length best matches its line's length (mora-ish count of the text x the take's own speaking rate), with a bonus
for longer pauses. Pauses inside a sentence ("さあ、") are short and fall in the wrong place for the counts,
so they lose to the real gaps between lines even when those gaps are only ~0.3 s.
The clips are re-joined with 0.25 s of silence into one mono mp3 (one file to fetch and decode)."""
import json, os, re, subprocess, sys, tempfile, wave
import numpy as np

# key, text - the same order as the script given to the user (keep in sync with CM in index.html)
CM_LINES = [
    ('start_a', 'さあ、スタートしました！'),
    ('start_b', 'ブラックアウト！レーススタート！'),
    ('start_rain', '雨の中のレース、路面は滑りやすいぞ！'),
    ('sc_start', 'セーフティカー先導でのスタートです。'),
    ('sc_green', 'セーフティカーが抜けた！グリーンフラッグ！'),
    ('gr_green', 'ゴーストとのバトル、スタート！'),
    ('pass_a', '抜いた！ポジションアップ！'),
    ('pass_b', 'インを突いて、オーバーテイク！'),
    ('lead', 'トップに立ちました！'),
    ('lost', 'あーっと、抜かれてしまった！'),
    ('closing', '前との差が、どんどん縮まっていきます！'),
    ('defend', '後ろから迫ってきている、守り切れるか！'),
    ('hit_car', 'おっと、接触！'),
    ('hit_wall', 'あーっと、ウォールにヒット！'),
    ('dirt', 'コースオフ！砂煙が上がった！'),
    ('sec_fast', 'セクターベスト！いいペースです！'),
    ('final', 'ファイナルラップ！最後の1周です！'),
    ('win_a', 'チェッカーフラッグ！優勝です！'),
    ('win_b', 'やりました！トップでチェッカー！'),
    ('podium', '表彰台、獲得です！'),
    ('finish', 'チェッカーを受けました。おつかれさまでした！'),
    ('pb', '自己ベスト更新！'),
    ('gold', 'ゴールドタイム！これは速い！'),
    ('push', 'ラップタイム、更新なるか！'),
]
SR = 44100
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def units(t):
    """rough spoken length: kana/kanji count (kanji ~1.6 morae), punctuation as a short pause"""
    n = 0.0
    for ch in t:
        if re.match(r'[぀-ヿ]', ch): n += 1 if ch not in 'ゃゅょャュョァィゥェォ' else 0.3
        elif re.match(r'[一-鿿]', ch): n += 1.6
        elif ch in '、。！？': n += 0.8
        elif ch.isdigit(): n += 2
        else: n += 0.5
    return n


def decode(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def trim(x, thr=0.012, pad=0.04):
    """cut leading/trailing silence, keep a little air"""
    env = np.convolve(np.abs(x), np.ones(441) / 441, 'same')
    idx = np.where(env > thr)[0]
    if not len(idx): return x
    a = max(0, idx[0] - int(pad * SR)); b = min(len(x), idx[-1] + int(pad * SR * 2))
    return x[a:b]


def pauses(x, thr=0.012, min_len=0.10):
    """[(start, end)] of quiet stretches in seconds"""
    env = np.convolve(np.abs(x), np.ones(441) / 441, 'same') < thr
    out, i, n = [], 0, len(env)
    while i < n:
        if env[i]:
            j = i
            while j < n and env[j]: j += 1
            if (j - i) / SR >= min_len and i > 0 and j < n: out.append((i / SR, j / SR))
            i = j
        else: i += 1
    return out


def split(x, texts):
    x = trim(x); dur = len(x) / SR; P = pauses(x); N = len(texts)
    if len(P) < N - 1: sys.exit(f'only {len(P)} pauses for {N} lines - generate with clear gaps, or send lines separately')
    U = np.array([units(t) for t in texts]); rate = dur / U.sum()
    cuts = [(a + b) / 2 for a, b in P]; L = [b - a for a, b in P]
    M = len(cuts); INF = 1e18
    # dp[k][j]: best cost with k-th cut (0-based) placed at pause j
    def seg_cost(t0, t1, k):
        e = U[k] * rate; return ((t1 - t0) - e) ** 2 / max(e, 0.3)
    dp = np.full((N - 1, M), INF); back = np.zeros((N - 1, M), int)
    for j in range(M): dp[0][j] = seg_cost(0, cuts[j], 0) - 2.0 * L[j]
    for k in range(1, N - 1):
        best, bi = INF, -1
        for j in range(M):
            c = INF
            for i in range(max(0, j - 12), j):
                if dp[k - 1][i] >= INF: continue
                v = dp[k - 1][i] + seg_cost(cuts[i], cuts[j], k) - 2.0 * L[j]
                if v < c: c, back[k][j] = v, i
            dp[k][j] = c
    last = min(range(M), key=lambda j: dp[N - 2][j] + seg_cost(cuts[j], dur, N - 1))
    sel = [last]
    for k in range(N - 2, 0, -1): sel.append(back[k][sel[-1]])
    sel = sel[::-1]
    edges = [0] + [cuts[j] for j in sel] + [dur]
    clips = [trim(x[int(edges[i] * SR):int(edges[i + 1] * SR)]) for i in range(N)]
    return clips, rate


def main():
    take = sys.argv[1]; fixes = dict(a.split('=', 1) for a in sys.argv[2:])
    keys = [k for k, _ in CM_LINES]; texts = [t for _, t in CM_LINES]
    clips, rate = split(decode(take), texts)
    for k, f in fixes.items():
        if k not in keys: sys.exit('unknown key ' + k)
        clips[keys.index(k)] = trim(decode(f))
    os.makedirs(os.path.join(ROOT, 'work/voice'), exist_ok=True)
    gap = np.zeros(int(0.25 * SR), np.float32); parts = [gap]; meta = {}; t = len(gap) / SR
    print(f'{"key":10s} {"sec":>5s} {"expect":>6s}  text')
    for k, txt, c in zip(keys, texts, clips):
        peak = np.abs(c).max() or 1; c = c * min(1.0, 0.95 / peak)
        meta[k] = [round(t, 3), round(t + len(c) / SR, 3)]; parts += [c, gap]; t += (len(c) + len(gap)) / SR
        flag = '' if 0.6 < (len(c) / SR) / (units(txt) * rate) < 1.6 else '  <-- check'
        print(f'{k:10s} {len(c)/SR:5.2f} {units(txt)*rate:6.2f}  {txt}{flag}')
        with wave.open(os.path.join(ROOT, 'work/voice', k + '.wav'), 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((c * 32767).astype(np.int16).tobytes())
    allx = np.concatenate(parts)
    with tempfile.TemporaryDirectory() as d:
        wv = os.path.join(d, 'a.wav'); mp = os.path.join(d, 'a.mp3')
        with wave.open(wv, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((allx * 32767).astype(np.int16).tobytes())
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', wv, '-ac', '1', '-b:a', '80k', mp], check=True)
        data = open(mp, 'rb').read()
    # mp3 encoders add a short delay at the start; measure it so the clip times stay exact
    dec = decode_bytes(data); off = align(dec, allx)
    for k in meta: meta[k] = [round(meta[k][0] + off, 3), round(meta[k][1] + off, 3)]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(ROOT, 'site/audio'); png = pack(data)
    open(os.path.join(out, 'voice.png'), 'wb').write(png)
    json.dump({'file': 'voice.png', 'bytes': len(data), 'clips': meta}, open(os.path.join(out, 'voice.json'), 'w'), ensure_ascii=False)
    print(f'voice.png {len(png)/1e6:.2f} MB, {t:.1f} s, encoder offset {off*1000:.0f} ms')


def decode_bytes(b):
    with tempfile.NamedTemporaryFile(suffix='.mp3') as f:
        f.write(b); f.flush(); return decode(f.name)


def align(dec, ref):
    a = np.abs(dec[:SR * 3]); r = np.abs(ref[:SR * 3])
    best, bo = -1, 0
    for o in range(0, 4000, 8):
        v = float(np.dot(a[o:o + len(r) - 4000], r[:len(r) - 4000]))
        if v > best: best, bo = v, o
    return bo / SR


def pack(data):
    """same lossless greyscale PNG as the other audio (width 4096, filter 0 on every row)"""
    import struct, zlib
    W = 4096; H = (len(data) + W - 1) // W; pad = data + bytes(H * W - len(data))
    rows = b''.join(b'\x00' + pad[r * W:(r + 1) * W] for r in range(H))
    ch = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 0, 0, 0, 0)) + ch(b'IDAT', zlib.compress(rows, 9)) + ch(b'IEND', b'')


if __name__ == '__main__':
    main()
