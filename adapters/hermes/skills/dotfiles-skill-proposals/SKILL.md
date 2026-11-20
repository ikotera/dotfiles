---
name: dotfiles-skill-proposals
description: Use for skill-proposals review. Apply only approved edits.
---

# dotfiles の共有スキルへの変更提案を処理する

Hermes（自動スキル改善や skill_manage）が dotfiles の共有スキルを書き換えようとすると、dotfiles-bridge プラグインがそれを止め、変更内容を `~/.hermes/skill-proposals/<日時>-<スキル名>.md` に保存する。このスキルは、その提案をユーザーと確認して反映するための手順。

「スキルの提案を確認」「skill-proposals を見て」等の依頼、または提案がたまっているときに使う。

## 手順

1. `~/.hermes/skill-proposals/` の `.md` を古い順に一覧にする（`applied/`・`rejected/` は除く）。無ければ「提案なし」と伝えて終わる。
2. 提案ごとに、対象のスキルの現在のファイルを `read_file` で読み、提案の内容と比べる。
   - 共有スキルの正本は `~/Github/dotfiles/skills/<名前>/`（Hermes 専用は `~/Github/dotfiles/adapters/hermes/skills/<名前>/`）。
   - `references/` は `~/Github/dotfiles/shared-references/` への symlink なので、編集するのは symlink の先（正本）。symlink を普通のファイルで置き換えない。
3. 提案ごとに、変更点の要約・Claude Code と Codex への影響・推奨（採用／修正して採用／見送り）をまとめ、ユーザーに選んでもらう。同じ内容の提案がいくつもある場合はまとめて示す。
4. 採用された提案だけを `patch`（または `write_file`）で正本に反映する。dotfiles-bridge が承認を求めるので、ユーザーが承認する。
   - 提案が Hermes 固有の内容（Hermes のツール名や仕組みに依存）なら、共有スキルに入れず、`adapters/hermes/skills/` 側のスキルか `instructions/hermes-instructions.md` に入れるよう提案する。
   - 他のエージェントでも通じる書き方に直す（`skill_view` などの Hermes のツール名に依存しない）。
5. 反映したら dotfiles で `commit` → `push`（`main`）する。報告ではどのリポジトリのどのブランチへ push したかを明記する。
6. 処理した提案ファイルを `applied/` か `rejected/` へ移し、先頭の「状態」を `採用（<commit>）`／`見送り（理由）` に書き換える。

## 守ること

- ユーザーの承認なしに正本へ反映しない。
- `skill_manage` で共有スキルを編集しようとしない（プラグインが止める）。正本の編集には `patch` / `write_file` を使う。
