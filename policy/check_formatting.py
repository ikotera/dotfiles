#!/usr/bin/env python3
"""
check_formatting.py — 出力整形チェッカ「本体」（ベンダ非依存）

役割:
  標準入力で「チェック対象テキスト」（＝AIアシスタントが書いた地の文）を受け取り、
  出力整形規約への違反を標準出力に1件ずつ書き出す。
    - 終了コード 0: 違反なし
    - 終了コード 1: 違反あり（詳細は stdout）

このスクリプトは Claude Code / Codex / Gemini のどれにも依存しない。
各ハーネス固有の入出力（フック JSON の形・差し戻し方法）はアダプタ側が担当し、
本体は「テキストを受け取り、違反を返す」ことだけに責任を持つ。
→ 3社で共有するのはこのファイル。各社で書くのは薄いアダプタだけ。

検査ルール（Claude Code の描画規約に対応 / shared-instructions.md と整合）:
  1. ```mermaid フェンス … この環境では図にならず生コード化するため禁止（SVGに置換）
  2. インライン数式 $...$ … 文中の単一ドル数式は描画されないため禁止
                            （$$...$$ の独立ブロックはOK。なので除外する）

チューニング:
  環境変数 FORMAT_CHECK_STRICT=1 を立てると、LaTeX らしさに関係なく
  すべての $...$ を違反として扱う（通貨記号などの誤検出を許容してでも厳格にしたい場合）。
"""
import os
import re
import sys

# 行頭（インデント可）の ```mermaid フェンス
MERMAID_FENCE = re.compile(r"^[ \t]*```[ \t]*mermaid\b", re.MULTILINE | re.IGNORECASE)
# フェンス行（``` または ~~~）。コードブロックの開閉判定に使う
FENCE_LINE = re.compile(r"^[ \t]*(```|~~~)")
# インラインコードスパン `...`
INLINE_CODE = re.compile(r"`[^`\n]*`")
# 独立ブロック数式 $$...$$（複数行可）。これは許可なので除去してから検査する
DISPLAY_MATH = re.compile(r"\$\$.*?\$\$", re.DOTALL)
# 文中の単一ドル数式 $...$（$$ は除外）
INLINE_MATH = re.compile(r"(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)")
# LaTeX らしさのシグナル（バックスラッシュ命令・上付き・下付き・波括弧）
LATEX_SIGNAL = re.compile(r"[\\^_{}]")

STRICT = os.environ.get("FORMAT_CHECK_STRICT") == "1"


def remove_fenced_blocks(text: str) -> str:
    """フェンス付きコードブロックの中身を取り除く。
    コード内の $ や ``` を数式・mermaid と誤検出しないため。"""
    out, in_fence = [], False
    for line in text.splitlines():
        if FENCE_LINE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return "\n".join(out)


def check(text: str):
    violations = []

    # 1) mermaid フェンス（元テキストのまま、行番号付きで報告）
    for m in MERMAID_FENCE.finditer(text):
        line_no = text.count("\n", 0, m.start()) + 1
        violations.append(
            f"[mermaid] {line_no}行目付近: ```mermaid は Claude Code では図にならず"
            "生コード化します。SVG（show_widget）に置き換えてください。"
        )

    # 2) インライン数式（コード・独立ブロックを除いた残りを検査）
    stripped = remove_fenced_blocks(text)
    stripped = INLINE_CODE.sub(" ", stripped)
    stripped = DISPLAY_MATH.sub(" ", stripped)
    for m in INLINE_MATH.finditer(stripped):
        content = m.group(1)
        if STRICT or LATEX_SIGNAL.search(content):
            snippet = m.group(0)
            if len(snippet) > 60:
                snippet = snippet[:57] + "..."
            violations.append(
                f"[inline-math] 文中の単一 $...$ は描画されません: {snippet}  "
                "→ $$...$$ を単独行に置くか、文章へ言い換えてください。"
            )

    return violations


def main():
    text = sys.stdin.read()
    violations = check(text)
    for v in violations:
        print(v)
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
