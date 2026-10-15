# 3Dモデル軽量化の手順（このコースで実際に使った設定）。リポジトリのルートで: bash tools/pipelines/sil.sh
# 入力: work/sil/ に元のGLBと中心線 course.json（下の名前）を置く。OPT は optimize2.py の設定JSON。
TOOLS="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$OPT" ] || OPT='{"maxtex":1024}'
set -e -o pipefail
cd "${WORK:-work/sil}"
python3 -I "$TOOLS"/trim_cfg.py sil.glb sil_course.json sil_trim.glb '{"scale":1.0,"clear":true,"road":["asphalt.001","groove.001","groove2.001","groove3.001","Curb_new.001","curb.001","asph_pitlane.001"],"veg":["trees.001"],"drop":[],"ground":["top2.001","grass.001","sand_new.001","sand-bordini.001","grass_NM.001","top2_NM.001","top2_refl.001"],"corridor":90,"ground_keep":160,"veg_keep":60,"veg_fraction":0.35,"patch_mat":"asphalt.001"}' | head -3
python3 -I "$TOOLS"/optimize2.py sil_trim.glb sil_opt0.glb "$OPT" 2>&1 | grep sil_opt
python3 -I "$TOOLS"/fix_alpha.py sil_opt0.glb sil_opt.glb
