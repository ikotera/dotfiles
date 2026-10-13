# <project>

AI エージェント（Claude Code・Codex・Gemini）向けの入口。詳細はすべて PLAN.md にある。

## 最初に読む

1. `PLAN.md`（唯一の正本。目的・仕様・要望・ステップ・版・計測・気づきの台帳）
2. dotfiles の開発規約（ローカル `~/Github/dotfiles/shared-references/dev/`、クラウド `~/dotfiles/shared-references/dev/`）: `workflow.md`・`principles.md`・`versioning.md`。読めない環境では下の「規則の要約」に従う。

## 規則の要約

- 要望は PLAN §7 に転記し、§8 のステップに割り当ててから実装する。チャットでの依頼も転記する。
- コア（GUI・OS 非依存）を先に作り、単体テストで固める。データを壊しうる処理は 計画 → プレビュー → 記録 → 実行 → 取り消し。
- 省資源: UI のスレッドで重い処理をしない。性能に関わる変更は計測して PLAN §11 に記録する。
- 見た目と操作感は参照アプリ（PLAN 冒頭）に合わせる。
- ステップを完了するたびに版を上げ（`scripts/bump_version.sh minor|patch|major`）、報告の先頭に `版: vX → vY` と書く。メインの画面に版を常に表示する。
- PLAN.md を更新してから commit し、`git push origin main --follow-tags` する。push 先のリポジトリとブランチを報告する。
- 他のプロジェクトにも役立つ気づきは PLAN §12 に1行書き、たまったら knowledge-base へ distill する。

## コマンド

```bash
cargo test                      # コア・CLI の単体テスト（GUI を含まない既定のビルド対象）
cargo clippy --all-targets
cargo build -p <gui-crate>      # GUI のビルド
scripts/bump_version.sh minor   # 版を上げて commit・タグ
scripts/bundle.sh --install     # .app を作って /Applications に入れる（macOS アプリの場合）
```
