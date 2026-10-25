# 月見坂ナイトラン — 作業ガイド

ブラウザで遊ぶ3Dレースゲーム（three.js r128、1ファイルのHTML）。実在の車とサーキットを、Sketchfab の
GLB モデルを変換して走らせている。UI と文章はすべて日本語。ユーザーは日本語で話すので、返答も日本語で。

## 公開先（3か所あって、別々に更新される）

| | URL | 更新方法 | ランキング |
|---|---|---|---|
| Netlify 版 | https://tsukimizaka-night-run.netlify.app | `main` への push のうち、コミットメッセージに `[deploy]` を含むものだけ本番に出る（`netlify.toml` の `ignore`、`site/` を公開） | 端末ごとの記録のみ |
| Claude 版（アーティファクト） | https://claude.ai/artifact/D5QourP6E7TqL4C8Z7rRJZ | claude.ai のチャットから Artifact ツールで再公開 | Claude の共有DBで全員のランキング |
| Vercel 版 | https://tsukimizaka-night-run.vercel.app | `main` への push ごとに自動で本番に出る（Hobby プラン、回数の上限なし）。直下の `vercel.json` で `site/` を公開、キャッシュ設定もここ | 端末ごとの記録のみ |

- **ユーザーへの報告では、更新したら毎回 Vercel 版の URL（https://tsukimizaka-night-run.vercel.app）をそのまま貼る**（ユーザーの希望、2026-10-22）。
- **Claude 版を publish するときはレース中の人を待つ**（新しい版は開いているページに自動で届いて再読み込みされ、走行が中断されるため）:
  1. ArtifactData で `live` を list（各プレイヤーの `live/<uid>` = `{racing:'race'|'free'|'', eta, at}`）。`at` が3分以内で `racing:'race'` のものの最大 `eta` を出す。
  2. いれば `notice/update` に `{status:'pending', eta:<その最大eta>, at:<今>}` を set（ゲームの上部に「アップデート予定（あと約N分）」と出る）。
  3. その時刻まで待ち（最長15分、途中で live を読み直してよい）、publish したら `notice/update` を `{status:'done', at}` にする。フリー走行は待たない（バナーで予告だけ）。
  4. publish のときは `capabilities` を省略して今の宣言を引き継ぐ（db の rules: records / ghosts / weather / live / notice、と user）。
  それでも走行中に再読み込みされたページは、次に開いたときに「更新のため中断」と出してスタート準備の画面から再開できる（`fpr-run`、`runRestoreNote`）。
- このリポジトリを直しても **Claude 版は変わらない**。Claude 版にも反映したいときはユーザーに伝える
  （Artifact ツールが使えるセッションなら `site/index.html` を読み直してから同じ URL に publish し、
  `cars/` `tracks/` `audio/` の新しいファイルは `files` で一緒に送る）。
- Claude Code のセッションは普通は作業ブランチに push する。Netlify の本番に出るのは `main` だけ。
- **Netlify は無料プラン（月300クレジット、本番デプロイ1回15クレジット＝月20回まで）。** 使い切ると本番の更新が止まる（2026-10-17〜実際に止まった）。
  普段の push には `[deploy]` を付けない。数日に1回、スケジュールタスク「月見坂ナイトラン Netlify まとめ反映」が前回の `[deploy]` 以降に `site/` の変更があれば空コミット `[deploy]` を push する。
  急ぎで出したいときだけ手で `[deploy]` 付きのコミットを push する。

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
  `cyl`（音: 3/4/6/8/10/12/'v8x'/'flat4'/'flat6'/'rotary'/'ev'）`turbo` `sc` `lag` `ev`
  `body:{w,l,ride,h,color,wb}` `model:{url,s,off,rotY}` `credit:{title,author,url,license,licUrl}`。
  加速力は `t100` と `top` から自動で合わせ込まれる（`simT100`）。
  車は `CARS` の末尾（`s2000` の後ろ）に足す（選択中の車は番号 `fpr-car` で覚えているため）。新しい車には `since:'<追加の翌日 YYYY-MM-DD>'` を付ける：
  デイリーの「今日の車」（`chRot`）はその日から並びに入るので、追加した日の途中でお題が変わらない。メーカーが新しいときは `chRegion` と実績 `jp` の日本メーカー一覧も確認。
