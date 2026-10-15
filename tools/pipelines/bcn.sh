# 3Dモデル軽量化の手順（このコースで実際に使った設定）。リポジトリのルートで: bash tools/pipelines/bcn.sh
# 入力: work/bcn/ に元のGLBと中心線 course.json（下の名前）を置く。OPT は optimize2.py の設定JSON。
TOOLS="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$OPT" ] || OPT='{"maxtex":1024}'
set -e -o pipefail
cd "${WORK:-work/bcn}"
python3 -I "$TOOLS"/trim_cfg.py bcn.glb bcn_course.json bcn_trim.glb '{"scale":1.0,"clear":true,"road":["MOTOROLA_96","MOTOROLA_53","MOTOROLA_67","MOTOROLA_66","MOTOROLA_38","MOTOROLA_63"],"veg":["MOTOROLA_52","MOTOROLA_97"],"drop":[],"ground":["MOTOROLA_79","MOTOROLA_65","MOTOROLA_45","MOTOROLA_21","MOTOROLA_82","MOTOROLA_12","MOTOROLA_81"],"corridor":90,"ground_keep":160,"veg_keep":60,"veg_fraction":0.35,"patch_mat":"MOTOROLA_96"}' | head -3
python3 -I "$TOOLS"/optimize2.py bcn_trim.glb bcn_opt0.glb "$OPT" 2>&1 | grep bcn_opt
python3 -I "$TOOLS"/fix_alpha.py bcn_opt0.glb bcn_opt.glb
