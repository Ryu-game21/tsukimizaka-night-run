箱根ターンパイク（Unity 試作）

【使い方】
1. Unity Hub で Unity 6（LTS）をインストールし、「Universal 3D」テンプレートで新しいプロジェクトを作る。
2. この zip の中の「Assets/Turnpike」フォルダを、プロジェクトの Assets フォルダの中にコピーする
   （Unity の Project ウィンドウの Assets にドラッグ＆ドロップでも可）。読み込みが終わるまで待つ。
3. 上のメニューバーの「Turnpike」→「シーンを作る (Build Scene)」を押す（1〜2分かかる）。
4. 再生ボタン（▶）を押すと走れる。

【操作】
W/↑ アクセル　S/↓ ブレーキ（止まっていればバック）　A/D または ←/→ ハンドル
Space サイドブレーキ　C 視点切り替え　R スタートへ戻る　（ゲームパッドも可）
スタートラインを越えると計測開始、ゴールラインで止まり、4秒後にスタートの手前へ戻る。

【中身】
Data/heights.bytes … 地形の高さ（12km 四方、2049×2049、16bit）
Data/road.json     … 道の中心線（約13.7km、4m 間隔）・バンク・スタート/ゴールの位置
Editor/TurnpikeBuilder.cs … シーンを自動で組み立てるスクリプト
Scripts/ … 車（TPCar）・カメラ（TPCamera）・タイム計測（TPRace）

【地図データの出典】
道路の形: © OpenStreetMap contributors（ODbL） https://www.openstreetmap.org/copyright
標高: 国土地理院 標高タイル https://maps.gsi.go.jp/development/ichiran.html
