---
name: dotfiles-skill-proposals
description: Use when skill proposals are pending. Judge and apply them.
---

# dotfiles の共有スキルへの変更提案を処理する

Hermes の自動スキル改善や `skill_manage` が dotfiles の共有スキルを書き換えようとすると、dotfiles-bridge が止め、変更内容を `~/.hermes/skill-proposals/<日時>-<スキル名>.md` に保存する。このスキルは、提案の採否を自分で判断し、反映するための手順である。

「スキルの提案を確認」「skill-proposals を見て」等の依頼、または未処理の提案があるときに使う。

## 手順

1. `~/.hermes/skill-proposals/` の `.md` を古い順に一覧にする（`applied/`・`rejected/` は除く）。無ければ「提案なし」と伝えて終わる。
2. 提案ごとに、対象のスキルの現在のファイルを `read_file` で読み、提案の内容と比べる。
   - 共有スキルの正本は `~/Github/dotfiles/skills/<名前>/`（Hermes 専用は `~/Github/dotfiles/adapters/hermes/skills/<名前>/`）。
   - `references/` は `~/Github/dotfiles/shared-references/` への symlink なので、編集するのは symlink の先（正本）。symlink を普通のファイルで置き換えない。
3. 提案ごとに変更点と Claude Code・Codex への影響を検討し、採用／修正して採用／見送りを自分で決める。方針や利用者の好みに関わる、影響が大きい、既存の規定と食い違うなど、判断に迷う場合だけユーザーに確認する。同じ内容の提案はまとめて判断する。
4. 採用または修正して採用と判断した内容を `patch` / `write_file` で正本に反映する。採否の判断と、ツールが編集時に求める承認は別である。
   - Hermes 固有の内容（Hermes のツール名や仕組みに依存）は、共有スキルではなく `adapters/hermes/skills/` 側のスキルか `instructions/hermes-instructions.md` に置く。
   - 共有スキルでは、他のエージェントでも通じる書き方にする（`skill_view` などの Hermes のツール名に依存しない）。
5. 反映したら dotfiles で `commit` → `push`（`main`）する。報告ではどのリポジトリのどのブランチへ push したかを明記する。
6. 処理した提案ファイルを `applied/` か `rejected/` へ移し、先頭の「状態」を `採用（<commit>）`／`修正して採用（<commit>）`／`見送り` に書き換える。

## 守ること

- 判断の理由を `applied/`・`rejected/` の提案ファイルに1行残し、処理したことを返答で短く報告する。
- `skill_manage` で共有スキルを編集しようとしない（プラグインが止める）。正本の編集には `patch` / `write_file` を使う。
