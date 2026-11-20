#!/bin/sh
# Hermes 専用の Edge を起動する（Hermes は browser.cdp_url で、この Edge に接続して操作する）。
# 普段の Edge とは別のデータフォルダ（~/.hermes/edge-profile）を使うので、ログインは共有されない。
# Hermes に使わせるサイトにだけ、このウィンドウでログインしておく。
# 通常は dotfiles-bridge プラグインが、Hermes がブラウザを使う直前に自動で起動し、使わない時間が続くと終了する。
# 手で起動したいとき（サイトへのログインなど）はこのスクリプトを直接実行する。
# Hermes 自身に Edge を起動させない理由: 画面なし（headless）で起動し直すとログイン用 Cookie が消えた（2026-11-20）。
set -eu
PORT="${HERMES_EDGE_PORT:-9222}"
DIR="${HERMES_HOME:-$HOME/.hermes}/edge-profile"
if curl -s "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
  echo "already running on port $PORT"
  exit 0
fi
mkdir -p "$DIR" && chmod 700 "$DIR"
# HERMES_EDGE_BACKGROUND=1: 前面に出さず、ウィンドウを隠して起動する（dotfiles-bridge が必要時に起動するとき）
OPEN_FLAGS="-n"
[ "${HERMES_EDGE_BACKGROUND:-0}" = "1" ] && OPEN_FLAGS="-n -g -j"
open $OPEN_FLAGS -a "Microsoft Edge" --args --user-data-dir="$DIR" --remote-debugging-port="$PORT" \
  --remote-debugging-address=127.0.0.1 --no-first-run --no-default-browser-check "$@"
