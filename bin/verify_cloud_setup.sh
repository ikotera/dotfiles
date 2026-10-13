#!/bin/bash
# クラウドセッションのどのリポジトリでも実行できる。~/.claude 配下が dotfiles を指しているか確認する。
set -uo pipefail

pass=0
fail=0
ok() { echo "OK   $1"; pass=$((pass + 1)); }
ng() { echo "NG   $1"; fail=$((fail + 1)); }
warn() { echo "WARN $1"; }

CLAUDE_DIR="$HOME/.claude"

echo "=== 1. ~/.claude/CLAUDE.md ==="
if [ -L "$CLAUDE_DIR/CLAUDE.md" ] && [ -f "$CLAUDE_DIR/CLAUDE.md" ]; then
  real="$(readlink -f "$CLAUDE_DIR/CLAUDE.md")"
  DEST="$(dirname "$real")"
  ok "~/.claude/CLAUDE.md -> $real"
else
  ng "~/.claude/CLAUDE.md が dotfiles への symlink になっていない"
  DEST=""
fi
grep -q '^@instructions/shared-instructions\.md$' "$CLAUDE_DIR/CLAUDE.md" 2>/dev/null \
  && ok "CLAUDE.md が @instructions/shared-instructions.md を import している" \
  || ng "CLAUDE.md に @instructions/shared-instructions.md の import が無い"

echo ""
echo "=== 2. ~/.claude/instructions（相対 import の解決先） ==="
[ -f "$CLAUDE_DIR/instructions/shared-instructions.md" ] \
  && ok "~/.claude/instructions/shared-instructions.md が読める" \
  || ng "~/.claude/instructions/shared-instructions.md が読めない"

echo ""
echo "=== 3. skills ==="
if [ -n "$DEST" ] && [ -d "$DEST/skills" ]; then
  for s in "$DEST"/skills/*/; do
    name="$(basename "$s")"
    [ -f "$s/SKILL.md" ] || continue
    target="$CLAUDE_DIR/skills/$name"
    if [ ! -f "$target/SKILL.md" ]; then
      ng "skill $name が ~/.claude/skills に見えていない"
      continue
    fi
    links="$(find "$target" -type l 2>/dev/null | wc -l | tr -d ' ')"
    if [ -L "$target" ] || [ "$links" != "0" ]; then
      ng "skill $name に symlink が残っている（references がツールから見えない原因になる）"
    elif [ -d "$s/references" ] && ! diff -rq "$s/references" "$target/references" >/dev/null 2>&1; then
      ng "skill $name の references が dotfiles と食い違う"
    else
      refs="$(find "$target/references" -type f 2>/dev/null | wc -l | tr -d ' ')"
      ok "skill $name は実体のコピー（references の実ファイル: $refs 件）"
    fi
  done
fi

echo ""
echo "=== 4. RTK（ローカル限定ツール）の参照が無いか ==="
if [ -n "$DEST" ] && grep -q "RTK" "$DEST/CLAUDE.md" "$DEST/instructions/shared-instructions.md" 2>/dev/null; then
  ng "CLAUDE.md / shared-instructions.md にRTK参照が残っている"
else
  ok "CLAUDE.md / shared-instructions.md にRTK参照なし"
fi

echo ""
echo "=== 5. dotfiles の鮮度（環境がキャッシュされている場合の遅れ） ==="
if [ -n "$DEST" ] && [ -d "$DEST/.git" ]; then
  local_head="$(git -C "$DEST" rev-parse HEAD 2>/dev/null)"
  remote_head="$(git -C "$DEST" ls-remote origin HEAD 2>/dev/null | head -1 | cut -f1 || true)"
  if [ -z "$remote_head" ]; then
    warn "リモートのHEADを取得できなかったため鮮度は未確認（ローカル: ${local_head:0:7}）"
  elif [ "$local_head" = "$remote_head" ]; then
    ok "dotfiles は最新（${local_head:0:7}）"
  else
    warn "dotfiles がリモートより古い（ローカル ${local_head:0:7} / リモート ${remote_head:0:7}）。環境設定スクリプトの # rev を上げて再構築する"
  fi
else
  warn "dotfiles が git clone ではないため鮮度は未確認"
fi

echo ""
echo "--------------------------------------------------"
echo "結果: $pass 件OK / $fail 件NG"
[ "$fail" -eq 0 ] && exit 0 || exit 1
