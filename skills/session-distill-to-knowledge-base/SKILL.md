---
name: session-distill-to-knowledge-base
description: Codex/AI セッションを要約・distill 化・保存し、knowledge-base の distill や atomic note 候補に変換するときに使う。全プロジェクト共通で、特に指定が無ければ出力先は、ローカル実行環境では ~/Github/knowledge-base、クラウド／リモート実行環境では GitHub リポジトリ ikotera/knowledge-base。
---

# Session Distill To Knowledge Base

セッションの要約、スレッドの distill 化、有用な議論の保存、会話の Obsidian ノート化を依頼されたときに使うスキル。

## 必ず参照するファイル

ファイルを作成・編集する前に読む：

1. `references/distill-atomic-workflow.md`
2. `references/vocabulary.md`
3. `references/distill-template.md`
4. `references/atomic-template.md`
5. `references/obsidian-rules.md`
6. `references/moc-workflow.md`

これらは `~/Github/dotfiles/shared-references/` の正本への symlink。

## ワークフロー

「このセッションをdistillしてください」のような一般的な依頼では、確認待ちを挟まず 1〜9 を一気通貫で実行する。ユーザーが依頼時に対象概念やスコープを明示した場合は、その範囲に限定する。

1. 出自となるセッション／会話内容を特定する。
2. `references/distill-atomic-workflow.md` に従って distill を作成する。
3. `type` / `domain` / `tags` / `status` は `references/vocabulary.md` に定義された値だけを使う。
4. distill は「索引＋候補メニュー」として扱い、知識本体（最終成果物）にはしない。
5. atomic note 候補を採番して提示する（distill 内の索引・出自記録として残す）。
6. ユーザーの追加確認を待たず、提示した候補を原則すべて materialize する。
7. materialize 後、distill の `spawned` リストと候補の状態を更新する。
8. MOC への委譲: 全候補を materialize し distill を `status: final` にしたら、トピックごとに MOC が要るか判断する。セッション内に相互の関連性が低い複数のトピックが含まれる場合は、1つの MOC にまとめず話題ごとに分けて判定する。あるトピックに関連する atomic note が3枚以上ある場合、または同一トピックに2枚目の distill がある／全体像の図が欲しい場合は、そのトピックの MOC を作成／更新する。作成する場合は `obsidian-moc` スキルを使うが、本パイプラインでは群分け草案をユーザーに提示して合意を取るヒューマンゲートは省略し、AI が妥当な群分けを判断して作成／更新し、結果を事後報告する。distill の frontmatter に `moc: "[[topic MOC]]"` を追加し、冒頭に `> 成果の統合先: [[topic MOC]]` を置く。群別索引・図といったナビは distill に複製せず MOC へ委譲する。MOC を作らないのは、関連 atomic note が2枚以下、または3枚あっても同一トピックとして束ねる関係が薄いなどの特殊な場面に限り、その理由を明示する。
9. 作成・更新したすべてのファイル（distill／atomic note／該当する場合は MOC・`vocabulary.md`）を git commit し、push する。コミットメッセージには対象トピックと生成物の概要を含める。

## 出力先の既定

- 既定の vault:
  - ローカル実行環境（ローカルファイルシステムから `~/Github/knowledge-base` に直接アクセスできるセッション）: `~/Github/knowledge-base`
  - クラウド／リモート実行環境（Claude Code on the web 等、ローカルに `~/Github/knowledge-base` が存在しないセッション）: GitHub リポジトリ `ikotera/knowledge-base`。まだセッションにアタッチ／クローンしていなければ最初に行い、そのワーキングツリーへ書き出す。
- distill の出力先: `references/distill-atomic-workflow.md` が指定する現行パスに従う（`01_Distills`）
- atomic note の出力先: `references/distill-atomic-workflow.md` が指定する現行パスに従う（`03_Atomic-notes`）
- MOC の出力先（必要な場合）: `02_MOC` — `obsidian-moc` スキルと `moc-workflow.md` を参照

作業中のリポジトリが knowledge-base vault でない場合も、ユーザーが別の出力先を明示しない限り、上記いずれかの knowledge-base vault に書き出す。

## ハードルール

- セッション distill を依頼されたとき、汎用的なチャット要約を出力しない。
- 新しい語彙の値を勝手に作らない。先に追加を提案する。
- 「distillしてください」等の一般的な依頼では、atomic note 候補の提示後にユーザーの追加確認を待たず、materialize・MOC 判定・commit/push まで自動的に完了させる。ユーザーが対象概念やスコープを明示的に限定した場合はその指示に従う。
- knowledge-base ノートを作るときは、ユーザーの日本語の命名・説明スタイルを尊重する。
