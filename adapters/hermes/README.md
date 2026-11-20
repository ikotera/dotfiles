# Hermes Agent 用アダプタ

Hermes Agent（Nous Research）を dotfiles の共通設定につなぐための、Hermes 専用の設定一式。
共有できるもの（規約・スキル・整形ポリシー）は既存の正本をそのまま読ませ、Hermes の仕組みに依存する部分だけをここに置く。

```text
adapters/hermes/
  setup.sh          # 何度実行してもよいセットアップ（下記）
  plugin/           # Hermes プラグイン dotfiles-bridge（~/.hermes/plugins/dotfiles-bridge へ symlink）
    plugin.yaml
    __init__.py     #  1) 共通規約の注入  2) RTK 化  3) 共有スキルの保護  4) 提案の通知  5) 専用 Edge の自動起動・終了
  SOUL.md           # Hermes の人格設定（~/.hermes/SOUL.md へ symlink）
  skills/           # Hermes の仕組みに依存するスキル（skills.external_dirs で読み込み）
    dotfiles-skill-proposals/   # 共有スキルへの変更提案を確認・反映する手順
  scripts/
    google_setup_narrow.py      # Google 連携を Gmail・カレンダーの権限だけで行うラッパー
    hermes-edge.sh              # Hermes 専用の Edge を起動する（Hermes はこれに接続して操作）
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
| `write_file` / `patch` | 上記と `shared-references/` の下のファイル | 編集時に承認を求める（提案の採否とは別） |
| それ以外 | Hermes 自身のスキル（`~/.hermes/skills/`）・メモリー・curator | 干渉しない |

Hermes はスキル `dotfiles-skill-proposals` の手順で Claude Code・Codex への影響を検討し、提案の採否を自分で判断する。判断に迷う提案だけユーザーに確認する。「スキルの提案を確認して」と明示的に頼むこともできる。

未処理の提案が増えると、`pre_llm_call` でその回の発言に通知を添える。Hermes は今回の依頼に答えた後に提案を処理する。急ぎの依頼や別件の作業中なら、区切りのよいときに処理する。システムプロンプトは変えないのでプロンプトキャッシュは崩れない。同じ提案を知らせるのは1つの会話で1回だけで、新しい提案が増えたときにだけ再び知らせる。定期実行（cron）の会話では知らせない。`DOTFILES_HERMES_NOTIFY=0` で止められる。

自動スキル改善が起動するのは、前回の改善または `skill_manage` からツール呼び出しが `skills.creation_nudge_interval`（既定 15）回たまったとき。学ぶことがなければ何も変えない。

あわせて `bin/sync.sh` は、`skills/*/references/` の symlink が実ファイルに変わった変更を自動 commit しない。Hermes の `skill_manage` は、まとめて行う操作が失敗すると巻き戻しのためにスキルのファイルを書き戻し、そのとき `references/` の symlink を実ファイルに置き換えてしまう（2026-11-20 に実際に起きた）。

## 外部サービスとの連携

| サービス | Hermes での方法 | マシンごとに必要な作業 |
|---|---|---|
| GitHub | `gh` CLI | `gh auth login` |
| Interactive Brokers | リモート MCP `https://api.ibkr.com/v1/api/mcp-public`（`trust: untrusted` で書き込み系は毎回承認） | `hermes mcp login ibkr` |
| Plaud | リモート MCP `https://mcp.plaud.ai/mcp` | `hermes mcp login plaud` |
| Gmail・Google Calendar | Hermes 標準スキル `google-workspace` | 下記 |
| Chrome/Edge | Hermes 専用の Edge（`~/.hermes/edge-profile`）を開いておき、`browser.cdp_url` で接続して操作 | 下記 |

URL と設定は `setup.sh` が入れる。トークン・クライアントの秘密情報は `~/.hermes/` に置き、dotfiles には入れない。

**Google**: Google Cloud でデスクトップアプリ用の OAuth クライアントを作り、Gmail API と Google Calendar API を有効にし、自分をテストユーザーに追加する。`google-workspace` の `setup.py` は Drive・Docs・Sheets・連絡先まで一括で要求するので、`scripts/google_setup_narrow.py` で権限を絞る。Hermes の Python（`hermes` の venv、ターミナルの `python`）で実行する。

```bash
python adapters/hermes/scripts/google_setup_narrow.py --client-secret ~/Downloads/client_secret_….json
python adapters/hermes/scripts/google_setup_narrow.py --auth-url     # 出た URL を「外部ブラウザ」で開く
python adapters/hermes/scripts/google_setup_narrow.py --auth-code '<リダイレクト先の URL まるごと>'
```

Hermes デスクトップ内のブラウザで開くと、権限を個別に選べない旧式の同意画面になり、許可しても先へ進まない（2026-11-20 に確認）。許可後の `http://localhost:1/…` は ERR_UNSAFE_PORT で開けないが、それで正常。アドレスバーの URL を渡す。

**Chrome/Edge**: Hermes 専用の Edge（データフォルダ `~/.hermes/edge-profile`、ポート 9222）に `browser.cdp_url: http://127.0.0.1:9222` で接続する。Hermes がブラウザのツールを使う直前に、起動していなければ dotfiles-bridge が `scripts/hermes-edge.sh` で前面に出さずに起動し（約4秒）、ブラウザを使わない時間が 10 分続くと終了する（`DOTFILES_HERMES_EDGE_IDLE_MIN` で変更、0 で終了しない）。手で起動した Edge は終了しない。サイトへのログインは `scripts/hermes-edge.sh` を直接実行して開いたウィンドウで行う。起動中は、同じ Mac のほかのプログラムもこの Edge を操作できる。

試して使わなかった方法（2026-11-20）:

- `browser.use_real_profile`（普段の Edge のプロファイルを写す）: gateway の Python（`~/.hermes/tools/python-3.14.9+…/bin/python3.14`）にフルディスクアクセスを与えれば写せるが、Edge が起動中だとプロファイルがロックされていて使えない。
- `browser.user_data_dir` + `executable_path`（Hermes が専用フォルダで Edge を起動）: ログイン用 Cookie が消えた。原因は headless ではなく、Hermes が `executable_path` の Edge を同梱 Chromium と同じ扱いにして `--use-mock-keychain --password-store=basic` を付けること（`tools/browser_launcher.py` の `packaged = executable is None`）。キーチェーンの鍵で暗号化された Cookie を解けず、捨ててしまう。プロファイルの複製で、このオプションを付けたときだけ再現した（headless・画面ありの両方とも、付けなければ問題なし）。
- Edge 内で別プロファイルを作る: 普段のデータフォルダの中にできるので、上と同じ制約を受ける。

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
- **5時間枠の警告**: Claude / OpenAI の使用率が80%以上なら、`pre_llm_call` が指揮役に毎ターン、自動通知を添える。Claude の5時間枠が80%以上なら基準を厳しくし、自分で行うのは会話・質問への回答と道具を1〜2回使う確認だけとし、要約・下書きも委任する。95%を超えそうなら、ユーザーにメインモデルを OpenAI 側へ切り替えるか尋ねる。フックは `$HERMES_HOME/cache/quota-status-cache.json` を読むだけで、キャッシュがないか10分を超えて古い場合は、`setup.sh` で配置済みの `$HERMES_HOME/scripts/quota-status.py --json` をバックグラウンドで実行して更新する。フック内で同期実行するとタイムアウトの原因になるため、更新を待たない。初回は通知せず、サブエージェントには差し込まない。

## プラグインを変更したとき

Hermes の会話（デスクトップアプリ、`hermes chat -q` を含む）は常駐の gateway プロセスの中で動き、プラグインのコードは読み込まれた時点のものが使われ続ける。`plugin/__init__.py` を変えたら `hermes gateway restart` を実行する（実行中の会話は中断される）。Hermes アプリを終了して起動し直すだけでは gateway は再起動しない（2026-11-20 に確認）。`instructions/*.md` の変更は再起動なしで次の会話から反映される（節の中身は会話の開始時にファイルから読むため）。

## 動作確認

```bash
hermes plugins doctor dotfiles-bridge          # import と登録が通るか
hermes skills list | grep external              # dotfiles のスキルが external として見えるか
grep "Session plugin prompt section" ~/.hermes/logs/agent.log | tail -3   # 新しいセッションで節が入ったか
```
