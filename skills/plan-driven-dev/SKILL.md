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
| 要望を実装する（1回分） | `references/workflow.md`（B）→ プロジェクトの `WISHLIST.md`・`PLAN.md` |
| 画面を作る・参照アプリに寄せる | `references/macos-look-and-feel.md` |
| 版を上げる・報告する | `references/versioning.md` |
| 気づきを残す・distill する | `references/workflow.md`（D）→ skill `session-distill-to-knowledge-base` |

## 必ず守ること

1. **着手前に knowledge-base を調べる**（`workflow.md` の C）。関係する MOC・distill を読み、PLAN §1.4 に書く。
2. **PLAN.md を唯一の正本にし、要望の原文だけは `WISHLIST.md` に置く**。WISHLIST.md は1行1要望で行頭にハイフンを付けず、要望の間に空白行を挟む。補足は空白行を挟まずに改行し、半角スペース2つで字下げした `- ` の箇条書きにする。チャットでの依頼も WISHLIST.md に足してから §7 に転記し、この2つの外に要望・判断を置かない。`WISHLIST.md` が無いプロジェクトでは、着手前に移行する（`workflow.md` の「WISHLIST.md への移行」）。
3. **コアを先に、単体テストで固める**。データを壊しうる処理は 計画 → プレビュー → 記録 → 実行 → 取り消し。
4. **計測する**。土台のコストを S0 で測り、性能に関わる変更は PLAN §11 に記録する。
5. **参照アプリに合わせる**。似た標準アプリがあれば、見た目・配置・用語・キー割り当て・メニューの並びまで合わせる。
6. **ステップごとに版を上げ、報告の先頭で伝える**（`版: vX → vY`）。メインの画面に版を常に表示する。
7. **commit・push まで行い、push 先のリポジトリ・ブランチ・タグを報告する**。
8. **気づきを PLAN §12 に1行ずつ書き、たまったら（3件以上・minor 以上の版の更新・会話が長くなったとき）、要約される前に knowledge-base へ distill する**。

## 開発規約そのものを変えるとき

- 規約の変更は、同じ内容を書いている箇所をすべて同じ commit で揃える: `shared-references/dev/workflow.md`・`shared-references/dev/templates/`（`PLAN.md`・`AGENTS.md` 等）・この SKILL.md・`instructions/shared-instructions.md`・`instructions/gemini-instructions.md`・`README.md`。先に `grep -rn '<旧い言い回し>' instructions shared-references/dev skills/plan-driven-dev README.md` で漏れを洗い出す。一部だけ直すと、エージェントごとに違う規約を読むことになる。
- 既存のプロジェクトに影響する変更には、移行の手順（何を・どこへ・版は上げない単独 commit）を `workflow.md` に書き、移行のタイミング（次に呼び出されたとき等）を明記する。
- Markdown のファイルの書式を決めるときは、規約に書く前に CommonMark の描画（例: `markdown-it` の `md.render()`）で確かめる。

## 複数の要望・外部連携を含む回

- 要望が複数あるときは、独立したまとまりごとに1ステップ（1つの minor 版・1 commit・1 push）に分け、まとまりを1つ終えるたびに push する。全部を1つの commit にまとめると、途中で中断・圧縮されたときに作業が失われ、`git revert` もしにくくなる。
- 外部のエージェント・API と連携する（例: ACP・MCP・OAuth）ときは、設計の前にスクラッチ（`$TMPDIR`）で数十行の試作を作り、実際のメッセージを記録して形を確かめる。確かめた形は、そのまま単体テストの入力に使う。推測で書いたプロトコルの実装は、結合の段階で作り直すことになる。
- 本物の外部サービスを使う結合テストは、`#[ignore]` 等で既定では動かないようにして実行の手順をコメントに書く。そのうえで、少なくとも1回は実際に通してから「確認済み」と報告する。利用枠を消費するので、毎回の `npm test` には含めない。
- 本文を信頼できない入力として表示する UI（HTML メール等）の画面テストでは、仕組みが働いていることを確かめる。無害化で要素が消えたこと、外部の資源の読み込みが方針どおりであること、sandbox 属性が付いていることを assert する。見た目の確認だけで済ませない。

## 推測と事実の区別

確かめていない原因や、計測していない性能の見込みは、PLAN と報告に「推測」「未計測」と明記する。
