#!/usr/bin/env bash
# GridCraft (storytold/gridcraft) を最新の main に同期し、release ビルドする。
# 使い方: gridcraft-update [--run [アプリへの引数...]]
#   --run を付けると、ビルド後にデスクトップアプリを起動する。
# 環境変数 GRIDCRAFT_DIR でクローン先を変更できる（既定: ~/Github/GridCraft）。
set -euo pipefail

REPO_URL="https://github.com/storytold/gridcraft.git"
DIR="${GRIDCRAFT_DIR:-$HOME/Github/GridCraft}"

if [ ! -d "$DIR/.git" ]; then
  echo "==> clone: $REPO_URL -> $DIR"
  git clone "$REPO_URL" "$DIR"
fi
cd "$DIR"

# ローカル変更があれば同期を止める（上書きで失わないため）
if [ -n "$(git status --porcelain)" ]; then
  echo "!! $DIR に未コミットの変更があります。退避（git stash）してから再実行してください。" >&2
  git status --short >&2
  exit 1
fi

before="$(git rev-parse --short HEAD)"
echo "==> sync: origin/main"
git fetch --prune origin
git checkout -q main
git merge --ff-only origin/main
after="$(git rev-parse --short HEAD)"
if [ "$before" = "$after" ]; then
  echo "    既に最新 ($after)"
else
  echo "    $before -> $after"
  git log --oneline "$before..$after" | head -20
fi

echo "==> build: cargo build --release (gridcraft, gridcraft-cli)"
cargo build --release --locked -p gridcraft -p gridcraft-cli

echo "==> 完了: $DIR/target/release/gridcraft"

if [ "${1:-}" = "--run" ]; then
  shift
  exec "$DIR/target/release/gridcraft" "$@"
fi
