# 3Dモデル軽量化の手順（このコースで実際に使った設定）。リポジトリのルートで: bash tools/pipelines/bah.sh
# 入力: work/bah/ に元のGLBと中心線 course.json（下の名前）を置く。OPT は optimize2.py の設定JSON。
TOOLS="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$OPT" ] || OPT='{"maxtex":1024}'
set -e -o pipefail
cd "${WORK:-work/bah}"
SC=$(python3 -c "import json;print(json.load(open('scale.json'))['scale'])")
python3 -I "$TOOLS"/trim_cfg.py bah.glb bah_course.json bah_trim.glb "{\"scale\":$SC,\"clear\":true,\"road\":[\"Material_41.001_71\"],\"veg\":[],\"drop\":[],\"ground\":[\"Bahrainv3001791Mtl_7\",\"Material_41.001_72\",\"Material_41.001_8\",\"Material_41.001_90\",\"Material_41.001_9\",\"Material_41.001_76\"],\"corridor\":90,\"ground_keep\":140,\"patch_mat\":\"Material_41.001_71\"}" | head -3
python3 -I "$TOOLS"/optimize2.py bah_trim.glb bah_opt0.glb "$OPT" 2>&1 | python3 -c "
import sys,re,collections
t=collections.defaultdict(lambda:[0,0])
for l in sys.stdin:
    m=re.match(r'\s+decimated (\S+): (\d+) -> (\d+)',l)
    if m:t[m[1]][0]+=int(m[2]);t[m[1]][1]+=int(m[3])
    elif 'bah_opt' in l:print(l.strip())
for k,v in t.items():print(' ',k,v)"
python3 -I "$TOOLS"/fix_alpha.py bah_opt0.glb bah_opt.glb
