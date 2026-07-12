# CLAUDE.md

このプロジェクトのAIエージェント向けガイドは @AGENTS.md にまとめてある(Codex等と共用)。
作業前に必ず読むこと。要点:

- `models/` 配下は生成物。直接編集せず `tools/gen_motions.py` を編集して再生成する
- モーション追加は AGENTS.md の「標準パイプライン」の順で実行する
- 完了条件: `tools/validate_motions.py` が exit 0 + `tools/verify_browser.sh` の目視確認
