# 月見坂ナイトラン — 作業ガイド

ブラウザで遊ぶ3Dレースゲーム（three.js r128、1ファイルのHTML）。実在の車とサーキットを、Sketchfab の
GLB モデルを変換して走らせている。UI と文章はすべて日本語。ユーザーは日本語で話すので、返答も日本語で。

## 公開先（2か所あって、別々に更新される）

| | URL | 更新方法 | ランキング |
|---|---|---|---|
| Netlify 版 | https://tsukimizaka-night-run.netlify.app | `main` に push すると自動デプロイ（`netlify.toml` で `site/` を公開） | 端末ごとの記録のみ |
| Claude 版（アーティファクト） | https://claude.ai/artifact/D5QourP6E7TqL4C8Z7rRJZ | claude.ai のチャットから Artifact ツールで再公開 | Claude の共有DBで全員のランキング |

- このリポジトリを直しても **Claude 版は変わらない**。Claude 版にも反映したいときはユーザーに伝える
  （Artifact ツールが使えるセッションなら `site/index.html` を読み直してから同じ URL に publish し、
  `cars/` `tracks/` `audio/` の新しいファイルは `files` で一緒に送る）。
- Claude Code のセッションは普通は作業ブランチに push する。Netlify の本番に出るのは `main` だけ。

## 構成

```
site/                 公開されるもの（Netlify の publish ディレクトリ）
  index.html          ゲーム本体（CSS・JS・コースデータまで全部この1ファイル）
  cars/<id>/          車の 3D モデル: model.json + geo0.png
  tracks/<id>/        コースの 3D モデル: model.json + geo*.png
  audio/              bgm / signal（mp3 を PNG に詰めたもの）
  _headers            キャッシュ設定
tools/                モデル変換・コース作成・検査の Python ツール（各ファイル先頭の docstring に usage）
tools/pipelines/      各コースで実際に使ったモデル軽量化の設定（マテリアル名など）
tests/run.js          ヘッドレスのロジックテスト（node tests/run.js）
```

### なぜ 3D モデルが PNG なのか
Claude のアーティファクトのホストは json / txt / png / jpg しか配信しない。そこで GLB のバイナリを
**幅 4096 のグレースケール PNG（各行フィルタ 0）** に可逆で詰め、ページ側の `pngData()` が IDAT を
DecompressionStream で展開して元のバイト列に戻している（`tools/pack_png.py`）。mp3 も同じ方式。
Netlify だけなら GLB を直接置けるが、両方の公開先で同じファイルを使うため、この形式を守ること。

## index.html の地図（キーワードで検索）

- `const CARS=[` … 車の一覧。主なフィールド:
  `t100`（0-100km/h 秒）`top`（最高速）`gripG` `brakeG`（実車の G）`gears` `red`（レッドゾーン rpm）
  `cyl`（音: 3/4/6/8/10/12/'v8x'/'flat6'/'rotary'/'ev'）`turbo` `sc` `lag` `ev`
  `body:{w,l,ride,h,color,wb}` `model:{url,s,off,rotY}` `credit:{title,author,url,license,licUrl}`。
  加速力は `t100` と `top` から自動で合わせ込まれる（`simT100`）。
- `const RIGS={` … 車のモーション（車輪の回転・前輪の操舵・車体のロール/ピッチ）の設定。車ごとに4輪の円柱
  `hubs:[[x,y,z,半径,x0,x1,yaw0]×4]`（左後・右後・左前・右前、車の座標で m、+z が前、+x が左）と、車輪と一緒に回る
  マテリアル名 `spin`。`rigModel` が読み込み時に車輪を切り出し、`rigDrive`/`rigFrame` が毎フレーム、各車の位置と向きの
  変化から速度・加速度・ヨーレートを出して動かす（プレイヤー・ライバル・ゴースト・リプレイ・メニューのデモすべて同じ）。
- `const CAB={` … 運転席視点の目の位置 `[x,y,z]`（車の座標、右ハンドルは -x）。3D モデルの本物の車内にカメラを置く
  （車体のロール/ピッチと一緒に動く、運転中はガラスを薄くする）。内装がないモデルは null で、従来の描いたダッシュボードを使う。
  車を追加したら、真上からの断面と運転席からの画像で座席を確かめて決める。
