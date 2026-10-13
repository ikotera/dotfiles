#!/bin/bash
# CoreSpotlight（Spotlight / Apple Intelligence の索引）の容量を手動で確認する。
# macOS 27.0 以降、PipelineStorage/Embedding/Journals が処理されずに毎日増え続ける現象を見張るためのもの。
# 実行には、実行元アプリ（ターミナル.app など）にフルディスクアクセスが必要。
#
# 使い方:
#   ~/Github/dotfiles/storage/spotlight-monitor.sh          # 確認して履歴に追記
#   ~/Github/dotfiles/storage/spotlight-monitor.sh --days 14 # 日別の増加を14日分表示（既定7日）
set -uo pipefail

BASE="$HOME/Library/Metadata/CoreSpotlight"
JOURNALS="$BASE/DocumentProcessing/PipelineStorage/Embedding/Journals"
HISTORY="$HOME/Library/Logs/storage-maintenance/spotlight-history.csv"
WARN_GB=15   # Journals がこれを超えたらリセットを検討する目安
DAYS=7
[ "${1:-}" = "--days" ] && DAYS="${2:-7}"

if ! ls "$BASE" >/dev/null 2>&1; then
  echo "読めません: $BASE"
  echo "この端末アプリにフルディスクアクセスを与えてください（システム設定 → プライバシーとセキュリティ → フルディスクアクセス）。"
  exit 1
fi

kb() { du -sk "$1" 2>/dev/null | cut -f1; }
fmt() { awk -v k="$1" 'BEGIN{ if (k>=1048576) printf "%.2fGB", k/1048576; else printf "%.0fMB", k/1024 }'; }

total_kb=$(kb "$BASE")
journal_kb=$(kb "$JOURNALS")
files=$(find "$JOURNALS" -type f | wc -l | tr -d ' ')
oldest=$(find "$JOURNALS" -type f -exec stat -f %Sm -t %Y-%m-%d {} + | sort | head -1)
today=$(date +%Y-%m-%d)

echo "== CoreSpotlight 容量（$today）"
printf '  全体           %s\n' "$(fmt "$total_kb")"
printf '  Embedding/Journals %s（%s ファイル、最古 %s）\n' "$(fmt "$journal_kb")" "$files" "${oldest:--}"

# 日別の増加（ファイルの更新日ごとの合計）
echo
echo "== 直近 ${DAYS} 日の Journals 増加（更新日ごと）"
since=$(date -v-"$((DAYS - 1))"d +%Y-%m-%d)
find "$JOURNALS" -type f -exec stat -f "%Sm %z" -t %Y-%m-%d {} + |
  awk -v s="$since" '$1>=s {b[$1]+=$2; n[$1]++}
       END {for (d in b) {printf "  %s %7.0fMB %5d files\n", d, b[d]/1048576, n[d]; t+=b[d]}
            if (t) printf "  平均  %7.0fMB/日\n", t/1048576/'"$DAYS"'}' | sort
avg_kb=$(find "$JOURNALS" -type f -exec stat -f "%Sm %z" -t %Y-%m-%d {} + |
  awk -v s="$since" -v d="$DAYS" '$1>=s {t+=$2} END {printf "%d", t/1024/d}')

# 前回からの変化（履歴 CSV）
mkdir -p "$(dirname "$HISTORY")"
[ -f "$HISTORY" ] || echo "date,total_kb,journals_kb,files" >"$HISTORY"
prev=$(tail -n +2 "$HISTORY" | tail -1)
echo
if [ -n "$prev" ]; then
  IFS=, read -r pdate _ pjkb _ <<<"$prev"
  days=$(( ( $(date -j -f %Y-%m-%d "$today" +%s) - $(date -j -f %Y-%m-%d "$pdate" +%s) ) / 86400 ))
  diff_kb=$(( journal_kb - pjkb ))
  if [ "$diff_kb" -ge 0 ]; then sign="+"; else sign="-"; fi
  echo "== 前回（$pdate、${days}日前）から: Journals ${sign}$(fmt "${diff_kb#-}")"
  [ "$diff_kb" -lt 0 ] && echo "  減っています。macOS 側で処理が進んだか、リセットされた可能性があります。"
else
  echo "== 初回の記録です（次回から前回比を表示）"
fi
echo "$today,$total_kb,$journal_kb,$files" >>"$HISTORY"

# 目安との比較
journal_gb=$(( journal_kb / 1048576 ))
echo
if [ "$journal_gb" -ge "$WARN_GB" ]; then
  echo "!! Journals が ${WARN_GB}GB を超えました。CoreSpotlight のリセットを検討してください。"
else
  left_kb=$(( WARN_GB * 1048576 - journal_kb ))
  if [ "${avg_kb:-0}" -gt 0 ]; then
    eta=$(( left_kb / avg_kb ))
    echo "目安（${WARN_GB}GB）まで残り $(fmt "$left_kb")。今のペースなら約 ${eta} 日後（$(date -v+"${eta}"d +%Y-%m-%d) ごろ）に到達します。"
  else
    echo "目安（${WARN_GB}GB）まで残り $(fmt "$left_kb")。直近 ${DAYS} 日は増えていません。"
  fi
  echo "履歴: ${HISTORY/#$HOME/~}"
fi
