# 3Dモデル軽量化の手順（このコースで実際に使った設定）。リポジトリのルートで: bash tools/pipelines/mad.sh
# 入力: work/mad/ に元のGLBと中心線 course.json（下の名前）を置く。OPT は optimize2.py の設定JSON。
TOOLS="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$OPT" ] || OPT='{"maxtex":1024}'
set -e -o pipefail
cd "${WORK:-work/mad}"
python3 -I "$TOOLS"/trim_cfg.py mad.glb mad_course.json mad_trim.glb '{"scale":1.0,"clear":true,"road":["TarmacDark.001","main_kerbs.001","kuwait_bridge_road_3_lane.001","concrete_smooth.001","tyre_skids1.001","rubber.001","Line_White.001","Line_Red.001","Line_Yellow.001"],"veg":["Cypress1.001","Cypress2.001","Cypress3.001","Cypress4.001","Maple1.001"],"drop":[],"ground":["Background.001","top.001"],"corridor":90,"ground_keep":160,"veg_keep":60,"veg_fraction":0.35,"patch_mat":"TarmacDark.001"}' | head -3
python3 -I "$TOOLS"/optimize2.py mad_trim.glb mad_opt0.glb "$OPT" 2>&1 | grep mad_opt
python3 -I "$TOOLS"/fix_alpha.py mad_opt0.glb mad_opt.glb
