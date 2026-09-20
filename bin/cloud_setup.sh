#!/bin/bash
set -euo pipefail

DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_DIR="$HOME/.claude"

mkdir -p "$CLAUDE_DIR/skills"
ln -sfn "$DEST/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"
ln -sfn "$DEST/instructions" "$CLAUDE_DIR/instructions"
for s in "$DEST"/skills/*/; do
  ln -sfn "${s%/}" "$CLAUDE_DIR/skills/$(basename "$s")"
done