- `const RIGS={` … 車のモーション（車輪の回転・前輪の操舵・車体のロール/ピッチ）の設定。車ごとに4輪の円柱
  `hubs:[[x,y,z,半径,x0,x1,yaw0]×4]`（左後・右後・左前・右前、車の座標で m、+z が前、+x が左）と、車輪と一緒に回る
  マテリアル名 `spin`。`rigModel` が読み込み時に車輪を切り出し、`rigDrive`/`rigFrame` が毎フレーム、各車の位置と向きの
  変化から速度・加速度・ヨーレートを出して動かす（プレイヤー・ライバル・ゴースト・リプレイ・メニューのデモすべて同じ）。
- `const CAB={` … 運転席視点の目の位置 `[x,y,z]`（車の座標、右ハンドルは -x）。3D モデルの本物の車内にカメラを置く
  （車体のロール/ピッチと一緒に動く、運転中はガラスを薄くする）。内装がないモデルは null で、従来の描いたダッシュボードを使う。
  車を追加したら、真上からの断面と運転席からの画像で座席を確かめて決める。
  車内のないモデル（R34 など）は描いたダッシュボード＋`HOOD_Z[車]`（車の座標 z）より前だけ残した本物のモデル（ボンネット・フェンダー・ミラー）を見せる（`hoodClip`、自分の車のマテリアルだけ複製してクリッピング平面）。
  `HOOD_Z` は車ごとに運転席からの描画で決める（今は該当なし：R34 もウラカン（STO → GT3 EVO2、id `hgt3`）も内装つきモデルに置き換え済みで、全車に車内がある）。目の高さは `CARS` の `eye`。
- `const XXX_DATA={pts:[...],hw:[...],bank:[...],rw:[...]}` … コースの中心線（x,y,z を 4m 間隔で平らに並べたもの）、
  半幅、バンク（横方向 1m あたりの高さ変化）、任意で壁の距離 `rw`。
- `const COURSES=[` … コース一覧（`pts:XXX_DATA.pts` などで参照、`W` `N` `runoff` `laps` `env` `credit`）。
- `ground`（`GROUND`/`groundLoad`/`groundApply`/`gDy`、`RWP`/`RWN`、`tracks/<id>/ground.json`）… 3Dモデルのあるコースは、`tools/ground_scan.py <id>` が道の外まで実際の地面の高さ（道の平面からの差、1m 刻み）と左右別々の壁の位置（ガードレール・フェンス・木・段差・崖・モデルの端・ほかの区間との中間）を出す。
  ゲームは車の高さに `gDy` を足し、壁は `pl.off` の符号で `RWP`（+NR 側）/`RWN`（-NR 側）。ゲームの点とスキャンの点は位置で対応づける（`GDY.K`）。`work/ground/export.js` で index.html からコースの点を書き出してから走らせ、`tools/ground_view.py` で上から確かめる。
  コースの点（pts/hw/bank）を変えたら ground.json も作り直す。
  モデルのメッシュ同士のすき間（3m以下で両側の高さがほぼ同じ）は地面として埋めて数える。ground.json の `road` はバンド上でいちばん多い不透明な面のマテリアル名で、ゲームはそのマテリアルで実際の地面の 0.25m 下に壁から壁までの下敷き（`groundUnder`/`UNDER`）を敷き、すき間から下の緑の板が見えないようにする（2026-10-25、鈴鹿1コーナー手前の緑の三角）。下敷きの高さは ground.json の `fl`（各点・1m 刻みで、壁に関係なくいちばん低い面、-128 はモデルの外）、道幅＋1m より外は `side`（道の外でいちばん多い面、芝など）のマテリアル。
  鈴鹿の穴の本当の原因は `trim_cfg.py` の木の間引き：木と地面が同じアトラス（`Merged_materials`）で、平らな地面の部分まで 35% に間引かれていた。今は平らで地面の高さにある部品（`flat_piece`）は間引かない。ほかのコースでアトラスを veg にしているもの（カタルーニャ `MOTOROLA_97`、ニュル `Object5121Mtl.002`）は、作り直すときに同じ効果がある（カタルーニャは差 約1000三角形で、目立つ穴は見つかっていないので未更新）。
