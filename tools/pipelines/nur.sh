# 3Dモデル軽量化の手順（このコースで実際に使った設定）。リポジトリのルートで: bash tools/pipelines/nur.sh
# 入力: work/nur/ に元のGLBと中心線 course.json（下の名前）を置く。OPT は optimize2.py の設定JSON。
TOOLS="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$OPT" ] || OPT='{"maxtex":1024}'
set -e -o pipefail
cd "${WORK:-work/nur}"
SC=$(python3 -c "import json;print(json.load(open('scale.json'))['scale'])")
python3 -I "$TOOLS"/trim_cfg.py nur.glb nur_course.json nur_trim.glb "{\"scale\":$SC,\"clear\":true,\"road\":[\"Object6521Mtl.002\"],\"veg\":[\"Object5121Mtl.002\"],\"drop\":[\"Union1Mtl\",\"Meshespinewallfbxpinewall0971Mtl.001\"],\"ground\":[\"Object6921Mtl.002\",\"Object6121Mtl.002\",\"Object4231Mtl.002\",\"Object4621Mtl.001\",\"Object5721Mtl.002\",\"Object721Mtl\"],\"corridor\":90,\"ground_keep\":140,\"veg_keep\":55,\"veg_fraction\":0.35,\"patch_mat\":\"Object6521Mtl.002\"}" | head -3
python3 -I "$TOOLS"/optimize2.py nur_trim.glb nur_opt0.glb '{"maxtex":512}' 2>&1 | grep nur_opt
python3 -I "$TOOLS"/fix_alpha.py nur_opt0.glb nur_opt.glb
