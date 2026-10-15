# 3Dモデル軽量化の手順（このコースで実際に使った設定）。リポジトリのルートで: bash tools/pipelines/mon.sh
# 入力: work/mon/ に元のGLBと中心線 course.json（下の名前）を置く。OPT は optimize2.py の設定JSON。
TOOLS="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$OPT" ] || OPT='{"maxtex":1024}'
set -e -o pipefail
cd "${WORK:-work/mon}"
python3 -I "$TOOLS"/trim_cfg.py mon.glb mon_course.json mon_trim.glb '{"scale":1.0,"clear":true,"road":["apsh-shader-norm.005","groove.003","groove2.005","groove2b.005","whiteline.005","curb-shader.005","curb-NM.005","apsh-shader-scuro.005","apsh-shader2.005","asph-pitlane.005"],"veg":["trees.005","tree8.005","treesline.005","branch5.005","Bark.005","hedge.005","tree_shadow.005"],"drop":[],"ground":["top_new.005","top_B.005","grass-shader.005","sand.005","grs_brd.005"],"corridor":90,"ground_keep":160,"veg_keep":60,"veg_fraction":0.35,"patch_mat":"apsh-shader-norm.005"}' | head -3
python3 -I "$TOOLS"/optimize2.py mon_trim.glb mon_opt0.glb "$OPT" 2>&1 | grep mon_opt
python3 -I "$TOOLS"/fix_alpha.py mon_opt0.glb mon_opt.glb
