# 3Dモデル軽量化の手順（このコースで実際に使った設定）。リポジトリのルートで: bash tools/pipelines/hun.sh
# 入力: work/hun/ に元のGLBと中心線 course.json（下の名前）を置く。OPT は optimize2.py の設定JSON。
TOOLS="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$OPT" ] || OPT='{"maxtex":1024}'
set -e -o pipefail
cd "${WORK:-work/hun}"
python3 -I "$TOOLS"/trim_cfg.py hun.glb hun_course.json hun_trim.glb '{"scale":1.0,"clear":true,"road":["drs_floor_a_01.001_76"],"veg":[],"drop":[],"ground":["drs_floor_a_01.001_13","Merged_materials","drs_floor_a_01.001_14"],"corridor":90,"ground_keep":160,"patch_mat":"drs_floor_a_01.001_76"}' | head -3
python3 -I "$TOOLS"/optimize2.py hun_trim.glb hun_opt0.glb "$OPT" 2>&1 | grep hun_opt
python3 -I "$TOOLS"/fix_alpha.py hun_opt0.glb hun_opt.glb
