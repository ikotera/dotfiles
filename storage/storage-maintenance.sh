#!/bin/bash
# 内蔵 SSD の自動整理と容量レポート（launchd で週1回: com.ikotera.storage-maintenance）
# - cargo の build-dir（~/.cargo/build.noindex）: 14日使っていない workspace、または 20GB 超の workspace を削除
# - ~/Github 配下の target: 30日使っていないものを削除
# - 容量の大きい場所をログに記録し、空きが 40GB 未満なら通知する
# どれも再ビルド・再ダウンロードで戻るものだけを消す。
set -uo pipefail

BUILD_DIR="$HOME/.cargo/build.noindex"
BUILD_IDLE_DAYS=14
BUILD_CAP_GB=20
TARGET_IDLE_DAYS=30
FREE_WARN_GB=40
LOG_DIR="$HOME/Library/Logs/storage-maintenance"
mkdir -p "$LOG_DIR"
exec >>"$LOG_DIR/storage.log" 2>&1

now=$(date +%s)
echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="

# ビルド中は触らない
if pgrep -x cargo >/dev/null || pgrep -x rustc >/dev/null; then
  echo "cargo/rustc が動いているため整理をスキップ"
  skip_clean=1
fi

# 最後にビルドされた時刻（epoch）を返す。プロファイル配下（深さ2まで）の最新 mtime を使う。
# build-dir 導入後の target には .fingerprint が無く最終成果物だけなので、特定のサブフォルダには頼らない。
last_build() {
  find "$1" -mindepth 1 -maxdepth 2 -exec stat -f %m {} + 2>/dev/null | sort -n | tail -1 | grep . || echo "$now"
}

if [ -z "${skip_clean:-}" ]; then
  if [ -d "$BUILD_DIR" ]; then
    for ws in "$BUILD_DIR"/*/*; do
      [ -d "$ws" ] || continue
      idle=$(( (now - $(last_build "$ws")) / 86400 ))
      size_gb=$(( $(du -sk "$ws" | cut -f1) / 1048576 ))
      if [ "$idle" -ge "$BUILD_IDLE_DAYS" ] || [ "$size_gb" -ge "$BUILD_CAP_GB" ]; then
        echo "削除: ${ws}（${idle}日未使用, ${size_gb}GB）"
        rm -rf "$ws"
      fi
    done
    find "$BUILD_DIR" -mindepth 1 -maxdepth 1 -type d -empty -delete
  fi

  while IFS= read -r tag; do
    t="$(dirname "$tag")"
    idle=$(( (now - $(last_build "$t")) / 86400 ))
    if [ "$idle" -ge "$TARGET_IDLE_DAYS" ]; then
      echo "削除: ${t}（${idle}日未使用, $(du -sh "$t" | cut -f1)）"
      rm -rf "$t"
    fi
  done < <(find "$HOME/Github" -maxdepth 5 -type f -name CACHEDIR.TAG -path '*/target/CACHEDIR.TAG' 2>/dev/null)
fi

# 容量レポート
for p in "$BUILD_DIR" "$HOME/Library/Caches" "$HOME/Library/Developer/CoreSimulator" \
         "$HOME/Library/Application Support/Claude/vm_bundles"; do
  [ -e "$p" ] && printf '%8s  %s\n' "$(du -sh "$p" 2>/dev/null | cut -f1)" "${p/#$HOME/~}"
done
xcrun simctl runtime list 2>/dev/null | grep -E 'Total Disk Images' | sed 's/^/  simulator: /'
free_gb=$(( $(df -k /System/Volumes/Data | awk 'NR==2{print $4}') / 1048576 ))
echo "空き: ${free_gb}GB"

if [ "$free_gb" -lt "$FREE_WARN_GB" ]; then
  osascript -e "display notification \"空きが ${free_gb}GB です。~/Library/Logs/storage-maintenance/storage.log を確認\" with title \"内蔵SSDの空き容量\""
fi
