# 3Dモデル軽量化の手順（このコースで実際に使った設定）。リポジトリのルートで: bash tools/pipelines/suz.sh
# 入力: work/suz/ に元のGLBと中心線 course.json（下の名前）を置く。OPT は optimize2.py の設定JSON。
TOOLS="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$OPT" ] || OPT='{"maxtex":1024}'
set -e
cd "${WORK:-work/suz}"
SC=$(python3 -c "import json;print(json.load(open('scale.json'))['scale'])")
python3 -I "$TOOLS"/trim_cfg.py suz.glb suz_course.json suz_trim.glb "{\"scale\":$SC,\"clear\":true,\"road\":[\"282_69\",\"282_64\"],\"veg\":[\"Merged_materials\"],\"drop\":[\"282_54\"],\"ground\":[\"282_62\",\"282_60\",\"282_61\",\"282_56\",\"282_57\",\"282_58\",\"282_59\",\"282_65\",\"material\"],\"corridor\":90,\"ground_keep\":140,\"veg_keep\":55,\"veg_fraction\":0.35,\"patch_mat\":\"282_69\"}" | head -1
python3 -I "$TOOLS"/optimize2.py suz_trim.glb suz_opt.glb '{"maxtex":1024}' 2>&1 | grep suz_opt