- `TIMES` / `WEATHERS` / `applyWeather` … 時間帯と天候（雨はグリップ 0.8・ブレーキ 0.85）。
- `function computeTrack` … 推奨速度・コーナー検出。`function updatePlayer` … 車の物理（AT/MT、エンジンブレーキ、壁、接触）。
  挙動（2026-10-25 試作）：`DF[車]`（200km/h での追加グリップの割合、`dfK`）のダウンフォース、`vCorner` で推奨速度・AI のラインにも反映。向き `pl.th` と進む向き（`pl.th-pl.beta`）を分け、前輪の限界でアンダー、
  ブレーキで前へ・アクセルで後ろへの荷重移動、後輪駆動のパワーオーバー、すべり角は約32°で頭打ち（スピンしない）。滑ると速度が落ちる。ラップタイムが変わるので、本番に出すときは記録の扱いを決める。
  MT は 1速の下にニュートラル（`pl.gear===0`、表示 N）：駆動もエンジンブレーキもなく、アクセルで空ぶかししてリミッター（`nRev`/`revCut`）に当たる。
- `AILV` / `aiBuild`（設定 `opts.ai`、スタート準備の「AIの強さ」）… レースのAIの難易度。やさしい・ふつう（従来どおり）・むずかしい・エキスパート。コーナーのグリップ `g`・ブレーキ `b`・最高速の上限 `cap`・ペース `s`・加速 `a` を変えた走行ライン `vcD` をスタート時に作る。エキスパートはゴールドタイム前後のペース。やさしいでの優勝は実績には数えないが、チャレンジには数える（難易度が要るお題は文面に「むずかしい以上」などと書き、`x.ai` で判定）。
- `ghost race`（`GR`/`grStart`/`grLoad`/`grGreen`/`grPlace`/`grEnd`、設定 `opts.opp`='ai'|'ghost'、スタート準備の「対戦相手」）… レースの相手を、そのコースのほかのプレイヤー上位3人の
  ベストラップ（車は問わない、共有ゴースト `ghosts/<uid>/runs/…`）にする。ゴーストの1周はフライングラップなので、アウトラップ1周（`SCL`=1、セーフティカーなし、表示 OUT）のあと
  ラインを越えた瞬間に全員スタート（ローリング）。ゴーストは AI の枠（`a.gh`）に入り、各自の周をくり返す（完走 = 周回数×その人のベストラップ）。接触なし。ゴーストがない枠は `a.out`（台数から外す）。
  共有DBがない（Netlify 版）・ほかの人の記録がないときは AI 戦になる。優勝は実績・チャレンジの勝利に数える（AI の難易度の実績と SC の実績は除く、相手0台なら数えない）。`'race'`/`'win'` は `gr:true`、`ai:'ghost'`。
- `position tower`（`towerTick`/`towerEntries`、`#tower`）… レース中、右上の順位の下に全員の順位・車の色・名前・トップとの差。並び替えは transform のアニメーション、上がった行は緑・下がった行は赤で光る。`#posN`/`#posT`（台数）もここで更新。スマホ（幅700px以下）のレース中はミニマップを隠す（`body.racing`）。
- `rear-view mirror`（`mirFrame`、`#mirHud`、設定 `opts.mirror`、スタート準備の「バックミラー」）… 運転席視点のとき、目の位置から後ろ向きのカメラで小さな RT に描き、画面上部の枠に左右反転で出す（自分の車は隠す）。モデルのミラーに映す方式は鏡面合わせが車ごとに必要で見送り（試作 HxQtySUxywVV4VZ1qj1Pyy）。
- `phones: landscape`（`phLayout`/`PH`/`VW()`/`VH()`）… スマホは常に横画面。縦持ちのとき（タッチ・縦長・幅540px以下）は `body.rot` でページ全体を90度回す（JS で body の幅・高さ・transform を px 指定）。
  横向きの低い画面（回した場合も本当に横向きも）は `body.phl` 用の配置（HUD・パッド・無線・メニュー）。回転中は縦持ち用の `max-width` メディアクエリが効かないよう `body:not(.rot)` で囲ってある。
  画面サイズは `innerWidth` ではなく `VW()`/`VH()`、要素の位置は `getBoundingClientRect` ではなく `offsetWidth` など（回転の影響を受けない値）を使う。Android は最初のタップで全画面＋横向き固定を試す（`phTryLock`）。
  タッチのパッドは走行中だけ（`body.hudon`）。
