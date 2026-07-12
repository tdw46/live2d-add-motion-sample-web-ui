# AGENTS.md — AIエージェント向けガイド

Live2DモデルにJSONだけでモーションを追加し、WebUIで再生確認するプロジェクト。
このドキュメントはAIエージェント(Claude Code / Codex 等)向けの作業手順書。

## 想定される依頼と、そのときやること

ユーザーは細かい手順を知らない前提。典型的な依頼は
**「このモデルにモーションを追加して」**(+モデルのzip/フォルダのパス)だけ。
その場合、以下を自律的に実行する:

1. **モデルの所在を特定** — パスが伝えられていなければ、`local-assets/` と
   リポジトリ内を探す(`*.model3.json` を検索)。見つからなければユーザーに
   モデルの場所を聞く(これはユーザーにしか分からない情報)。
2. **セットアップ** — `python3 tools/setup_model.py <zipまたはフォルダ>`。
   実行用コピーが `models/` に作られ、`model.config.json` に登録される。
   以降のツールとWebUIはすべてこの設定を参照する。
3. **分析** — `python3 tools/analyze_model.py` で利用可能なパラメータ・
   安全値域・物理演算出力(★印)・基本姿勢を把握する。
4. **モーション設計** — 下の「設計ルール」に従い、`motion-defs/<モデル名>.py` を
   このモデル用に書く。モデル名は model3.json のファイル名から拡張子を除いたもの
   (例: `mao_pro.model3.json` → `motion-defs/mao_pro.py`)。書式は同梱サンプル
   `motion-defs/hiyori_pro_t11.py` を参照。パラメータ構成はモデルごとに違うので、
   他モデルの定義を流用せず、analyze結果に合わせて設計し直す。
5. **生成** — `python3 tools/gen_motions.py`(生成 + model3.json登録。冪等)。
   モデルに存在しないパラメータを使うとここでエラーになる。
6. **検証** — `python3 tools/validate_motions.py` が exit 0 になるまで直す。
7. **目視確認** — `tools/verify_browser.sh` でスクリーンショットを撮り、
   表情・ポーズが意図通りかを自分の目で確認する(基本ポーズのままなら失敗)。
8. **引き渡し** — `python3 -m http.server 8765` を起動し、
   http://localhost:8765 で確認できることを伝える。

モーションの「何を作るか」の判断(どの感情表現が作れるか、どのパラメータを
使うか)はエージェントの仕事。機械的な処理はすべてツールがやる。

## リポジトリ構成

```
index.html                 WebUI(静的HTML)。model.config.json からモデルを解決
tools/
  setup_model.py           モデル配置(zip/フォルダ→models/)+ model.config.json 生成
  analyze_model.py         パラメータ一覧・安全値域・物理出力・基本姿勢を出力
  gen_motions.py           生成エンジン(モデル非依存・編集不要)。定義から生成 + model3.json登録(冪等)
  validate_motions.py      独立バリデータ(生成とは別実装)
  verify_browser.sh        ヘッドレスChromeで実描画スクリーンショット
motion-defs/<モデル名>.py   ★モーション定義(モデルごとの創作物・モーションの唯一のソース)
                           [git管理外](同梱サンプル hiyori_pro_t11.py のみ追跡)
model.config.json          [git管理外] 現在のモデル設定(setup_model.pyが生成)
local-assets/              [git管理外] モデル原本置き場
models/                    [git管理外] 実行用モデル。setup+genで完全再構築できる生成物
tmp-verify/                [git管理外] verify_browser.sh の出力
```

重要: `models/` 配下は**生成物**。`.motion3.json` や `model3.json` を直接編集しない。
変更はすべて `motion-defs/<モデル名>.py` を編集して `gen_motions.py` を再実行する。
`tools/` 配下はモデル非依存のエンジンなので、モデルを変えても編集しない。

## 設計ルール(モデルに依らない共通則)

- Cubism Editorでのリグ/メッシュ編集はしない。既存パラメータのみ使う。
- 値は既存モーションの観測値域内に収める(`analyze_model.py` が出力。
  バリデータも同じ基準で落とす)。
