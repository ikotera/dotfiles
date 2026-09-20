---
name: obsidian-atomic-notes
description: knowledge-base vault で Obsidian の atomic note を作成・維持・正規化・Wikilink するときに使う。特に既存ノートや未リンク用語から概念ノートを起こす、frontmatter を整える、用語を [[Wikilink]] でつなぐ、といった依頼で起動する。
---

# Obsidian Atomic Notes

既存ノートの整備、欠けている概念ノートの作成、atomic note 化、frontmatter の正規化、Wikilink 補完など、Obsidian knowledge-base の保守に使うスキル。

## 必ず参照するファイル

ノートを作成・編集する前に読む：

1. `references/atomic-workflow.md`
2. `references/vocabulary.md`
3. `references/atomic-template.md`
4. `references/obsidian-rules.md`

これらは `~/Github/dotfiles/shared-references/` の正本への symlink。

## ワークフロー

1. 対象ノートを全文読む。
2. 外部化する用語、または候補語を特定する。
3. 既存ノートを同名・同義語・aliases・英日表記ゆれで検索する。
4. 使える既存ノートがあれば再利用し、概念を重複作成しない。
5. 既存ノートが無ければ、1概念＝1ファイルで atomic note を作成する。
6. 元ノート本文の該当語を自然な範囲で `[[Wikilink]]` 化する。
7. frontmatter を `references/vocabulary.md` に照らして検証する。
8. 作成・更新後に同一トピックの関連 atomic note が3枚以上あるか確認し、該当する場合は `obsidian-moc` / `references/moc-workflow.md` に従って MOC 作成／更新を提案または実行する。

## ヒューマンゲート

作成する用語が明示されていない場合は、まず候補を採番して提示し、どの番号を materialize するか尋ねる。番号指定が来るまで新規ノートを作らない。

## ハードルール

- 1概念＝1ファイル。
- `concept` ノートの `domain` は単一・必須。
- 語彙は `references/vocabulary.md` の値を使う。
- ワークフローで生成するノートに `updated` は付けない。
- frontmatter が関係（`up` / `related` / `source`）を持つなら、本文に `## 関連` や `## 参照` セクションを作らない。
- 関連 atomic note が3枚以上ある同一トピックでは MOC を作成／更新する。MOC を作らないのは、関連 atomic note が2枚以下、または3枚あっても同一トピックとして束ねる関係が薄いなどの特殊な場面に限る。