- `gyro steering`（`GY`/`gyroSteer`/`gyAsk`/`gyCenter`、設定 `opts.gyro`、スタート準備の「ジャイロ操作」、タッチ端末だけ表示）… スマホをハンドルのように回して曲がる。`devicemotion` の重力を端末の軸で読み、
  いまの重力にいちばん近い軸を「まっすぐ」にして（走り出す時・画面の向きが変わった時に取り直す）、そこからの回転角で舵。ON の間は左の◀▶を隠す（`body.gyro`）。キーやボタンを押している間はそちらが優先。
  iPhone はタップから `DeviceMotionEvent.requestPermission()`（ページを開くたびに最初のタップで再要求）。センサーの値が来ない埋め込み（Claude 版のアプリ内など）では ON にせず、ブラウザ版を案内する。ページ先頭に viewport の meta（Netlify 版用。Claude 版は外側のページが付ける）。
- `commentary voice`（`CM`/`cmSay`/`cmFromRadio`/`cmStartCall`、設定 `opts.cm`、スタート準備の「実況」）… 録音した実況の短いセリフ。`audio/voice.json`（`clips:{key:[t0,t1]}`）＋`voice.png`（mp3 1本）を
  `tools/pack_voice.py` が台本（`CM_LINES`、ユーザーに渡した順）を通しで読んだ1本の音声から切り出して作る（`key=fix.mp3` で1行だけ差し替え）。声は ElevenLabs でユーザーが作る（実在の人の声のまねはしない、話し方の特徴だけで作った声）。
  ファイルがなければ実況なし・行も出ない。きっかけはスタート（GO）、無線のイベント（`radioSay` の先頭で `cmFromRadio`、無線 OFF でもレースの判定は回す）、ゴール、自己ベスト。1度に1つ、キーごとの間隔 `CM_CD`、話している間はエンジン音を下げる。
  台本2（`CM_LINES2`）は天候・時間帯と車の組み合わせのセリフ：`cmPassKey`（相手との馬力差・年式差・メーカー・国・EV・雨の4WD）、`cmLostKey`、`cmBattleKey`、`cmWinKey`、スタートの時間帯/天候。`cmVar` が合うものから確率で選び、voice.json にないキーは使わない。
  台本3・4（`CM_LINES3` 車 `c_<id>`・`CM_LINES4` コース `t_<id>`）は紹介：セーフティカー先導の1周（とゴースト対戦のアウトラップ）で、最初のセリフのあとにコース→車の順に読む（`cmIntroLap`→`CM.seq`→`cmTick`、GREEN で打ち切り。2026-10-24 にユーザーの希望でスタート準備の画面から移した。`cmIntro` は未使用）。車やコースを足したら台本3・4にも1行足して、その行だけ録ってもらう。
- `graphics quality`（`GFX`/`gfxSet`/`gfxScene`/`gfxFrame`/`gfxRoadLike`、設定 `opts.gfx`='high'|'std'、スタート準備の「画質」、既定はPC+WebGL2で高画質・スマホは標準）… 高画質は three r128 の EffectComposer（examples を jsdelivr から必要時に読む）：
  UnrealBloomPass（夜・夕方は強め）、色調・周辺減光・粒子・速度の放射ブラーのシェーダー、太陽の影（プレイヤーに追従、車だけ落とす）と車の下の接地影、雨で灰色の路面だけ濡らす（テクスチャの平均色で判定）。走行中に重いと自動で標準へ。
