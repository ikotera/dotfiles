#!/usr/bin/env bash
# third-party-update.sh — cron（AI を使わないジョブ）用。第三者のエージェント用ツールの更新を確かめ、あれば入れる。
#
#   1. Agent Reach: 新しい版があれば `agent-reach-patch.py --update`（更新して手元の改変を当て直す）。
#      無くても改変が外れていれば当て直す。
#   2. npx skills でグローバルに入れたスキル（~/.agents/.skill-lock.json に載っているもの）: 更新があれば `update -g -y`。
#
# 何も変わらなければ何も出力しない（cron は空の出力を届けない）。変わったときと失敗したときだけ1行ずつ報告する。
set -uo pipefail

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export CI=1   # npx skills の対話を止める
DOTFILES="${DOTFILES:-$HOME/Github/dotfiles}"
PATCH="$DOTFILES/bin/agent-reach-patch.py"
cd "$HOME" || exit 1   # npx skills はプロジェクトの中だとプロジェクトのスキルを見るため、ホームで動かす

report=()

lock_state() {  # lock ファイルの「スキル名@commit」の一覧
  python3 -I - <<'PY'
import json, os
d = json.load(open(os.path.expanduser("~/.agents/.skill-lock.json")))
print(" ".join(f"{k}@{(v.get('commit') or '')[:7]}" for k, v in sorted(d["skills"].items())))
PY
}

# 1. Agent Reach
if command -v agent-reach >/dev/null 2>&1; then
  check="$(agent-reach update --check 2>&1)"
  read -r ok current latest available < <(python3 -I -c '
import json, sys
try:
    d = json.loads(sys.stdin.read().strip().splitlines()[-1]); r = d.get("result") or {}
    print(d.get("ok"), r.get("current"), r.get("latest"), r.get("update_available"))
except Exception:
    print("False ? ? False")' <<<"$check")
  if [ "$ok" != "True" ]; then
    report+=("Agent Reach: 更新の確認に失敗（$(tail -c 300 <<<"$check")）")
  elif [ "$available" = "True" ]; then
    out="$(python3 -I "$PATCH" --update 2>&1)"
    now="$(agent-reach version 2>/dev/null | python3 -I -c 'import json,sys; print((json.load(sys.stdin).get("result") or {}).get("version"))' 2>/dev/null)"
    if [ "$now" = "$latest" ] && ! grep -q "目印が見つからない" <<<"$out"; then
      report+=("Agent Reach: $current → $latest に更新し、手元の改変を当て直した")
    else
      report+=("Agent Reach: $current → $latest の更新か改変の当て直しに失敗（現在 $now）: $(tail -c 400 <<<"$out")")
    fi
  else
    out="$(python3 -I "$PATCH" 2>&1)"
    if grep -q "目印が見つからない\|Error\|Traceback" <<<"$out"; then
      report+=("Agent Reach: 改変の当て直しに失敗: $(tail -c 400 <<<"$out")")
    elif grep -q ": patched$" <<<"$out"; then
      report+=("Agent Reach: 改変が外れていたので当て直した（$current）")
    fi
  fi
fi

# 2. npx skills（グローバル）
if command -v npx >/dev/null 2>&1 && [ -f "$HOME/.agents/.skill-lock.json" ]; then
  check="$(npx -y skills@latest check -g </dev/null 2>&1)"; rc=$?
  if [ $rc -eq 0 ] && grep -q "up to date" <<<"$check"; then
    :
  elif [ $rc -eq 0 ] || [ $rc -eq 1 ]; then
    before="$(lock_state)"
    out="$(npx -y skills@latest update -g -y </dev/null 2>&1)"; urc=$?
    after="$(lock_state)"
    if [ $urc -ne 0 ]; then
      report+=("npx skills: 更新に失敗: $(tail -c 400 <<<"$out")")
    elif [ "$before" != "$after" ]; then
      report+=("npx skills: 更新した（前: $before / 後: $after）")
    fi
  else
    report+=("npx skills: 更新の確認に失敗: $(tail -c 300 <<<"$check")")
  fi
fi

if [ ${#report[@]} -gt 0 ]; then
  echo "第三者ツールの週次更新（$(date '+%Y-%m-%d %H:%M')）"
  printf -- '- %s\n' "${report[@]}"
fi
exit 0
