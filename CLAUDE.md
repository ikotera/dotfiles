# 出力整形規約（Claude Code デスクトップ版 Code タブ。2026-11-12 実測）

前提: skins mod の数式と図表の描き直しは無効にしておく（`/skin math off`、`/skin charts off`）。有効だと、数式は「MATH」見出し付きの文字の積み上げに、mermaid は文字で組んだ絵に描き直されて崩れる。

- インライン数式は `$...$` を使う。区切りの内側は **60文字以内**にする（61文字以上は生テキストのまま表示される。anthropics/claude-code issue 102139）。長い式は独立式にする。
- `\(...\)` も描画されるが、`$...$` に統一する（リスト項目内でバックスラッシュが落ちる報告がある）。
- 独立数式は `$$...$$` を**単独行**に置く。`math` 言語指定のコードフェンスも可。
- `\[...\]` は使わない（バックスラッシュが落ちて `[ \frac{a}{b} ]` のような生テキストになる）。
- `\tag{}` は未検証。番号が要るなら式の外に「(1)」とテキストで書く。
- 独立式の中の `\{` `\}` `\\`（cases・行列）は崩れる報告がある（issue 92152）。`\lbrace` `\rbrace` を使うか、箇条書きに書き換える。
- 図は ```mermaid フェンスで描いてよい（flowchart・pie・sequenceDiagram が図になることを実測。詳細は `instructions/shared-instructions.md` の図解規約）。

例:

(1)

$$
V_{\mathrm{load}} = V_{\mathrm{oc}} - I R_{\mathrm{int}}
$$

ここで、

- $V_{\mathrm{load}}$：負荷時の端子電圧（単位 V）
- $V_{\mathrm{oc}}$：開放電圧（単位 V）
- $I$：負荷電流（単位 A）
- $R_{\mathrm{int}}$：バッテリー内部抵抗（単位 Ω）

@instructions/shared-instructions.md