- `const XXX_DATA={pts:[...],hw:[...],bank:[...],rw:[...]}` … コースの中心線（x,y,z を 4m 間隔で平らに並べたもの）、
  半幅、バンク（横方向 1m あたりの高さ変化）、任意で壁の距離 `rw`。
- `const COURSES=[` … コース一覧（`pts:XXX_DATA.pts` などで参照、`W` `N` `runoff` `laps` `env` `credit`）。
- `TIMES` / `WEATHERS` / `applyWeather` … 時間帯と天候（雨はグリップ 0.8・ブレーキ 0.85）。
- `function computeTrack` … 推奨速度・コーナー検出。`function updatePlayer` … 車の物理（AT/MT、エンジンブレーキ、壁、接触）。
- `/* ---------- audio` … WebAudio 合成のエンジン音（`PROF` が気筒形式ごとの音色）。
- `/* ---------- flow:` … タイトル → モード → マシン → コース → 変速 → 天候 → スタート準備 の段階メニュー。
- `best-lap replay` / `tutorial` … リプレイとチュートリアル。
- `player record`（`renderProf`）… プレイヤー記録の画面。自分の実績の集計（`profSummary`：解除数・ランク別の数・走行距離など、
  数だけ）を `records/<uid>` の各プレイヤーに `prof` として載せ（`publishProf`、走行中は送らない）、全員の分を読んで表示する。
- 共有ランキング（`initShared`）は Claude の `window.claude.use('db')` があるときだけ動き、無ければ端末内の記録に切り替わる。

## 車を追加する手順（Sketchfab の GLB）

作業用の `work/`（.gitignore 済み）に GLB を置いて進める。

1. `python3 tools/inspect_cars.py car.glb` … マテリアル・三角形数・画像を確認。
2. `python3 tools/flatten.py car.glb car_flat.glb [消すマテリアル,...]` … 変換を焼き込み、マテリアルごとに1メッシュへ。
   地面・ショールームの床などはここで落とす。Z-up のモデルは `ZUP=1`。
3. `python3 tools/fit_car.py car_flat.glb '{"drop":[],"wb":<ホイールベースm>,"L":<全長m>,"nose":"+z"}'`
   … 車軸と接地高さから `model:{s,off}` を提案。
4. `python3 tools/render_views.py car_flat.glb views.png '{"s":..,"off":[..],"rotY":0,"L":..,"wb":..,"H":..,"W":..}'`
   … 横・上・前・斜めの画像で、車輪が接地線・車軸位置に合っているか **必ず目で確認**。
5. `python3 tools/optimize2.py car_flat.glb car_opt0.glb '{"maxtex":512,"cluster":{"<3000三角形超のマテリアル>":[0.01]}}'`
   → `python3 tools/fix_alpha.py car_opt0.glb car_opt.glb` → `python3 tools/pack_png.py car_opt.glb site/cars/<id>`。
   1台あたり数MB以内が目安。
6. `CARS` に項目を追加（実車のカタログ値。公表値がないものは desc に「目安」と書く）。クレジットとライセンスは必須。
   続けて「車のモーション」の手順で `RIGS` も追加する。
7. `node tests/run.js` … 0-100km/h がカタログ値と合い、AT と MT が一致することを確認。

## 車のモーション（車を追加したら設定する）

1. `python3 tools/rig_wheels.py <id>` … 4輪の円柱と回るマテリアルの候補を `RIGS` の1行で出す（たたき台）。
   前輪が切れた状態で作られたモデルは yaw0 で真っすぐに直す。ブレーキキャリパーらしい物は回さない（前輪では操舵だけ）。
2. `RIGS` に追加して、`python3 tools/rig_check.py <id>` で **実際に描画して必ず目で確認**（three.js r128 を
   `work/three` に置く手順は docstring）。見る所:
   - restDiff ≈ 0（止まっている時は元のモデルと同じ見た目。違うなら頂点属性・面の向き・切り出しの問題）
   - spinOut = 0（車輪を回してもタイヤの外側が動かない）
   - シートで、キャリパーが回っていないか、フェンダーの内張りなどボディの一部が車輪と一緒に動いていないか
3. 回ってはいけない物が回る → そのマテリアルを `spin` から外す。ボディの一部が動く → 円柱（x0,x1,半径）を見直す。
   切り出しに失敗した車は元の動かないモデルのまま表示される（`rigModel` が false を返す）。

## コースを追加する手順（Sketchfab のサーキット）

