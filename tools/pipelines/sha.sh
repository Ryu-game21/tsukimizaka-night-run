# 3Dモデル軽量化の手順（このコースで実際に使った設定）。リポジトリのルートで: bash tools/pipelines/sha.sh
# 入力: work/sha/ に元のGLBと中心線 course.json（下の名前）を置く。OPT は optimize2.py の設定JSON。
TOOLS="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$OPT" ] || OPT='{"maxtex":1024}'
set -e -o pipefail
cd "${WORK:-work/sha}"
python3 -I "$TOOLS"/trim_cfg.py sha.glb sha_course.json sha_trim.glb '{"scale":1.0,"clear":true,"road":["advert_side_a_22","advert_side_a_50"],"veg":[],"drop":[],"ground":["advert_side_a_82","advert_side_a_13","advert_side_a_79","advert_side_a_86","advert_side_a_81","advert_side_a_14","advert_side_a_93","advert_side_a_94"],"corridor":90,"ground_keep":140,"patch_mat":"advert_side_a_22"}' | head -3
python3 -I "$TOOLS"/optimize2.py sha_trim.glb sha_opt.glb "$OPT" 2>&1 | python3 -c "
import sys,re,collections
t=collections.defaultdict(lambda:[0,0])
for l in sys.stdin:
    m=re.match(r'\s+decimated (\S+): (\d+) -> (\d+)',l)
    if m:t[m[1]][0]+=int(m[2]);t[m[1]][1]+=int(m[3])
    elif 'sha_opt' in l:print(l.strip())
for k,v in t.items():print(' ',k,v)"
