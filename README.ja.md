# live2d-add-motion-sample-web-ui

**Cubism Editorを使わず、JSONの追加・編集だけでLive2Dモデルにモーションを追加する**サンプルです。ブラウザで動くWebUI付き。

[English README is here](README.md)

![WebUIのスクリーンショット。左にひよりのアバター、右に今回追加したモーションの再生ボタン一覧](docs/images/webui.png)

<sub>サンプルモデル: ひより・momose ©Live2D(モデルデータは本リポジトリには含まれません)</sub>

## これは何?

Live2Dのモーション(`.motion3.json`)は、パラメータごとのキーフレームカーブを並べたただのJSONです。つまりリグやメッシュを触らなくても、**既存モデルが持っているパラメータの範囲内なら、テキスト編集だけで新しい動きを作れます**。

このリポジトリでは、Live2D公式サンプルモデル「ひより」に次の7モーションをJSONだけで追加しています。

| モーション | 主に使うパラメータ |
|---|---|
| 喜ぶ | 笑顔目(EyeSmile)+ 口角 + 頬 + 体のバウンス |
| ウィンク | 片目開閉 + 首かしげ |
| うなずき | 顔の上下角度(2回うなずき) |
| 考え中 | 首かしげ + 目線そらし + 眉ひそめ |
| びっくり | 目の見開き + 眉上げ + 「お」の口 + のけぞり |
| 照れる | 頬(照れ)+ うつむき + 伏し目 |
| 首ふり | 顔の左右角度の往復 |

再現性を重視して、モーションは手書きせず**生成スクリプト+独立バリデータ+ヘッドレスブラウザ検証**のパイプラインで作っています。AIエージェント(Claude Code / Codex等)に「新しいモーションを追加して」と頼めるよう、エージェント向けドキュメント([AGENTS.md](AGENTS.md))も同梱しています。

## クイックスタート

必要なもの: **Python 3**(標準ライブラリのみ)、**モダンブラウザ**、そして Claude Code / Codex などのコーディングエージェント

```bash
git clone https://github.com/shinshin86/live2d-add-motion-sample-web-ui.git
cd live2d-add-motion-sample-web-ui
```

リポジトリ直下でエージェントを起動し、**モデルの場所を添えて一言依頼するだけ**です:

> `~/Downloads/model.zip` にLive2Dモデルがあります。このモデルにモーションを追加して、ブラウザで確認できるようにしてください。

モデルの配置・セットアップ・モーション設計・生成・検証・サーバー起動まで、すべてエージェントが実行します(作業手順は [AGENTS.md](AGENTS.md) に定義してあり、エージェントが自動で読み込みます)。zipでもフォルダでも、置き場所はどこでも構いません。

モデルを持っていない場合は、公式サンプルモデル[「ひより・momose(hiyori_pro)」](https://www.live2d.com/learn/sample/momose-hiyori/)をダウンロードして試せます(同梱のサンプルモーション定義がそのまま使えます)。

モーションを追加・変更したいときも、依頼するだけです:

> このモデルに「手を振る」モーションを追加してください。既存パラメータで自然に作れない場合は、無理に作らず代替案を提案してください。

### 手動で実行する場合

```bash
python3 tools/setup_model.py <モデルのzipまたはフォルダ>   # 配置 + model.config.json 生成
python3 tools/gen_motions.py        # モーション生成 + 登録
python3 tools/validate_motions.py   # 検証(「OK」が出ること)

python3 tools/serve.py              # サーバー起動 (デフォルトポート: 17342)
# → http://localhost:17342
```

モーション定義はモデルごとに `motion-defs/<モデル名>.py` に置きます(同梱のサンプル定義が例)。別のモデルではパラメータ構成に合わせて定義を新しく書く必要があります — その設計こそがAIエージェントに任せる部分で、定義ファイルは `models/` と同じ作業成果物としてgit管理外になっています(モデルを切り替えてもリポジトリにdiffは出ません)。

## WebUIの使い方

- **今回追加したモーション**(★付きカード)のボタンで再生。既存モーションは折りたたみから展開
- アバターは**ドラッグで移動**、**ホイール/ピンチで拡大縮小**。「表示リセット」で初期配置に戻る
- デバッグ用クエリパラメータ: `?play=Action:0`(自動再生)/ `&freeze=1.2`(指定秒でポーズ固定)/ `?uitest=1`(ドラッグ・ズームの自動テスト)
- UIは英語がデフォルトで、ブラウザの優先ロケールが日本語の場合は自動的に日本語になります。`?lang=en` または `?lang=ja` で切り替えを上書きできます。

## 自分でモーションを追加するには

AIエージェントに任せる場合はクイックスタートの依頼例をそのまま使ってください(モーション名を変えるだけ)。手動でやる場合:

1. `python3 tools/analyze_model.py` — 使えるパラメータ・安全な値域・物理演算が管理するパラメータ(直接動かさない)を確認
2. `motion-defs/<モデル名>.py` にキーフレームを追記(書式は同梱サンプルを参照)
3. 生成 → 検証 → ブラウザ確認:

```bash
python3 tools/gen_motions.py
python3 tools/validate_motions.py
tools/verify_browser.sh   # ヘッドレスChromeでピーク時のポーズを撮影(要Chrome)
```

設計ルール(値域・基本姿勢復帰・物理パラメータ回避など)とモデル固有の知見は [AGENTS.md](AGENTS.md) にまとまっています。人間が読んでも役立ちます。

## リポジトリ構成

```
index.html                  WebUI(静的HTML、ビルド不要)。model.config.json からモデルを解決
tools/
  setup_model.py            モデル配置(zip/フォルダ → models/)+ model.config.json 生成
  analyze_model.py          パラメータ・値域・物理出力の分析
  gen_motions.py            生成エンジン(モデル非依存)。定義から生成+登録(冪等)
  validate_motions.py       独立実装のバリデータ
  serve.py                  ローカルWebUIサーバー(デフォルトポート: 17342)
  verify_browser.sh         ヘッドレスChromeでの実描画検証 ※macOSのChromeパスを想定(env CHROME で変更可)
motion-defs/<モデル名>.py    モーション定義(モデルごとの創作物) [git管理外・同梱サンプルのみ追跡]
AGENTS.md                   AIエージェント向け作業ガイド
model.config.json           [git管理外] 現在のモデル設定(setup_model.pyが生成)
local-assets/ , models/     [git管理外] Live2Dモデルデータ(ライセンス上、非同梱)
```

## ライセンス

このリポジトリの自作部分(HTML/スクリプト/ドキュメント)は [MITライセンス](LICENSE) です。

以下はMITの対象外で、それぞれのライセンスに従います:

- **Live2Dサンプルモデル「ひより」**: [Live2D Free Material License](https://www.live2d.com/eula/live2d-free-material-license-agreement_jp.html) の対象で再配布不可のため非同梱です。各自[公式配布ページ](https://www.live2d.com/learn/sample/momose-hiyori/)から入手してください。READMEのスクリーンショットに含まれるモデルの著作権はLive2D社に帰属します。
- **Live2D Cubism Core**(`live2dcubismcore.min.js`): WebUIがLive2D公式CDNから読み込みます([Live2D Proprietary Software License](https://www.live2d.com/eula/live2d-proprietary-software-license-agreement_jp.html))。本リポジトリはCore自体を再配布していません。組み込んだ製品を事業として公開する場合は、事業規模により[出版許諾契約](https://www.live2d.com/sdk/license/)が必要になることがあります。
- **PixiJS / pixi-live2d-display**: CDNから読み込み(いずれもMITライセンス)。
