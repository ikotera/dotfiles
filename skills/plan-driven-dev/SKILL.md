---
name: plan-driven-dev
description: アプリやツールを新しく作る・既存のプロジェクトに機能を足す・PLAN.md の要望を実装するときに使う。PLAN.md を唯一の正本にして、要望の転記 → ステップへの割り当て → 実装 → 確認・計測 → 版の更新 → commit・push → 報告 → knowledge-base への distill を毎回同じ型で回す。「新しいプロジェクトを始めたい」「PLAN.md の要望を実装して」「アプリを作って」「Rust で GUI を」「Finder のような」「版を上げて」といった依頼で起動する。
---

# PLAN.md 駆動の開発

個人用のアプリ・ツールを、Rust コア＋用途に応じたフロントエンドで、省資源・心地よさ・堅牢性を満たしながら作るための入口。中身は `references/`（dotfiles の `shared-references/dev/` への symlink）にある。

## 必ず参照するファイル

作業の種類に応じて読む。

| 作業 | 読むファイル |
|---|---|
| 新しいプロジェクトを始める | `references/workflow.md`（A）→ `references/principles.md` → `references/stack-selection.md` → `references/templates/` |
| 要望を実装する（1回分） | `references/workflow.md`（B）→ プロジェクトの `PLAN.md` |
| 画面を作る・参照アプリに寄せる | `references/macos-look-and-feel.md` |
| 版を上げる・報告する | `references/versioning.md` |
| 気づきを残す・distill する | `references/workflow.md`（D）→ skill `session-distill-to-knowledge-base` |

## 必ず守ること

1. **着手前に knowledge-base を調べる**（`workflow.md` の C）。関係する MOC・distill を読み、PLAN §1.4 に書く。
2. **PLAN.md を唯一の正本にする**。チャットでの依頼も §7 に転記し、計画書の外に要望・判断を置かない。
3. **コアを先に、単体テストで固める**。データを壊しうる処理は 計画 → プレビュー → 記録 → 実行 → 取り消し。
4. **計測する**。土台のコストを S0 で測り、性能に関わる変更は PLAN §11 に記録する。
5. **参照アプリに合わせる**。似た標準アプリがあれば、見た目・配置・用語・キー割り当て・メニューの並びまで合わせる。
6. **ステップごとに版を上げ、報告の先頭で伝える**（`版: vX → vY`）。メインの画面に版を常に表示する。
7. **commit・push まで行い、push 先のリポジトリ・ブランチ・タグを報告する**。
8. **気づきを PLAN §12 に1行ずつ書き、たまったら（3件以上・minor 以上の版の更新・会話が長くなったとき）、要約される前に knowledge-base へ distill する**。

## 推測と事実の区別

確かめていない原因や、計測していない性能の見込みは、PLAN と報告に「推測」「未計測」と明記する。