コースの範囲（道幅・壁）が正しいことが最重要。ユーザーは「見た目は道路なのに壁がある」「ガイドがずれる」を
とても気にする。最後に必ず検査する。

1. `tools/survey.py` で航空写真風の画像とマテリアル候補を出し、路面・縁石・タイヤ跡（groove）・芝・砂のマテリアル名を決める。
2. `tools/groove_loop.py model.glb groove1,.. road1,.. x0 z0 W H` … タイヤ跡から周回ループ（loop.npy, road.npy, grid.json）。
   タイヤ跡が途切れる所は経由点でつなぐ。タイヤ跡がなければ `MASK=asph.npy`（`tools/graph.py` で作る）。
3. `tools/fit_band.py <半幅の目安> [反復]` … 中心線と半幅。白線の外側まで舗装が広い所は `CENTER=<左右合計の上限m>` で中央に寄せる。
4. `tools/band_limit.py [pitline.npy]` … ピットレーンとの分離線や、曲率による半幅の上限。
5. `tools/orient_start.py sx sz` … 時計回りに揃え、スタート地点を index 0 に。
6. `D=work/xxx/ GLB=xxx.glb ROADM=road1,road2 tools/route_profile.py` … 高さとバンク → course.json。
   古い路面の上に傾いた路面が重なっているバンクは `TOP=1`、バンク上限は `BMAX`、横方向の許容は `BTOL`、最小半幅は `HWMIN`。
7. 3D モデルの軽量化: `tools/pipelines/<既存コース>.sh` を手本に `trim_cfg.py` → `optimize2.py` → `fix_alpha.py`
   → `pack_png.py out.glb site/tracks/<id>`。
8. `XXX_DATA` と `COURSES` の項目を追加（`env` の空・霧・地面色、`credit` 必須）。
9. **検査（省略しない）**
   - `tools/final_check.py model.glb course.json road1,road2 <公式全長m>` … 道幅の面がすべて路面の上か、道幅の中に壁や物がないか、端が折り返していないか、全長と向き。
   - `tools/inspect_tiles.py model.glb course.json out road1,road2` … 1周分の上空タイル画像。黄が中心線、赤と青が道幅の端。目で全部見る。
   - `tools/wall_check.py course.json road.npy grid.json <runoff> write <上限>` … 見えている舗装より手前に壁が来る所を検出し、`rw` 配列を出す（ゲームは `RW=max(HW+runoff, rw)`）。
   - `tools/holes.py`（路面の穴）、`tools/sightlines.py`（視界を遮る物）。
10. `node tests/run.js`（全コースが組み上がるか）。

過去にあった失敗: 本線から外れて支線やエスケープ路を通ってしまう（経由点で修正）、ピットレーンに中心線が寄る
（分離線で切る）、白線を道の端とみなして見えている道路に壁を作る（舗装全体を基準にして `rw` で壁を外へ）、
バンクで下の古い平らな面の高さを拾う（`TOP=1`）。

## テストと確認

- `node tests/run.js` … メニューの流れ、全コースの組み上げ、雨のグリップ、周回とリプレイ、チュートリアル、全車の 0-100km/h。
  three.js は Vector3 と CatmullRomCurve3 以外スタブなので、見た目は確認できない。
- 見た目の確認は実ブラウザで。CDN（cdnjs / jsdelivr）と Google Fonts を読むので、オフライン環境では描画されない。
  サンドボックスでは three.js r128 を GitHub から取り、Playwright でその場に差し替えて描画できる（`tools/rig_check.py` の方式）。
  ただし swiftshader なので 1 フレーム数秒かかる。走行の確認は描画を止めて `frame()` を手で進めるとよい。
- 911 ターボ（930）はターボラグの再現で、停止からの 0-100 がカタログ値より約 0.8 秒遅い（意図的）。

## 約束ごと

- UI の文言は日本語。漢字・カタカナの車名やコース名は既存の書き方に合わせる。
- 3D モデルにはクレジット（タイトル・作者・URL・ライセンス）を必ず付ける。NC ライセンスのモデルもあるので商用利用はしない。
- 元の GLB（`*.glb`）はリポジトリに入れない（サイズとライセンスのため）。`work/` で作業する。
- 物理・推奨速度・ランキングのキー（`fpr-*` の localStorage）を変えるときは、既存の記録が壊れないように。
- コミットメッセージは日本語で可。
