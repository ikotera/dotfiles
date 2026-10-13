// アプリのアイコン（1024×1024 の PNG）を描く。scripts/bundle.sh が icns に変換する。
// 使い方: swift scripts/make_icon.swift <出力.png> [主の SF Symbol] [右下に重ねる SF Symbol]
//   例: swift scripts/make_icon.swift icon.png folder.fill tag.fill
// 出自: file-classifier の scripts/make_icon.swift を一般化（dotfiles/shared-references/dev/templates）
import AppKit

let args = CommandLine.arguments
let out = args[1]
let mainSymbol = args.count > 2 ? args[2] : "app.fill"
let badgeSymbol = args.count > 3 ? args[3] : nil

// 背景のグラデーション（上 → 下）と、重ねる記号の色。プロジェクトごとに変える
let topColor = NSColor(calibratedRed: 0.20, green: 0.56, blue: 1.00, alpha: 1)
let bottomColor = NSColor(calibratedRed: 0.04, green: 0.30, blue: 0.84, alpha: 1)
let badgeColor = NSColor(calibratedRed: 1.0, green: 0.62, blue: 0.10, alpha: 1)

let size = 1024.0
let image = NSImage(size: NSSize(width: size, height: size))
image.lockFocus()

// macOS のアイコンの格子に合わせ、周りに余白を取った角丸の四角
let inset = 100.0
let rect = NSRect(x: inset, y: inset, width: size - inset * 2, height: size - inset * 2)
let shape = NSBezierPath(roundedRect: rect, xRadius: 185, yRadius: 185)
NSGraphicsContext.current?.saveGraphicsState()
let shadow = NSShadow()
shadow.shadowColor = NSColor.black.withAlphaComponent(0.3)
shadow.shadowBlurRadius = 24
shadow.shadowOffset = NSSize(width: 0, height: -10)
shadow.set()
NSGradient(colors: [topColor, bottomColor])!.draw(in: shape, angle: -90)
NSGraphicsContext.current?.restoreGraphicsState()

func symbol(_ name: String, points: CGFloat, color: NSColor) -> NSImage {
    let config = NSImage.SymbolConfiguration(pointSize: points, weight: .semibold)
        .applying(NSImage.SymbolConfiguration(paletteColors: [color]))
    guard let base = NSImage(systemSymbolName: name, accessibilityDescription: nil) else {
        fatalError("SF Symbol が見つからない: \(name)")
    }
    return base.withSymbolConfiguration(config)!
}

// 主の記号を中央に
let main = symbol(mainSymbol, points: 430, color: .white)
main.draw(in: NSRect(
    x: (size - main.size.width) / 2, y: (size - main.size.height) / 2 + 40,
    width: main.size.width, height: main.size.height))

// 右下に重ねる記号（背景色の縁取りを付けて重なりを見やすくする）
if let badgeSymbol {
    let badge = symbol(badgeSymbol, points: 240, color: badgeColor)
    let badgeBack = symbol(badgeSymbol, points: 270, color: bottomColor)
    let origin = NSPoint(x: 560, y: 190)
    badgeBack.draw(in: NSRect(x: origin.x - 15, y: origin.y - 15, width: badgeBack.size.width, height: badgeBack.size.height))
    badge.draw(in: NSRect(x: origin.x, y: origin.y, width: badge.size.width, height: badge.size.height))
}

image.unlockFocus()
let rep = NSBitmapImageRep(data: image.tiffRepresentation!)!
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: out))
