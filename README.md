# dotfiles

Claude Code / Codex CLI / Gemini CLI 間で共有する AI エージェント設定（指示書・skills・フック等）の正本。
各マシンの設定ファイルからシンボリックリンクで参照し、Claude Code のクラウドセッションには環境設定のセットアップスクリプトで配信する。

**このリポジトリは公開**。秘密情報（トークン・鍵・個人情報）を置かないこと。自動同期（`bin/sync.sh`）はトークン様の文字列を検知するとコミットを中止する。

## ディレクトリ構成

```text
dotfiles/
  CLAUDE.md                 # Claude Code 用エントリ。@instructions/shared-instructions.md を import（RTKは含めない）
  AGENTS.md                 # Codex CLI 用エントリ。shared-instructions.md に加え @~/.codex/RTK.md も import
  instructions/
    shared-instructions.md  # 全ツール共通の出力整形・回答規約（正本）
    gemini-instructions.md  # Gemini CLI 固有の規約
  skills/<skill-name>/      # Claude Code の Skill（references/ は shared-references/ への相対 symlink）
  shared-references/        # skills から共有参照される規約・テンプレート類の正本
  adapters/claude/stop_hook.py   # Stop フック用アダプタ（policy/check_formatting.py を橋渡し）
  policy/check_formatting.py     # 出力整形ルールの検査本体（ベンダ非依存）
  bin/
    sync.sh                 # ローカル(macOS)の自動同期
    cloud_setup.sh          # クラウド環境: ~/.claude へのリンクを張る
    verify_cloud_setup.sh   # クラウドセッションでの動作確認
```

## CLAUDE.md と AGENTS.md の関係

- Claude Code は `CLAUDE.md`、Codex CLI は `AGENTS.md` というファイル名を読む。規約の実体は `instructions/shared-instructions.md` に一本化している。
- `CLAUDE.md` は `@instructions/shared-instructions.md` という**相対パス**の `@import` を持つ。`@import` の相対パスは「importする側のファイルが読まれた見かけ上のパス」を基準に解決されるため、`~/.claude/CLAUDE.md` から読まれる場合に備えて `~/.claude/instructions` を `instructions/` へのsymlinkにしている。
- **RTK**（[rtk-ai/rtk](https://github.com/rtk-ai/rtk)、bashコマンド出力を圧縮してトークンを節約するCLIプロキシ）はローカルにしかインストールされていない。共有ファイル（`CLAUDE.md`・`shared-instructions.md`）にRTKの `@import` を置くと、クラウドセッションが存在しないファイルを探して無駄な呼び出しをするため、RTKの読み込みはローカルの `~/.claude/CLAUDE.md`（git管理外の実ファイル）に限定している。

## ローカル（macOS）のセットアップ

```bash
git clone https://github.com/ikotera/dotfiles.git ~/Github/dotfiles
ln -sfn ~/Github/dotfiles ~/.agents
ln -sfn ~/Github/dotfiles/skills ~/.claude/skills
ln -sfn ~/Github/dotfiles/instructions ~/.claude/instructions
ln -sfn ~/Github/dotfiles/AGENTS.md ~/.codex/AGENTS.md
ln -sfn ~/Github/dotfiles/instructions ~/.codex/instructions
```

`~/.claude/CLAUDE.md` は symlink ではなく実ファイルにする（`rtk` 未導入なら1行目のみでよい）。

```bash
cat > ~/.claude/CLAUDE.md <<'EOF'
@~/Github/dotfiles/CLAUDE.md

@~/.claude/RTK.md
EOF
```

コミットの作者メールを公開しないため、このリポジトリのコミットはGitHubの noreply アドレスを使う（リポジトリ内のgit設定で指定済み）。

## クラウドセッションへの配信

クラウド環境（Claude Code on the web）の**環境設定のセットアップスクリプト**に次を設定する。ここで `~/.claude/` を用意するので、どのリポジトリに紐づくセッションでも効く。

```bash
#!/bin/bash
# rev: 1
rm -rf "$HOME/dotfiles"
git clone --quiet --depth 1 https://github.com/ikotera/dotfiles.git "$HOME/dotfiles" \
  && bash "$HOME/dotfiles/bin/cloud_setup.sh" \
  || echo "dotfiles setup failed" >&2
```

- 失敗してもセッションの起動を止めないよう `||` で握りつぶす。失敗に気づけるよう `bin/verify_cloud_setup.sh` で確認する。
- 実際のクラウドセッションで、次の3点を確認済み（2026-09-20）。
  - ユーザー全体の `~/.claude/CLAUDE.md` が、別リポジトリのセッションでも読み込まれる。
  - セットアップスクリプトは `CLAUDE.md` の読み込みより前に完了し、`@import` も解決される。
  - skills は `~/.claude/skills/<名前>` に1件ずつリンクすれば自動検出される（`~/.claude/skills/` には標準skillが入っているので、ディレクトリごと置き換えない）。
- **環境はキャッシュされ、セッションごとにはスクリプトが再実行されない。** dotfilesを更新したら、スクリプトの `# rev: N` を上げて（内容を変えて）環境を再構築させる。スクリプトを書き換えると再構築される点は確認済みだが、キャッシュの有効期限そのものは未確認。

### 動作確認

クラウドセッションで次を実行する（`~/dotfiles` はcloneした場所。どのリポジトリのセッションでもよい）。

```bash
bash ~/dotfiles/bin/verify_cloud_setup.sh
```

`~/.claude` 配下のリンク、skillの認識、壊れたsymlink、RTK参照の混入、dotfilesの鮮度（リモートより古ければ警告）を確認し、問題があれば `NG` を表示して `exit 1` になる。

## 自動同期（macOS）

`bin/sync.sh` が `git pull --rebase --autostash` → 変更があればコミット（トークン様の文字列があれば中止）→ `git push` を行う。launchd の LaunchAgent `com.ikotera.dotfiles-sync`（`~/Library/LaunchAgents/com.ikotera.dotfiles-sync.plist`）から30分ごとに実行される。ログは `~/Library/Logs/dotfiles-sync/sync.log`。

launchd は最小限の `PATH` しか渡さず、`git` が Xcode Command Line Tools のスタブに解決されてライセンス未同意エラーになるため、`sync.sh` 冒頭で `/opt/homebrew/bin` を `PATH` に追加している。

```bash
launchctl print gui/$(id -u)/com.ikotera.dotfiles-sync      # 状態確認
launchctl kickstart -k gui/$(id -u)/com.ikotera.dotfiles-sync   # 即時実行
launchctl bootout gui/$(id -u)/com.ikotera.dotfiles-sync    # 無効化
```

Linux / Windows では同等のスケジューラ（cron・systemd timer・タスクスケジューラ）から `bin/sync.sh` を呼び出す仕組みを別途用意する（Windows は移植版が必要）。

## 経緯

`ikotera/agents`（旧）→ private の `ikotera/dotfiles` → `ikotera/knowledge-base` 内の `dotfiles/` へ統合、を経て、現在の公開リポジトリになった。クラウド環境ではセッションに紐づいたリポジトリ以外のprivateリポジトリへgitアクセスできず（PATを設定しても不可）、submodule・起動時cloneのいずれも成立しなかったため。公開リポジトリなら認証なしでcloneできることをクラウドセッションで確認し、この構成に落ち着いた。旧リポジトリの履歴は非公開のアーカイブ（`ikotera/dotfiles-archive`）に残している。
