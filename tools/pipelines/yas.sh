# 3Dモデル軽量化の手順（このコースで実際に使った設定）。リポジトリのルートで: bash tools/pipelines/yas.sh
# 入力: work/yas/ に元のGLBと中心線 course.json（下の名前）を置く。OPT は optimize2.py の設定JSON。
TOOLS="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$OPT" ] || OPT='{"maxtex":1024}'
set -e
cd "${WORK:-work/yas}"
python3 -I "$TOOLS"/yas_profile.py
python3 -I - <<'P'
import json
c=json.load(open('course.json'));s=60
for k in c:c[k]=c[k][s:]+c[k][:s]
json.dump(c,open('yas_course.json','w'))
P
SC=$(python3 -c "import json;print(json.load(open('scale.json'))['scale'])")
python3 -I "$TOOLS"/trim_cfg.py yas.glb yas_course.json yas_trim.glb "{\"scale\":$SC,\"clear\":true,\"road\":[\"tentrail_32\"],\"veg\":[],\"drop\":[\"tentrail_82\",\"tentrail_90\",\"tentrail_87\",\"tentrail_93\",\"tentrail_35\",\"tentrail_36\",\"tentrail_37\",\"tentrail_38\",\"tentrail_39\",\"tentrail_92\"],\"ground\":[\"tentrail_69\",\"tentrail_26\",\"tentrail_29\",\"tentrail_19\",\"tentrail_31\",\"tentrail_27\",\"tentrail_22\",\"tentrail_30\"],\"corridor\":90,\"ground_keep\":140}" | head -2
python3 -I "$TOOLS"/optimize2.py yas_trim.glb yas_opt.glb '{"maxtex":1024,"cluster":{"tentrail_57":[0.25],"tentrail_89":[0.3],"Merged_materials":[0.25],"tentrail_86":[0.3],"tentrail_94":0.25,"tentrail_6":0.3,"tentrail_23":0.3}}' 2>&1 | grep yas_opt
