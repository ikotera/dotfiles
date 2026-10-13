# 技術選定: Rust コア＋用途に応じたフロントエンド

## 構成の基本形

```text
<project>/                 Cargo ワークスペース（＋必要ならフロントエンドのプロジェクト）
├── crates/<p>-core/       GUI・OS 非依存のコア。仕様・検証・データ操作・安全策・単体テストの大半
├── crates/<p>-mac/        OS 固有の処理（macOS の API。objc2 等）。将来 <p>-win・<p>-linux を並べる
├── crates/<p>-cli/        コアを操作する CLI。GUI 完成前の確認、テスト、一括操作
└── <フロントエンド>        下の候補から選ぶ
```

- 依存の向きは「フロントエンド → OS 固有 → コア」「CLI → コア」。コアはフロントエンドにも OS にも依存しない。
- ワークスペースの `default-members` は GUI を含まないクレートにして、`cargo test` を速く保つ。
- この分け方なら、フロントエンドを後から替える・増やす（例: macOS は SwiftUI、Linux は GPUI）ことができる。

## フロントエンドの候補

確度: 各候補の性質は一般に知られた特徴。メモリ量の目安は file-classifier の実測（GPUI）以外は**未計測の推測**なので、迷ったら S0 で計測して決める。

| 候補 | 向く用途 | 長所 | 短所・注意 |
|---|---|---|---|
| **SwiftUI / AppKit ＋ Rust コア**（UniFFI 等で接続） | macOS / iOS 専用で、標準アプリと同じ見た目・操作感を最優先するアプリ | 標準の部品をそのまま使うので、最新の macOS の外観（素材・半透明・アニメーション）、メニュー、日本語入力、アクセシビリティ、ダークモードが自動で揃う | Swift と Rust の2言語。FFI（Foreign Function Interface、言語間の呼び出し）の境界の設計とビルドの手間（Xcode / swift build と cargo の連携） |
| **GPUI**（Zed 製、Rust） | 大量の行を扱う高密度な UI（ファイル一覧、エディタ）、Rust だけで完結させたいアプリ、将来のマルチプラットフォーム | 1言語で完結。GPU 描画で速い。空のウィンドウで約 57 MB（file-classifier の実測） | 部品を全て自前で描くため、標準の見た目は真似して作る必要がある（透明タイトルバーの誤ズーム、IME の不具合などの実例あり）。ドキュメントが少なくソースを読む場面が多い。API の破壊的変更が起きやすい |
| **Tauri**（Rust ＋ Web 技術の UI） | クロスプラットフォームで、UI を Web 技術で素早く作りたいもの | Electron よりバイナリが小さい。OS の WebView を使う | WebView のプロセスの分だけメモリを使う。見た目は Web 風になりやすく、標準アプリへの寄せは CSS で頑張る必要がある |
| **egui / iced / Slint** など | 道具的な画面、設定画面中心のツール | Rust だけで手軽 | 標準の見た目から離れる。参照アプリに合わせる用途には不向き |
| **TUI**（ratatui） | 端末で使うツール | 非常に軽い | 端末の中だけ |
| **CLI のみ**（clap） | 画面が要らない処理 | 最小 | ― |

## 選び方

1. **参照アプリがあり、macOS だけで使う** → SwiftUI / AppKit ＋ Rust コアを第一候補にする。見た目を真似る手間が無くなり、OS の更新で外観が変わっても追従できる。
2. **数万行の一覧を滑らかに動かす、または Rust だけで完結させたい、将来 Windows / Linux でも使う** → GPUI を第一候補にする。標準アプリへの寄せは `macos-look-and-feel.md` のチェック項目で潰していく。
3. **Web 技術の資産がある、複数 OS で同じ見た目でよい** → Tauri。
4. **端末で十分** → TUI か CLI。
5. 迷ったら、S0 で候補ごとに「空のウィンドウ（または最小の一覧画面）」を作り、メモリ（phys_footprint）・初回描画の時間・無操作時の CPU・バイナリサイズを計測して PLAN §11 に並べてから決める。

選んだ案・選ばなかった案・理由は PLAN §1.3 に表で残す。

## Rust のワークスペースの決まりごと

テンプレート `templates/Cargo.toml` に入れてある。

- `edition = "2024"`、`rust-version` を明記する。
- `[workspace.lints.rust] unsafe_code = "deny"`、`[workspace.lints.clippy] unwrap_used = "warn"`。各クレートは `[lints] workspace = true`。OS の API を呼ぶクレートだけ、モジュール単位で `#![allow(unsafe_code)]` とし、理由をコメントに書く。
- `[profile.release] lto = "thin"`、`codegen-units = 1`（サイズと速度のため）。
- 設定・記録は `~/.config/<project>/` に置く（走査の対象からは自動で外す）。
- 依存を足すときは、足す理由とバイナリサイズ・メモリへの影響を確かめる。重いもの（全文検索エンジン、データベース）は §9 で利用者と合意してから。

## macOS アプリにする

- `templates/scripts/bundle.sh` で `.app` を作り、`--install` で `/Applications` に入れる（`[[Rust製GUIアプリのアプリバンドル化]]`）。アイコンは `templates/scripts/make_icon.swift` で SF Symbols を使って描く。
- 署名はアドホック（この Mac で使うため）。ほかの Mac に配るには Developer ID での署名と公証が要る。
- Finder から起動したアプリは PATH が最小なので、外部コマンドは `/opt/homebrew/bin` 等も探す。
