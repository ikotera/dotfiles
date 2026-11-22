---
name: obsidian-report
description: knowledge-base vault の 06_Reports にレポート（ある目的のために比較的分量のある情報を1つの読み物にまとめた論考）を作成・改訂するときに使う。properties・タイトル・目的・要約・本文・考察・参考情報の型で書き、セッション外の情報も取得して補強し、既存の atomic note・MOC にリンクし、不足する atomic note を作成し、図・グラフ・表・数式で直感的に示す。「〜をレポートにまとめて」「06_Reports に〜のレポートを」といった依頼で起動する。
---

# Obsidian Report

目的に沿って通読できる論考（`type: report`）を `06_Reports` に作るスキル。distill（セッションの索引）・atomic note（1概念）・MOC（トピックのハブ）と並ぶ4つ目の型で、結論・根拠・考察を本文に持つ。

## 必ず参照するファイル

作成・編集の前に読む：

1. `references/report-workflow.md` — 手順（Phase 1〜9）と落とし穴
2. `references/report-template.md` — レポートの骨格
3. `references/vocabulary.md` — `type: report` のキー定義と語彙
4. `references/obsidian-rules.md` — 保存先・命名・Wikilink・図の保存
5. `references/atomic-template.md` / `references/atomic-workflow.md` — 不足する atomic note を作るとき
6. `references/moc-workflow.md` — MOC へ接続するとき

これらは dotfiles の `shared-references/` にある正本の写し（ローカルでは `~/Github/dotfiles/` への symlink、クラウドでは実体のコピー）。この skill の `references/` から読み、正本のパスを直接開かない。ただし symlink を辿れない読み取りツール（Hermes の `skill_view` 等）でエラーになった場合に限り、正本 `~/Github/dotfiles/shared-references/<ファイル名>` を通常のファイル読み取りで読む。

## ワークフロー（要約。詳細は report-workflow.md）

1. 目的と読者を確定する（目的欄に1〜3文）。
2. 既存の distill・MOC・atomic note・レポートを棚卸しし、過去の議論を参照する。
3. セッション外の情報を一次情報から取得し、主張ごとに確度（確立・文献あり・推測）を付ける。論点が多ければサブエージェントに分けて並行調査させ、出典 URL と確認状況を構造化して返させる。
4. 章立てと、章ごとの図・表・式を先に決める。
5. 不足する atomic note を作る（レポートの依頼に含まれるものとして扱い、候補提示のゲートは省略して事後報告する）。並行作成時は、作るノート名の一覧を全員に渡す。
6. 図を `11_Images` に自己完結 SVG で作り、ブラウザで描画を目視確認する。数値は1つのスクリプトの出力を正本にする。
7. 本文を書く（目的→要約→本文→考察→参考情報→改訂履歴）。
8. リンク解決・自己参照・frontmatter・数値・出典をスクリプトと目視で検証する。
9. MOC へ接続する（既存 MOC は更新、新設は群分け草案を提示してユーザーの合意を取る）。
10. vault を commit・push し、作成・更新したファイル、未確認の主張、MOC の扱いを報告する。

## ハードルール

- 保存先は `06_Reports/<タイトル>.md`。タイトル＝ファイル名＝H1。
- frontmatter は `vocabulary.md` の「キー定義（report）」に従う。`status` は `draft` → `final`。`updated` は使わない。
- 骨格（properties・タイトル・目的・要約・本文・考察・参考情報）を省かない。
- 数値は開いて確認した出典のものだけを使い、確認できないものは「未確認」と書く。推測は推測と明記する。
- 用語の定義・導出の本体は atomic note に置き、レポートはリンクする。
- 数式は `$$...$$`＋`\tag{n}` の通し番号、全変数に意味と単位。`$...$` の中に日本語を入れない。
- 結果の表は画像にせず Markdown 表で書く。図には読み方を1〜3文添える。
