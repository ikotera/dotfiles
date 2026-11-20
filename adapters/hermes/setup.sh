#!/usr/bin/env bash
# adapters/hermes/setup.sh — Hermes Agent を dotfiles につなぐ（何度実行してもよい）
#
# やること:
#   1. dotfiles-bridge プラグインを $HERMES_HOME/plugins へ symlink して有効化
#      （共通規約の注入と RTK の自動適用。詳細は plugin/__init__.py）
#   2. SOUL.md（Hermes の人格設定）を dotfiles の正本へ symlink
#   3. skills.external_dirs に dotfiles の skills/ と adapters/hermes/skills/ を登録
#   4. OBSIDIAN_VAULT_PATH に knowledge-base を設定（$HERMES_HOME/.env）
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

# 3. 外部スキル（~/.agents は dotfiles への symlink。無ければ実体のパスを使う）
SHARED_SKILLS="$DOTFILES/skills"
[ "$(cd "$HOME/.agents" 2>/dev/null && pwd -P)" = "$(cd "$DOTFILES" && pwd -P)" ] && SHARED_SKILLS="~/.agents/skills"
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
# ブラウザ: 既定ブラウザ（Edge/Chrome）のログイン状態を写したプロファイルで操作する
hermes config set browser.use_real_profile true

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
