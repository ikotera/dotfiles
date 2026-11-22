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

これらは dotfiles の `shared-references/` にある正本の写し（ローカルでは `~/Github/dotfiles/` への symlink、クラウドでは実体のコピー）。この skill の `references/` から読み、正本のパスを直接開かない。ただし symlink を辿れない読み取りツール（Hermes の `skill_view` 等）でエラーになった場合に限り、正本 `~/Github/dotfiles/shared-references/<ファイル名>` を通常のファイル読み取りで読む。

## ワークフロー

「このセッションをdistillしてください」のような一般的な依頼では、確認待ちを挟まず 1〜9 を一気通貫で実行する。ユーザーが依頼時に対象概念やスコープを明示した場合は、その範囲に限定する。

1. 出自となるセッション／会話内容を特定する。distill のファイル名にするセッションのタイトルは、実行環境が付けたタイトルを使い（例: Hermes ならセッション一覧の `title`）、自分で考えた要約タイトルを付けない。
   - 作成前に `03_Atomic-notes` と `02_MOC` で同じ領域の既存ノートを探し、重複を作らず `related`・`up`・MOC の「隣接ハブ」でつなぐ。
   - 同じセッションを追加で distill する場合は、新しい distill を作らず既存の distill に候補を追記し、既存の atomic note は新規作成ではなく追記で更新する。
2. `references/distill-atomic-workflow.md` に従って distill を作成する。
3. `type` / `domain` / `tags` / `status` は `references/vocabulary.md` に定義された値だけを使う。
4. distill は「索引＋候補メニュー」として扱い、知識本体（最終成果物）にはしない。
5. atomic note 候補を採番して提示する（distill 内の索引・出自記録として残す）。
6. ユーザーの追加確認を待たず、提示した候補を原則すべて materialize する。
   - セッションで作った図・チャート・ウィジェット・結果の表・スクリプトやリポジトリは、文章に要約して終わらせず、なるべく多く atomic note に残す（`references/obsidian-rules.md`「ビジュアル・動的な成果物の保存」、`references/distill-atomic-workflow.md` Phase 4）。対話型のチャートはブラウザで描画した静止画（PNG）と HTML の写しを `11_Images` に置き、静止画は撮った後に白紙・途切れがないか確かめる。
   - モデル・シミュレーションを扱ったセッションでは「仕組みのノート」、コードやリポジトリを作ったセッションでは「構成のノート」も作る。
7. materialize 後、distill の `spawned` リストと候補の状態を更新する。
8. MOC への委譲: 全候補を materialize し distill を `status: final` にしたら、トピックごとに MOC が要るか判断する。セッション内に相互の関連性が低い複数のトピックが含まれる場合は、1つの MOC にまとめず話題ごとに分けて判定する。あるトピックに関連する atomic note が3枚以上ある場合、または同一トピックに2枚目の distill がある／全体像の図が欲しい場合は、そのトピックの MOC を作成／更新する。作成する場合は `obsidian-moc` スキルを使うが、本パイプラインでは群分け草案をユーザーに提示して合意を取るヒューマンゲートは省略し、AI が妥当な群分けを判断して作成／更新し、結果を事後報告する。distill の frontmatter に `moc: "[[topic MOC]]"` を追加し、冒頭に `> 成果の統合先: [[topic MOC]]` を置く。群別索引・図といったナビは distill に複製せず MOC へ委譲する。MOC を作らないのは、関連 atomic note が2枚以下、または3枚あっても同一トピックとして束ねる関係が薄いなどの特殊な場面に限り、その理由を明示する。
   - 既存 MOC に項目を足すときは、frontmatter の `sources` がインライン配列（`sources: ["[[a]]", ...]`）かブロック配列（`sources:` の次行から `- `）かを確かめてから追記する。片方の形だけを想定した置換は何も変えずに通り、追記漏れに気づけない。
   - commit 前に、作成・更新したノートの全 `[[Wikilink]]` が vault 内の実在ノートに解決するか、自己参照がないかをスクリプトで確かめる。解決しないリンクは、ノートを作るか通常のテキストに戻す。
9. 作成・更新したすべてのファイル（distill／atomic note／該当する場合は MOC・`vocabulary.md`）を git commit し、push する。コミットメッセージには対象トピックと生成物の概要を含める。
   - `git add` は今回作成・更新したファイルだけをパス指定で行う（`git add -A` を使わない）。vault には Obsidian が書き換える `.obsidian/`（プラグイン更新・表示設定）の未コミット変更が溜まっていることがあり、混ぜると distill のコミットが読めなくなる。
   - 既存の未コミット変更があれば、中身（どのプラグインが何版から何版へ、どの設定が変わったか）を要約して報告し、コミットするかはユーザーに委ねる。依頼されたら別のコミットにする。

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
