---
name: obsidian-moc
description: knowledge-base vault で MOC（Map of Content／トピックのハブ）を作成・維持・拡充するときに使う。関連する atomic note が3枚以上あるトピックを群別索引＋全体像図で束ねる、複数の distill を統合する、全体像ノートを作る、既存 MOC に新しいノートを取り込む、distill の成果を MOC へ委譲する、といった依頼で起動する。
---

# Obsidian MOC

トピック（領域・主題）軸の恒久ハブ＝ MOC を作成・維持するためのスキル。MOC は概念の説明本体を持たず、散在する atomic note を**群別索引＋全体像（図・語り）**で束ねる「入口」に徹する。distill が「どこから来たか（セッション軸・出自）」を担うのに対し、MOC は「どこへ行けばよいか（トピック軸）」を担う。両者は併用し、統合しない。

## 必ず参照するファイル

ノートを作成・編集する前に読む：

1. `references/moc-workflow.md`
2. `references/vocabulary.md`
3. `references/moc-template.md`
4. `references/obsidian-rules.md`
5. `references/distill-atomic-workflow.md`

これらは `~/Github/dotfiles/shared-references/` の正本への symlink。

## ワークフロー

1. 対象トピックの atomic note を `03_Atomic-notes` から洗い出す（同義語・aliases・英日表記ゆれも確認）。
2. 関連する distill（`01_Distills`）を特定し、`sources` に束ねる候補とする。
3. 既存 MOC があれば新規作成せず更新する（1トピック＝1 MOC）。
4. 群分け（と図の方針）の草案を提示し、ユーザーの合意を取る（ヒューマンゲート）。
5. `moc-template.md` に従い `02_MOC/<トピック名>.md` を作成／更新する。本文は群ごとに `[[ノード]] — 一言` を並べ、説明本体は atomic note へ委譲する。
6. 図は `11_Images` に自己完結 SVG を置き `![[ファイル名.svg]]` で名前埋め込みする。
7. 束ねた distill が `status: final` なら、その frontmatter に `moc: "[[この MOC]]"` を追加し、冒頭に `> 成果の統合先: [[この MOC]]` を置く。
8. リンク解決・群の漏れ重複・frontmatter・図の埋め込みを検証し、変更ファイルを報告する。

## MOC 作成基準

MOC は乱立させないが、関連 atomic note が1つのトピック集合を形成する段階では早めに作る。次のいずれかを満たしたら作成／更新する：

- 同一トピックに関連する atomic note が 3枚以上ある
- 同一トピックに 2枚目の distill が生まれた
- 全体像の図を持たせたい／全体像の語りで個別ノートを橋渡ししたい

MOC を作らないのは、関連 atomic note が 2枚以下、または 3枚あっても同一トピックとして束ねる関係が薄いなどの特殊な場面に限る。その場合は、作らない理由を明示する。

## ヒューマンゲート

群分けと図の方針は大きな構成判断なので、草案を提示してユーザーの合意を取ってから本体を作る。独断で確定しない。

## ハードルール

- MOC は概念の説明本体を持たない（説明は atomic note、出自は distill、MOC は群別索引＋全体像）。
- 1トピック＝1 MOC。重複作成しない。
- frontmatter は `vocabulary.md` の「キー定義（moc）」に従う（`type: moc`、`status` は `seedling`→`growing`→`evergreen`、`sources` は多値）。
- `updated` は使わない。
- 保存先は `02_MOC`、図は `11_Images`。