- `/* ---------- audio` … WebAudio 合成のエンジン音（`PROF` が気筒形式ごとの音色）。
- `engine character`（`S2CFG`/`EXH`/`s2Frame`）… 車ごとの音の特徴と排気の炎。`S2CFG[車]` は bark（アクセルオフの破裂音の量）・style
  （pop/crackle パチパチ/burble ボコボコ/bang）・bov（ブローオフの大きさ）・flutter・als（アンチラグ）・shift（dct/seq/isr）・vtec（切替 rpm）・
  whine（ギア鳴き）・hybrid・scK。全車に燃焼のばらつき・回転の揺れ・メカ音、運転席視点では車内のこもり（`S2.cab`）と路面の継ぎ目。
  破裂音は `A.pop` バスで大きめに鳴らし、鳴る瞬間だけエンジンを下げる（`s2Dip`）。`EXH[車]` はマフラー出口 `[x,y,z(,横出し±1)]`（車の座標）で、
  破裂音に合わせて `rig_body` に付けた炎のスプライトと点光源が出る（`fxFlame`）。車を追加したら後ろからの描画でマフラー位置を確かめて `EXH` に入れる（モデルにマフラーがない GR ヤリス・GT-R GT3・S2000 は推定）。
- `menu motion and sound`（`menuMotion`/`menuShot`/`MCAM`/`uiSnd`/`menuSel`）… メニューの段階が進むと右から・戻ると左から滑り込み、ボタンやカードが順に出る。選んだものは小さく弾む。背景の3Dは段階ごとのカメラ（タイトル＝引きの周回、マシン＝低いアップ、コース＝空撮、変速/天候＝後ろ、スタート＝前からの低いアングル）へなめらかに移る。
  効果音は合成（hover の小さなチック、選択のクリック、進む/戻るのシュッ、車を選ぶとその車のレッドゾーンに合わせた空ぶかし、スタートの上昇音）。reduce motion ではアニメなし。
- `splash / finish cinematic / lap-record effects`（`splashShow`/`splashEnter`、`FIN`/`finCineStart`/`finCam`/`fxTimeScale`、`fxLapRecord`/`fxBanner`/`fxConfetti`、`fxDemo` と `FX_DEMO`）… ページは PRESS TO ENTER の画面から始まる（最初の操作で音を有効にする）。レースのゴールは線の先の横からのカメラ・上下の黒帯・0.2倍のスロー（音もこもる）→ 元の速さで走り抜けて固定カメラから遠ざかる → 結果。
  フリー走行の自己ベストは緑の光とバナー、コースレコード（全員・全車で最速）は紫の光・紙吹雪・白いフラッシュ・短いスロー・ファンファーレ。`FX_DEMO` を true にすると右下に「演出を見る」パネル（試作ページだけ）。
- `/* ---------- flow:` … タイトル → モード → マシン → コース → 変速 → 天候 → スタート準備 の段階メニュー。
- `best-lap replay` / `tutorial` … リプレイとチュートリアル。
- `challenges`（`chEv`/`chSync`/`renderChal`、状態は `ACHS.dly` `ACHS.wk` `ACHS.stk` `ACHS.cp` `ACHS.titles` `ACHS.title` `ACHS.cos`）… タイトルの「チャレンジ」画面。
  デイリー3つ（かんたん20・ふつう30・むずかしい50pt、全部で +30＋連続日数ボーナス最大 +50）は日本時間の日付から `chDailies` で決まり全員共通、
  ウィークリー1つ（`CH_WEEKLY`、月曜0時、150pt＋称号）。進み具合はゲームのイベント（`chEv('lap'|'win'|'great'|'km'|'pb'|'gold'|'sector'|'pass'|'rev'|'flame'|'speed'|'race')`）で増える。
  合計ポイント（実績＋チャレンジ、`totalPts`）は減らず、ドライバーレベル（`lvOf`）と `COS`（炎の色・マフラー・ブローオフ）の解放に使う。称号 `TITLES` はウィークリー・レベル・一部の実績で手に入り、
  レベルと選んだ称号は `prof`（lv, ti）に載ってランキングとプレイヤー記録に出る。
  2026-10-19 からのデイリー・ウィークリーは「ゲームの要素を幅広く使う」お題（`chDailies2`/`CH_WEEKLY2`）。かんたんは今日の車×コース（`chRot` の固定シャッフル順で毎日進み、全車・全コースが順番に出る）、
  ふつう・むずかしいとウィークリーは天候・時間帯・視点・MT・リアル天候・ゴースト（`chEv('ghost')`）・リプレイ（`'replay'`）・SC・AIの強さ・タイヤ温度・セクターなど。`'lap'` は view/gh/mode、`'win'`/`'race'` は ai/sc/rank/pass/tyreOk/cab を持つ。「今週まだ乗っていない車／走っていないコース」は各自の `ACHS.wk.cars` / `ACHS.wk.courses` で判定する。
