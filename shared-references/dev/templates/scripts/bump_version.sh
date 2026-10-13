#!/bin/bash
# 版を上げて commit し、注釈付きタグを付ける（dotfiles/shared-references/dev/versioning.md）。
#
#   scripts/bump_version.sh minor "S5: ショートカット変更モード"   # 0.4.0 → 0.5.0
#   scripts/bump_version.sh patch "検索欄の不具合を修正"           # 0.5.0 → 0.5.1
#   scripts/bump_version.sh major "保存形式の変更"                 # 1.3.1 → 2.0.0
#
# 先に PLAN.md（§8.2 のステップ行と §10 の版の履歴）を更新しておく。実装の変更もまとめて
# commit する場合は、実行前に git add しておく（ここでは Cargo.toml・Cargo.lock・PLAN.md だけを足す）。
# push は別に行う: git push origin main --follow-tags
set -euo pipefail

cd "$(dirname "$0")/.."

part=${1:-}
summary=${2:-}
if [[ ! "$part" =~ ^(major|minor|patch)$ || -z "$summary" ]]; then
  echo "使い方: $0 major|minor|patch \"<要約>\"" >&2
  exit 2
fi

current=$(sed -n '/^\[workspace.package\]/,/^\[/s/^version = "\(.*\)"/\1/p' Cargo.toml)
if [[ ! "$current" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
  echo "Cargo.toml の [workspace.package] version を読めない: '$current'" >&2
  exit 1
fi
major=${BASH_REMATCH[1]} minor=${BASH_REMATCH[2]} patch=${BASH_REMATCH[3]}
case $part in
  major) next="$((major + 1)).0.0" ;;
  minor) next="$major.$((minor + 1)).0" ;;
  patch) next="$major.$minor.$((patch + 1))" ;;
esac

if git rev-parse -q --verify "refs/tags/v$next" >/dev/null; then
  echo "タグ v$next は既にある" >&2
  exit 1
fi

# [workspace.package] の中の version 行だけを書き換える（BSD sed と GNU sed の両方で動く書き方）
tmp=$(mktemp)
awk -v next_version="$next" '
  /^\[/ { in_pkg = ($0 == "[workspace.package]") }
  in_pkg && /^version = "/ && !done { print "version = \"" next_version "\""; done = 1; next }
  { print }
' Cargo.toml >"$tmp"
mv "$tmp" Cargo.toml

# Cargo.lock の各クレートの版を合わせる（まずオフラインで試し、足りない物があればダウンロードする）
cargo metadata --format-version 1 --offline >/dev/null 2>&1 || cargo metadata --format-version 1 >/dev/null 2>&1

git add Cargo.toml
[[ -f Cargo.lock ]] && git add Cargo.lock
[[ -f PLAN.md ]] && git add PLAN.md
git commit -m "v$next: $summary"
git tag -a "v$next" -m "v$next: $summary"
echo "版: v$current → v$next（タグ v$next）。push: git push origin main --follow-tags"
