#!/usr/bin/env bash
# adapters/hermes/setup.sh — Hermes Agent を dotfiles につなぐ（何度実行してもよい）
#
# やること:
#   1. dotfiles-bridge プラグインを $HERMES_HOME/plugins へ symlink して有効化
#      （共通規約の注入と RTK の自動適用。詳細は plugin/__init__.py）
#   2. SOUL.md（Hermes の人格設定）を dotfiles の正本へ symlink
#   3. skills.external_dirs に ~/.agents/skills（無ければ dotfiles の skills/）と adapters/hermes/skills/ を登録
#   4. OBSIDIAN_VAULT_PATH に knowledge-base を設定（$HERMES_HOME/.env）
#   4c. Claude と ChatGPT の使い分け（scripts/apply-model-routing.sh）と残量確認の cron、第三者ツールの週次更新の cron
#   4d. Zed の外部エージェント（ACP）に Hermes を登録（scripts/zed-acp.py）
#   4e. サブエージェントの実行ログを追うコマンドを ~/.local/bin に symlink
#   5. hermes import-agent が作ったコピーのうち、dotfiles と同一で不要になったものを片付ける
#
# 秘密情報・メモリー（MEMORY.md / USER.md）は扱わない。dotfiles は公開リポジトリのため。
set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
KB="${KNOWLEDGE_BASE_DIR:-$HOME/Github/knowledge-base}"
HERE="$DOTFILES/adapters/hermes"

command -v hermes >/dev/null || { echo "hermes が見つかりません" >&2; exit 1; }
mkdir -p "$HERMES_HOME/plugins"

link() {  # link <正本> <リンク>。実ファイルがあれば退避してから張る
  local src="$1" dst="$2"
  if [ -e "$dst" ] && [ ! -L "$dst" ]; then
    mv "$dst" "$dst.pre-dotfiles.$(date +%Y%m%d%H%M%S)"
    echo "退避: $dst"
  fi
  ln -sfn "$src" "$dst"
  echo "link: $dst -> $src"
}

# 1. プラグイン
link "$HERE/plugin" "$HERMES_HOME/plugins/dotfiles-bridge"
hermes plugins enable dotfiles-bridge >/dev/null 2>&1 || hermes plugins enable dotfiles-bridge

# 2. SOUL.md
link "$HERE/SOUL.md" "$HERMES_HOME/SOUL.md"

# 3. 外部スキル（~/.agents/skills は手元の実フォルダ。自作は dotfiles から1件ずつ symlink、
#    第三者のスキルは npx skills・agent-reach が実体を置く。無ければ dotfiles の skills/ を使う）
SHARED_SKILLS="$DOTFILES/skills"
[ -d "$HOME/.agents/skills" ] && [ ! -L "$HOME/.agents" ] && SHARED_SKILLS="~/.agents/skills"
hermes config set skills.external_dirs "[\"$SHARED_SKILLS\", \"$HERE/skills\"]"

# 4. Obsidian の vault
[ -d "$KB" ] && hermes config set OBSIDIAN_VAULT_PATH "$KB"

# 4b. 外部サービスとの連携（URL と設定だけ。OAuth のトークンはマシンごとに `hermes mcp login <名前>` で取る）
mcp_remote() {  # mcp_remote <名前> <URL> [trust]
  hermes config set "mcp_servers.$1.url" "$2"
  hermes config set "mcp_servers.$1.auth" oauth
  hermes config set "mcp_servers.$1.enabled" true
  [ -n "${3:-}" ] && hermes config set "mcp_servers.$1.trust" "$3"
  return 0
}
mcp_remote ibkr https://api.ibkr.com/v1/api/mcp-public untrusted   # 発注など書き込み系は毎回承認
mcp_remote plaud https://mcp.plaud.ai/mcp
# ブラウザ: Hermes 専用の Edge（scripts/hermes-edge.sh で起動、~/.hermes/edge-profile）に接続して操作する。
# Hermes に Edge を起動させると（headless）ログイン用 Cookie が消え、普段のプロファイルを写す
# use_real_profile は Edge を終了していないと使えないため、どちらも使わない。
chmod +x "$HERE/scripts/hermes-edge.sh"
hermes config set browser.use_real_profile false
hermes config set browser.executable_path ""
hermes config set browser.user_data_dir ""
hermes config set browser.cdp_url "http://127.0.0.1:${HERMES_EDGE_PORT:-9222}"

# 4c. Claude と ChatGPT の使い分け（ルート・予備の接続先・裏方処理。手順の正本はスキル quota-aware-routing）
bash "$HERE/scripts/apply-model-routing.sh"
#     cron は ~/.hermes/scripts/ の外を指す symlink を拒むため、コピーで置く（正本は dotfiles）
mkdir -p "$HERMES_HOME/scripts"
for f in quota-status.py quota-alert.sh subscription-snapshot.py third-party-update.sh; do
  install -m 755 "$HERE/scripts/$f" "$HERMES_HOME/scripts/$f"
done
CRON_LIST="$(hermes cron list 2>/dev/null || true)"   # pipefail 下で grep -q に直接つなぐと SIGPIPE で誤判定する
cron_has() { grep -q "Name: *$1\$" <<<"$CRON_LIST"; }
cron_has quota-alert || hermes cron create "every 1h" --no-agent --script quota-alert.sh \
  --name quota-alert --deliver local --catch-up off >/dev/null
#     週次の確認。結果はチャットで受け取りたいので、届け先は作成後に Hermes の中で付け直す（CLI からは local）
cron_has subscription-review || hermes cron create "every monday 9am" "$(cat "$HERE/cron/subscription-review.md")" \
  --name subscription-review --script subscription-snapshot.py --continuity --catch-up on \
  --provider openai-codex --model gpt-6.2-sol --reasoning-effort medium --deliver local >/dev/null
#     第三者ツール（Agent Reach・npx skills）の週次更新。変化か失敗があったときだけ報告する（届け先は上と同じく後で付け直す）
cron_has third-party-update || hermes cron create "every monday 8am" --no-agent --script third-party-update.sh \
  --name third-party-update --deliver local --catch-up on >/dev/null

# 4d. Zed から ACP で Hermes を使う（settings.json の agent_servers に hermes-agent を足す）
#     Dock から起動した Zed は PATH を引き継がないことがあるため、hermes は絶対パスで書く
python3 "$HERE/scripts/zed-acp.py" "$(command -v hermes)"
bash "$HERE/scripts/apply-hermes-patches.sh"

# 4e. Zed のターミナルからサブエージェントの実行ログを追う
mkdir -p "$HOME/.local/bin"
link "$HERE/scripts/hermes-subagent-tail" "$HOME/.local/bin/hermes-subagent-tail"

# 5. import-agent の残骸（dotfiles と完全に同一のコピーだけ消す）
IMPORTS="$HERMES_HOME/skills/claude-code-imports"
if [ -d "$IMPORTS" ]; then
  for d in "$IMPORTS"/*/; do
    [ -d "$d" ] || continue
    name="$(basename "$d")"
    if [ -d "$DOTFILES/skills/$name" ] && diff -rq "$d" "$DOTFILES/skills/$name" >/dev/null 2>&1; then
      rm -rf "$d" && echo "削除（dotfiles と同一）: $d"
    else
      echo "残す（dotfiles と差分あり／正本なし）: $d"
    fi
  done
  rmdir "$IMPORTS" 2>/dev/null || true
fi

echo "完了。新しいセッションから反映されます（hermes を再起動）。"
