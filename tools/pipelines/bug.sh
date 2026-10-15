# 3Dモデル軽量化の手順（このコースで実際に使った設定）。リポジトリのルートで: bash tools/pipelines/bug.sh
# 入力: work/bug/ に元のGLBと中心線 course.json（下の名前）を置く。OPT は optimize2.py の設定JSON。
TOOLS="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$OPT" ] || OPT='{"maxtex":1024}'
set -e -o pipefail
cd "${WORK:-work/bug}"
python3 -I "$TOOLS"/trim_cfg.py bug.glb bug_course.json bug_trim.glb '{"scale":1.0,"clear":true,"road":["01_-_Default.002","ROADREAL2_WET.002","ROADREAL3_WET.002","ROADREAL4_WET.002","ROADKERB1_WET.002","ROADTSTRIPE.002","ROAS_01.002","ROAD_02.002"],"veg":["trees_new.002","pines1.002","trees2.002","TREE_01.002","TREELINE_01.002"],"drop":[],"ground":["GRASS_01.002","GRASS_03.002","BACKGRD_001.002","FPOLE_01.002","TRANSIT.002"],"corridor":90,"ground_keep":160,"veg_keep":60,"veg_fraction":0.35,"patch_mat":"01_-_Default.002"}' | head -3
python3 -I "$TOOLS"/optimize2.py bug_trim.glb bug_opt0.glb "$OPT" 2>&1 | grep bug_opt
python3 -I "$TOOLS"/fix_alpha.py bug_opt0.glb bug_opt.glb
