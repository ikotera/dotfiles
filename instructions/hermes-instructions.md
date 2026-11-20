# Hermes 固有の規約（shared-instructions.md への差分）
共通規約は `shared-instructions.md`（別節で注入）に従い、Hermes で異なる点だけを次に定める。両者が食い違う場合はこちらを優先する。

## 出力整形（Hermes デスクトップ）
- 数式は `$...$`（インライン）と `$$...$$`（単独行の独立式）を使う。Hermes の描画は `\(...\)`・`\[...\]` も KaTeX に正規化するが、記法は `$` 系に統一する。独立式の番号は式の外に「(1)」と書く。
- `$...$` の中に日本語（CJK）を入れない。その式は数式として描画されず生の文字になる。日本語は式の外に書く。
- 図は ```mermaid フェンスで描く。mermaid で表せない図や操作できる図は、HTML ファイルを書いて `::preview{file="..."}` で表示する。
- 以上は Hermes のレンダラのソース（apps/desktop の markdown-preprocess.ts）で確認したもので、画面での実測ではない。

## スキル
- 他のエージェントでも使う手順の正本は dotfiles の `skills/`。Hermes は `skills.external_dirs` で読み込む。
- dotfiles のスキル（`skills/`・`adapters/hermes/skills/`・`shared-references/`）は公開リポジトリへ自動で push され、Claude Code・Codex も読む。`skill_manage` での書き換えは dotfiles-bridge が止め、内容を `~/.hermes/skill-proposals/` に提案として保存する。改善点に気づいたら提案として残す。反映するかはスキル `dotfiles-skill-proposals` の手順で自分で判断し（迷うときだけユーザーに確認する）、反映には `patch` / `write_file` を使う。
- dotfiles のスキルの `references/` は `shared-references/` への symlink で、`skill_view` では「Path escapes allowed directory」になり読めない。そのときは、エラーに出る実体のパス（`~/Github/dotfiles/shared-references/...`）を `read_file` で読む。
- Hermes の仕組みに依存する手順は dotfiles の `adapters/hermes/skills/` に置く（同じく external_dirs で読み込む）。
- Hermes 自身のスキル（`~/.hermes/skills/`、git 管理外）とメモリーは、これまでどおり自由に作成・改善してよい。他のエージェントでも使えそうなスキルは、dotfiles の `skills/` へ移すことを提案する。

## メモリー
- dotfiles は公開リポジトリのため、MEMORY.md・USER.md（`~/.hermes/memories/`）の内容を dotfiles に書かない。
- 長く残す知見は knowledge-base（Obsidian の vault、`OBSIDIAN_VAULT_PATH`）に atomic note・distill として残す。メモリーには参照先だけを置く。

## コマンド実行
- terminal のコマンドは dotfiles-bridge プラグインが `rtk rewrite` で自動的に RTK 版へ書き換える。`rtk` を手で付ける必要はない。

## モデルの使い分け
- 指揮は Claude（Claude Pro の枠）、実作業はサブエージェント（主に ChatGPT Plus の枠）が担う。`delegate_task` を使う前、重い依頼や表で委任に当たる作業に入る前、サブエージェントの回答を検証するときは、スキル `quota-aware-routing` を読み込み、その手順に従う（残量の確認、ルートの選択、不十分な回答の格上げやり直し）。

| 依頼の型 | 担当 |
|---|---|
| 会話・質問への回答・道具を1〜2回使う確認 | 自分（指揮役） |
| 道具を3回以上使う見込みの作業、ファイルの変更、調査、テストの作成 | サブエージェント（OpenAI 側のルート） |
| ユーザーとのやり取りが要る作業 | 自分。ただし手を動かす部分だけ切り出して委任する |

Claude の5時間枠が80%以上なら基準を厳しくし、自分で行うのは会話・質問への回答と道具を1〜2回使う確認だけとし、要約・下書きも委任する。95%を超えそうなら、ユーザーにメインモデルを OpenAI 側へ切り替えるか尋ねる。

委任しても指揮役のターン（指示・確認）は残るため、道具を1〜2回使えば済む作業は委任するとかえって高くつく。