- 最終フレームは基本姿勢に戻す(基本姿勢は既存モーションの先頭フレームから
  自動推定される。デフォルト値はモデルごとに違う — 例: ひよりはMouthForm=1)。
- 物理演算の出力パラメータ(★印)はモーションで直接動かさない。
  頭・体の角度を動かせば自然に揺れる。
- PartOpacityの切り替えは、フェードイン/ポップが不自然になるため原則使わない。
- 新規モーションは既存グループを変えず `Action` グループに登録する。
- アクションは `Loop: false`、FadeIn/Out は 0.2〜0.5秒。
- 腕・手はパラメータの意味が読みにくいことが多い。自然な連続パラメータが
  確認できない場合、大きな手振りは作らずに顔・体の表現で代替する。
- 既存モーションを持たないモデルでは値域チェックが効かない。パラメータIDの
  慣習的な範囲(Angle系±30、目0〜1、EyeBall±1など)に保守的に収め、
  目視確認を特に念入りに行う。
- 不自然なモーションは無理に残さず、理由を説明して代替案を提示する。

## モデル固有の癖の見つけ方(ひよりで得た知見を例に)

パラメータの「効き方」はモデルごとに違う。既存モーションの使い方から学ぶこと。
ひよりの例:

- 笑顔目(^^)は **EyeOpen=0 + EyeSmile=1 の組み合わせ**で出る(EyeOpen=1のまま
  Smileを上げてもほぼ変化しない)。既存モーションでの併用パターンを見て発見した。
- MouthForm の基本値は 1(0ではない)。びっくりの「お」の口は -1.5 前後。
- ヨー回転(AngleX)は見た目の変化が控えめで、首ふりは±20以上でないと読み取れない。
- アイドル中の腕位置(ArmLA/RA=-10)のような「置きポーズ」があるので、
  アクションで腕を動かすと前後のつながりが崩れやすい。

新しいモデルでは同種の癖を「既存モーションのカーブの使い方」から再発見する。

## WebUIのデバッグフック(index.html)

| クエリ | 動作 |
|---|---|
| `?play=Action:0` | ロード後に指定モーションを自動再生 |
| `&freeze=1.2` | 再生開始からその秒数でポーズを固定(描画は継続) |
| `?uitest=1` | ドラッグ/ズームを合成イベントで実行し結果をステータス欄に表示 |
| `?model=<path>` | model.config.json を使わず指定モデルを読み込む |

## ヘッドレスブラウザ検証の落とし穴(実測済み・重要)

`tools/verify_browser.sh` を使えばすべて対処済み。自前でやる場合の注意:

- `--virtual-time-budget` では**モーションの時間が進まない**(playing=trueのまま
  0フレーム目で止まる)。実時間 + `--timeout=30000` を使う。
- `--dump-dom` は `--timeout` を待たず load 直後に出力する。状態確認は
  `--screenshot` の画像で行う(ステータス欄の文字列も画像から読める)。
- WebGLは `--disable-gpu` だと初期化に失敗する。
  `--use-angle=swiftshader-webgl --enable-unsafe-swiftshader` を使う。
- スクリーンショットはネットワークアイドル到達後すぐ撮られることがある。
  「何秒後の見た目」の検証はスリープに頼らず `&freeze=` でポーズを固定する。
- キャンバスが空白になる場合: `PIXI.Application` に `preserveDrawingBuffer: true`
  が必要(index.htmlは設定済み)。ticker停止による静止はスクリーンショットに
  写らないので不可(freezeはモーション更新のみ止める方式)。

## 完了条件(Definition of Done)

1. `validate_motions.py` が exit 0
2. `verify_browser.sh` の全スクリーンショットで意図した表情・ポーズが目視確認できる
   (基本ポーズのままなら再生に失敗している。破綻・不自然なフェードがないこと)
3. 既存モーション・既存グループを壊していない(model3.jsonの差分がActionのみ)
4. ユーザーに確認用URL(ローカルサーバー)を案内済み

## ライセンス上の注意

Live2Dのモデルデータは多くの場合再配布不可。`models/` `local-assets/`
`model.config.json` は.gitignore済みで、**コミットしてはならない**。
git管理対象は index.html / tools / ドキュメントのみ。
