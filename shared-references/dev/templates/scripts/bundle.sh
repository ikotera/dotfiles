#!/bin/bash
# アプリ（<NAME>.app）を作り、必要なら /Applications に入れる。
#
#   scripts/bundle.sh            # dist/<NAME>.app を作る
#   scripts/bundle.sh --install  # 作ってから /Applications に入れる（動いていれば終了させてから置き換える）
#
# 版は Cargo.toml の [workspace.package] version から取る。署名はアドホック（この Mac で使うため）。
# 出自: file-classifier の scripts/bundle.sh を一般化（dotfiles/shared-references/dev/templates）
set -euo pipefail

cd "$(dirname "$0")/.."

# ---- プロジェクトごとに書き換える ----
NAME="<project>"                   # .app の名前と、GUI の実行ファイル名
BUNDLE_ID="com.ikotera.<project>"
GUI_CRATE="<p>-app"                # GUI のクレート
CLI_CRATE="<p>-cli"                # 同梱する CLI のクレート（不要なら空にする）
CLI_BIN="<p>"                      # 同梱する CLI の実行ファイル名
ICON_SYMBOLS=(app.fill)           # make_icon.swift に渡す SF Symbol（主、右下）
MIN_MACOS=13.0
CATEGORY=public.app-category.productivity
# --------------------------------------

VERSION=$(sed -n '/^\[workspace.package\]/,/^\[/s/^version = "\(.*\)"/\1/p' Cargo.toml)
APP=dist/$NAME.app

echo "==> $NAME $VERSION をビルド"
if [[ -n "$CLI_CRATE" ]]; then
  cargo build --release -p "$GUI_CRATE" -p "$CLI_CRATE"
else
  cargo build --release -p "$GUI_CRATE"
fi

echo "==> $APP を作る"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "target/release/$NAME" "$APP/Contents/MacOS/$NAME"
# CLI も同梱する。端末から使うときは Contents/MacOS/<CLI_BIN> を PATH の通った所にリンクする
if [[ -n "$CLI_CRATE" ]]; then
  cp "target/release/$CLI_BIN" "$APP/Contents/MacOS/$CLI_BIN"
fi

# アイコン: scripts/make_icon.swift で描いた PNG から icns を作る
ICONSET=$(mktemp -d)/AppIcon.iconset
mkdir -p "$ICONSET"
swift scripts/make_icon.swift "$ICONSET/src.png" "${ICON_SYMBOLS[@]}"
for s in 16 32 128 256 512; do
  sips -z $s $s "$ICONSET/src.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  sips -z $((s * 2)) $((s * 2)) "$ICONSET/src.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
rm "$ICONSET/src.png"
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$NAME</string>
  <key>CFBundleDisplayName</key><string>$NAME</string>
  <key>CFBundleExecutable</key><string>$NAME</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>CFBundleDevelopmentRegion</key><string>ja</string>
  <key>LSMinimumSystemVersion</key><string>$MIN_MACOS</string>
  <key>LSApplicationCategoryType</key><string>$CATEGORY</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSSupportsAutomaticGraphicsSwitching</key><true/>
</dict>
</plist>
PLIST

codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"
echo "==> 作成: ${APP}（$(du -sh "$APP" | cut -f1)）"

if [[ "${1:-}" == "--install" ]]; then
  DEST=/Applications/$NAME.app
  # 動いていれば終了させる（置き換え中に古い実行ファイルが使われないように）
  osascript -e "tell application id \"$BUNDLE_ID\" to quit" >/dev/null 2>&1 || true
  pkill -x "$NAME" 2>/dev/null || true
  rm -rf "$DEST"
  ditto "$APP" "$DEST"
  # Launchpad・Spotlight にすぐ出るよう、Launch Services に登録し直す
  /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$DEST"
  echo "==> インストール: ${DEST}"
fi
