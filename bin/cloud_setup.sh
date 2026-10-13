#!/bin/bash
set -euo pipefail

DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_DIR="$HOME/.claude"

mkdir -p "$CLAUDE_DIR/skills"
ln -sfn "$DEST/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"
ln -sfn "$DEST/instructions" "$CLAUDE_DIR/instructions"

# skill は symlink ではなく、references/ 内の symlink も実体化したコピーで置く。
# symlink のままだと、ツールが相対リンクを ~/.claude/skills/<名前>/ 基準で文字列解決したり、
# 作業ディレクトリ外の ~/dotfiles を読めなかったりして、規約ファイルが見えなくなるため。
for s in "$DEST"/skills/*/; do
  name="$(basename "$s")"
  [ -f "$s/SKILL.md" ] || continue
  rm -rf "${CLAUDE_DIR:?}/skills/$name"
  cp -RL "${s%/}" "$CLAUDE_DIR/skills/$name"
done