- `player record`（`renderProf`）… プレイヤー記録の画面。自分の実績の集計（`profSummary`：解除数・ランク別の数・走行距離など、
  数だけ）を `records/<uid>` の各プレイヤーに `prof` として載せ（`publishProf`、走行中は送らない）、全員の分を読んで表示する。
- `safety car start`（`scStart`/`scUpdate`、状態は `scar`）… レースの前にセーフティカー先導の1周（ヴァンテージか SLS、`SCCARS` は選べない車）。
  この周は周回数・タイム・ラップ記録に入らない（`SCL`=1 のとき完走は `LAPS+SCL` 周、表示は `SC` → `1/LAPS`、TOTAL は `raceT-raceT0`）。追い越し禁止（AI は前の車の後ろに並び、プレイヤーは速度を抑える）、残り `SC_EXIT` m で道の外へ抜けて消え、先頭がラインを越えたら GREEN。設定 `opts.sc` で切れる。
- `tyre temperature`（`tyreUpdate`、`tyreT` は 前左・前右・後左・後右、`tyreK` がグリップ倍率）… コーナーの横G・ブレーキ・ホイールスピンで温まり、
  風と気温で冷える（雨は冷えやすい）。適温は普通 70〜95°C、`gripG>=1.2` の車は 80〜105°C。冷えすぎ・熱すぎでグリップとブレーキが落ち、
  コーナー予告の推奨速度も `recNow` で下がる。右上のゲージ（`drawTyres`）と結果画面に表示。気温は `tempGrip` ではなくタイヤを通して効く。ライバル車には効かない。
- `team radio`（`radioSay`/`radioTick`、状態は `RD`）… エンジニア無線の吹き出し（左下）。レースは順位・前後との差・SC・ファイナルラップ・結果、
  フリーはアウトラップ・セクター（自己ベスト/ゴースト比較、遅れたコーナー名）・周回タイム・ゴールド・走りのくせ（突っ込みすぎ・減速しすぎ・ダート・道幅）。
  共通でタイヤ（適温・オーバーヒート）と接触。1回出たら8秒以上空け、キーごとに再発言の間隔。遅らせる発言は `rdLater`（ゲーム時間）。設定 `opts.radio`。
- 共有ランキング（`initShared`）は Claude の `window.claude.use('db')` があるときだけ動き、無ければ端末内の記録に切り替わる。
- `cloud save`（`csPull`/`csPush`/`csMergeAch`/`csRestoreBests`）… 実績・チャレンジ・称号・カスタマイズ（`ACHS`、端末の localStorage）を、本人だけが読める
  `data/users/<uid>/save` = `{players:{<名前>:{ach,at}}, last}` にも保存し（`achSave` から数秒まとめて）、開いたときに端末のデータと合わせる（解除済み・マップは和、数値は大きいほう、デイリー/ウィークリー/連続日数は新しい期間）。
  ベストタイムは共有ランキングの自分の行から端末に戻す。新しい端末の名前入力には前回の名前（`last`）が入る。2026-10-20、別の端末/アプリで開いて実績が見えなくなった件の対策。

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
   - `tools/route_audit.py model.glb course.json` … 中心線が本コース以外の道（ピット入口・側道・旧レイアウト）を通っていないか。コースの路面（タイヤ跡など）が中心から消えて横にある区間を出す。当たった所は上からの描画で必ず目で確かめる（ハンガロリンク最終コーナーで実際にあった）。
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
