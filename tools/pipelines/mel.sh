# 3Dモデル軽量化の手順（このコースで実際に使った設定）。リポジトリのルートで: bash tools/pipelines/mel.sh
# 入力: work/mel/ に元のGLBと中心線 course.json（下の名前）を置く。OPT は optimize2.py の設定JSON。
TOOLS="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$OPT" ] || OPT='{"maxtex":1024}'
set -e -o pipefail
cd "${WORK:-work/mel}"
python3 -I "$TOOLS"/trim_cfg.py mel.glb mel_course.json mel_trim.glb '{"scale":1.0,"clear":true,"road":["PAT_rolex.004_65"],"veg":[],"drop":[],"ground":["PAT_rolex.004_12","PAT_rolex.004_75","PAT_rolex.004_20"],"corridor":90,"ground_keep":160,"patch_mat":"PAT_rolex.004_65"}' | head -3
python3 -I "$TOOLS"/optimize2.py mel_trim.glb mel_opt0.glb "$OPT" 2>&1 | grep mel_opt
python3 -I "$TOOLS"/fix_alpha.py mel_opt0.glb mel_opt.glb
