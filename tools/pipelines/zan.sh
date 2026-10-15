# 3Dモデル軽量化の手順（このコースで実際に使った設定）。リポジトリのルートで: bash tools/pipelines/zan.sh
# 入力: work/zan/ に元のGLBと中心線 course.json（下の名前）を置く。OPT は optimize2.py の設定JSON。
TOOLS="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$OPT" ] || OPT='{"maxtex":1024}'
set -e -o pipefail
cd "${WORK:-work/zan}"
python3 -I "$TOOLS"/trim_cfg.py zan.glb zan_course.json zan_trim.glb '{"scale":1.0,"clear":true,"road":["Dado_LW_041_96","Dado_LW_041_42","Dado_LW_041_60","Dado_LW_041_71","Dado_LW_041_55","Dado_LW_041_74","Dado_LW_041_61"],"veg":[],"drop":[],"ground":["Dado_LW_041_73","Dado_LW_041_97","Dado_LW_041_86","Dado_LW_041_81","Dado_LW_041_43","Dado_LW_041_31","Dado_LW_041_24"],"corridor":90,"ground_keep":160,"patch_mat":"Dado_LW_041_96"}' | head -3
python3 -I "$TOOLS"/optimize2.py zan_trim.glb zan_opt0.glb "$OPT" 2>&1 | grep zan_opt
python3 -I "$TOOLS"/fix_alpha.py zan_opt0.glb zan_opt.glb
