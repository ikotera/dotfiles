# Hermes Agent 用アダプタ

Hermes Agent（Nous Research）を dotfiles の共通設定につなぐための、Hermes 専用の設定一式。
共有できるもの（規約・スキル・整形ポリシー）は既存の正本をそのまま読ませ、Hermes の仕組みに依存する部分だけをここに置く。

```text
adapters/hermes/
  setup.sh          # 何度実行してもよいセットアップ（下記）
  plugin/           # Hermes プラグイン dotfiles-bridge（~/.hermes/plugins/dotfiles-bridge へ symlink）
    plugin.yaml
    __init__.py     #  1) 共通規約の注入  2) terminal コマンドの RTK 化  3) 共有スキルの保護
  SOUL.md           # Hermes の人格設定（~/.hermes/SOUL.md へ symlink）
  skills/           # Hermes の仕組みに依存するスキル（skills.external_dirs で読み込み）
    dotfiles-skill-proposals/   # 共有スキルへの変更提案を確認・反映する手順
```

## 他のエージェントとの対応

| 共有したいもの | Claude Code | Codex CLI | Hermes |
|---|---|---|---|
| 共通規約 `instructions/shared-instructions.md` | `CLAUDE.md` の `@import` | `AGENTS.md` の `@import` | dotfiles-bridge がセッション開始時にファイルから読み、システムプロンプトの節として注入 |
| 固有の差分 | `CLAUDE.md` 本文 | — | `instructions/hermes-instructions.md`（同じく注入。食い違えばこちらを優先） |
| スキル `skills/` | `~/.claude/skills/<名前>` へ1件ずつ symlink | — | `skills.external_dirs: [~/.agents/skills, adapters/hermes/skills]`（読み取り専用） |
| RTK | PreToolUse フック `rtk hook claude` | `~/.codex/RTK.md` の指示 | dotfiles-bridge の `pre_tool_call` が `rtk rewrite` で書き換え |
| 出力整形チェック `policy/check_formatting.py` | Stop フック `adapters/claude/stop_hook.py` | — | **使わない**（下記） |
| メモリー | `~/.claude/` | `~/.codex/memories/` | `~/.hermes/memories/`（公開リポジトリには置かない） |

## 共有スキルの保護（提案してから反映）

Hermes には会話のあとに自動でスキルを改善する機能（background review）があり、`skills.external_dirs` のスキルも中身の書き換えは許されている（削除だけ禁止）。dotfiles は `bin/sync.sh` が30分ごとに公開リポジトリへ push し、Claude Code・Codex も同じスキルを読むため、dotfiles-bridge の `pre_tool_call` で次のように振り分ける。

| 操作 | 対象 | 扱い |
|---|---|---|
| `skill_manage`（自動改善を含む） | dotfiles の `skills/`・`adapters/hermes/skills/` のスキル | 止める。内容を `~/.hermes/skill-proposals/<日時>-<スキル名>.md` に提案として保存 |
| `write_file` / `patch` | 上記と `shared-references/` の下のファイル | 承認を求める（ユーザーが採用を決めたときの反映用） |
| それ以外 | Hermes 自身のスキル（`~/.hermes/skills/`）・メモリー・curator | 干渉しない |

提案の確認と反映は、Hermes に「スキルの提案を確認して」と頼む（スキル `dotfiles-skill-proposals`）。

あわせて `bin/sync.sh` は、`skills/*/references/` の symlink が実ファイルに変わった変更を自動 commit しない。Hermes の `skill_manage` は、まとめて行う操作が失敗すると巻き戻しのためにスキルのファイルを書き戻し、そのとき `references/` の symlink を実ファイルに置き換えてしまう（2026-11-20 に実際に起きた）。

## setup.sh がすること

1. `plugin/` を `~/.hermes/plugins/dotfiles-bridge` に symlink し、`hermes plugins enable` で有効化する。
2. `SOUL.md` を `~/.hermes/SOUL.md` に symlink する（既存の実ファイルは `*.pre-dotfiles.<日時>` に退避）。
3. `hermes config set skills.external_dirs` に `~/.agents/skills` と `adapters/hermes/skills` を登録する。
4. `OBSIDIAN_VAULT_PATH` に `~/Github/knowledge-base` を設定する（`~/.hermes/.env`。Hermes 標準の `obsidian` スキルが読む）。
5. `hermes import-agent` が作ったスキルのコピー（`~/.hermes/skills/claude-code-imports/`）のうち、dotfiles と完全に同一のものを消す。

`config.yaml` は丸ごと管理しない。Hermes 自身が状態を書き込むうえ、`hermes config set` 以外で編集すると壊れやすいため、必要なキーだけを `setup.sh` から設定する。設定を変えたら `setup.sh` にも反映する。

## Hermes の制約と、その対応

- **`@import` がない**: Hermes が読むのはカレントディレクトリの `AGENTS.md`／`CLAUDE.md` 等と `SOUL.md` だけ。プラグインの「システムプロンプト節」（1節4,000字・合計8,000字まで）を使う。共通規約は `# ` 見出しごとに分けて複数の節に詰め、上限を超えたら省略して `read_file` で正本を読むよう案内する。節は新しいセッションの作成時に読まれ、そのセッションの間は固定される（プロンプトキャッシュのため）。
- **`skill_view` が symlink の外側を読まない**: `skills/*/references/` は `shared-references/` への相対 symlink なので「Path escapes allowed directory」になる。コピーで回避せず、`hermes-instructions.md` と各 SKILL.md に「そのときは正本を `read_file` で読む」と書いて対応した。
- **出力整形チェックを移さない理由**: `check_formatting.py` の2つの規則（61文字以上の `$...$`、`\[...\]`）は Claude Code の描画の不具合に合わせたもの。Hermes デスクトップは前処理で `\(...\)`・`\[...\]` を KaTeX 用に変換し、`$...$` の長さ制限もない（apps/desktop の `markdown-preprocess.ts` で確認。画面での実測は未実施）。また Hermes で応答をやり直させられるフック（`pre_verify`）は、コードを編集したターンでしか発火しない。Hermes 固有の注意点（`$...$` の中の日本語は描画されない等）は `hermes-instructions.md` に書いた。
- **RTK の書き換え**: `rtk rewrite` の終了コード 0（書き換え）と 3（書き換え・要確認）で書き換え、それ以外は元のまま。失敗・時間切れ（3秒）でも何もしない。`DOTFILES_HERMES_RTK=0` で止められる。

## プラグインを変更したとき

Hermes の会話（デスクトップアプリ、`hermes chat -q` を含む）は常駐の gateway プロセスの中で動き、プラグインのコードは読み込まれた時点のものが使われ続ける。`plugin/__init__.py` を変えたら `hermes gateway restart` を実行する（実行中の会話は中断される）。Hermes アプリを終了して起動し直すだけでは gateway は再起動しない（2026-11-20 に確認）。`instructions/*.md` の変更は再起動なしで次の会話から反映される（節の中身は会話の開始時にファイルから読むため）。

## 動作確認

```bash
hermes plugins doctor dotfiles-bridge          # import と登録が通るか
hermes skills list | grep external              # dotfiles のスキルが external として見えるか
grep "Session plugin prompt section" ~/.hermes/logs/agent.log | tail -3   # 新しいセッションで節が入ったか
```
