# 3Dモデル軽量化の手順（このコースで実際に使った設定）。リポジトリのルートで: bash tools/pipelines/sin.sh
# 入力: work/sin/ に元のGLBと中心線 course.json（下の名前）を置く。OPT は optimize2.py の設定JSON。
TOOLS="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$OPT" ] || OPT='{"maxtex":1024}'
set -e -o pipefail
cd "${WORK:-work/sin}"
python3 -I "$TOOLS"/trim_cfg.py sin.glb sin_course.json sin_trim.glb '{"scale":1.0,"clear":true,"road":["11001Mtl_14"],"veg":[],"drop":[],"ground":["11001Mtl_94","11001Mtl","11001Mtl_95","11001Mtl_80","11001Mtl_86"],"corridor":90,"ground_keep":160,"patch_mat":"11001Mtl_14"}' | head -3
python3 -I "$TOOLS"/optimize2.py sin_trim.glb sin_opt0.glb "$OPT" 2>&1 | grep sin_opt
python3 -I "$TOOLS"/fix_alpha.py sin_opt0.glb sin_opt.glb
