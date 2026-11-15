#!/usr/bin/env bash
# GridCraft (storytold/gridcraft) を最新の main に同期し、craft-fonts を組み込んで .app にビルドし、
# /Applications に「GridCraft Dev.app」としてインストールする（公式配布版 GridCraft.app は残す）。
#
# 使い方: gridcraft-update [--no-install] [--run [アプリへの引数...]]
#   --no-install  ビルドだけ行い、/Applications へは入れない
#   --run         最後にアプリを起動する（--run より後ろの引数はアプリへ渡す）
# 環境変数:
#   GRIDCRAFT_DIR    GridCraft のクローン先（既定: ~/Github/GridCraft）
#   CRAFT_FONTS_DIR  craft-fonts のクローン先（既定: ~/Github/craft-fonts）
set -euo pipefail

REPO_URL="https://github.com/storytold/gridcraft.git"
FONTS_URL="https://github.com/storytold/craft-fonts.git"
DIR="${GRIDCRAFT_DIR:-$HOME/Github/GridCraft}"
FONTS="${CRAFT_FONTS_DIR:-$HOME/Github/craft-fonts}"
DEST="/Applications/GridCraft Dev.app"
DEV_ID="ai.storyteller.gridcraft.dev"

INSTALL=1
RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --no-install) INSTALL=0; shift ;;
    --run) RUN=1; shift; break ;;
    -h | --help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

# 未コミットの変更があるクローンは同期しない（上書きで失わないため）
sync_repo() { # <dir> <url> <ref>
  local dir="$1" url="$2" ref="$3"
  if [ ! -d "$dir/.git" ]; then
    echo "==> clone: $url -> $dir"
    git clone "$url" "$dir"
  fi
  if [ -n "$(git -C "$dir" status --porcelain)" ]; then
    echo "!! $dir に未コミットの変更があります。退避（git stash）してから再実行してください。" >&2
    git -C "$dir" status --short >&2
    exit 1
  fi
  git -C "$dir" fetch --prune -q origin
  if [ "$ref" = main ]; then
    git -C "$dir" checkout -q main
    git -C "$dir" merge -q --ff-only origin/main
  else
    git -C "$dir" checkout -q --detach "$ref"
  fi
}

# ---- GridCraft ------------------------------------------------------------------------------
before="$(git -C "$DIR" rev-parse --short HEAD 2>/dev/null || echo none)"
echo "==> sync: GridCraft origin/main"
sync_repo "$DIR" "$REPO_URL" main
after="$(git -C "$DIR" rev-parse --short HEAD)"
if [ "$before" = "$after" ]; then
  echo "    既に最新 ($after)"
else
  echo "    $before -> $after"
  [ "$before" = none ] || git -C "$DIR" log --oneline "$before..$after" | head -20
fi

# ---- craft-fonts（公式リリースと同じ版に固定。版は GridCraft の release.yml から読む） ----------------
FONTS_REF="$(sed -n 's/^ *craft-fonts-ref: *\([0-9a-f]\{7,40\}\).*/\1/p' "$DIR/.github/workflows/release.yml" | head -1)"
if [ -z "$FONTS_REF" ]; then
  echo "!! release.yml から craft-fonts-ref を読めませんでした" >&2
  exit 1
fi
echo "==> sync: craft-fonts @ ${FONTS_REF:0:8}"
sync_repo "$FONTS" "$FONTS_URL" "$FONTS_REF"

# ---- ローカルパッチ（bin/patches/gridcraft-*.patch）: ビルドの間だけ当て、終了時に必ず戻す ----------
# 本家で直った（パッチが当たらなくなった）ものは警告して飛ばす。不要になったらファイルを消す。
PATCH_DIR="$(cd "$(dirname "$(readlink "$0" || echo "$0")")" && pwd)/patches"
APPLIED=()
revert_patches() {
  local p
  for p in ${APPLIED[@]+"${APPLIED[@]}"}; do git -C "$DIR" apply -R "$p" || echo "!! 戻せませんでした: $p" >&2; done
  APPLIED=()
}
trap revert_patches EXIT
for p in "$PATCH_DIR"/gridcraft-*.patch; do
  [ -f "$p" ] || continue
  if git -C "$DIR" apply --check "$p" 2>/dev/null; then
    git -C "$DIR" apply "$p"
    APPLIED+=("$p")
    echo "==> patch: $(basename "$p")"
  else
    echo "warning: $(basename "$p") は当たりません（本家で修正済みか、コードが変わった）。当てずに続行します。" >&2
  fi
done

# ---- build: 公式の packaging/macos/package.sh（簡易署名, この Mac の CPU 向け） -------------------
ARCH="$(uname -m)"
[ "$ARCH" = arm64 ] && ARCH=aarch64
echo "==> build: package.sh --arch $ARCH (CRAFT_FONTS_REQUIRED=1)"
CRAFT_FONTS_DIR="$FONTS" CRAFT_FONTS_REQUIRED=1 "$DIR/packaging/macos/package.sh" --arch "$ARCH"
revert_patches
APP="$DIR/target/macos-package/GridCraft.app"
echo "==> 完了: $APP"
echo "    CLI: $DIR/target/$ARCH-apple-darwin/release/gridcraft-cli"

# ---- install: 「GridCraft Dev.app」として公式版と並べる -------------------------------------------
if [ "$INSTALL" = 1 ]; then
  if pgrep -qf "$DEST/Contents/MacOS/"; then
    echo "!! GridCraft Dev が起動中です。終了してから再実行してください（ビルドは完了済み）。" >&2
    exit 1
  fi
  STAGE="$DIR/target/macos-package/dev-install"
  rm -rf "$STAGE"
  mkdir -p "$STAGE"
  ditto "$APP" "$STAGE/GridCraft Dev.app"
  PLIST="$STAGE/GridCraft Dev.app/Contents/Info.plist"
  # 公式版と別のアプリとして扱われるよう ID と表示名を変える（設定フォルダは共通）
  plutil -replace CFBundleIdentifier -string "$DEV_ID" "$PLIST"
  plutil -replace CFBundleName -string "GridCraft Dev" "$PLIST"
  plutil -replace CFBundleDisplayName -string "GridCraft Dev" "$PLIST"
  # Info.plist を変えたので、package.sh と同じ設定で署名し直す
  ENT="$DIR/packaging/macos/entitlements.plist"
  codesign --force --sign - --timestamp=none --options runtime --entitlements "$ENT" \
    "$STAGE/GridCraft Dev.app/Contents/MacOS/GridCraft"
  codesign --force --sign - --timestamp=none --options runtime --entitlements "$ENT" "$STAGE/GridCraft Dev.app"
  codesign --verify --strict --deep "$STAGE/GridCraft Dev.app"
  # 旧版はゴミ箱へ（取り消せるように）
  if [ -e "$DEST" ]; then
    mv "$DEST" "$HOME/.Trash/GridCraft Dev $(date +%Y%m%d-%H%M%S).app"
  fi
  ditto "$STAGE/GridCraft Dev.app" "$DEST"
  rm -rf "$STAGE"
  /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$DEST" || true
  echo "==> install: $DEST ($(git -C "$DIR" rev-parse --short HEAD))"
fi

if [ "$RUN" = 1 ]; then
  if [ "$INSTALL" = 1 ]; then
    exec "$DEST/Contents/MacOS/GridCraft" "$@"
  else
    exec "$APP/Contents/MacOS/GridCraft" "$@"
  fi
fi
