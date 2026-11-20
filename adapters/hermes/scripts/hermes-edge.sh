#!/bin/sh
# Hermes 専用の Edge を起動する（Hermes は browser.cdp_url で、この Edge に接続して操作する）。
# 普段の Edge とは別のデータフォルダ（~/.hermes/edge-profile）を使うので、ログインは共有されない。
# Hermes に使わせるサイトにだけ、このウィンドウでログインしておく。
# Hermes に Edge を起動させない理由: 画面なし（headless）で起動し直すとログイン用 Cookie が消えた（2026-11-20）。
set -eu
PORT="${HERMES_EDGE_PORT:-9222}"
DIR="${HERMES_HOME:-$HOME/.hermes}/edge-profile"
if curl -s "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
  echo "already running on port $PORT"
  exit 0
fi
mkdir -p "$DIR" && chmod 700 "$DIR"
open -na "Microsoft Edge" --args --user-data-dir="$DIR" --remote-debugging-port="$PORT" \
  --remote-debugging-address=127.0.0.1 --no-first-run --no-default-browser-check "$@"
