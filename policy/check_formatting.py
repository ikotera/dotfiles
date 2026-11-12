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

検査ルール（Claude Code デスクトップ版 Code タブの描画に対応 / CLAUDE.md と整合。2026-11-12 実測）:
  1. インライン数式 $...$ … 区切りの内側が61文字以上だと描画されないため禁止
                            （60文字以内はOK。$$...$$ の独立ブロックは除外する）
  2. \[...\] の独立数式 … バックスラッシュが落ちて生テキスト化するため禁止（$$...$$ に置換）

チューニング:
  環境変数 FORMAT_CHECK_STRICT=1 を立てると、LaTeX らしさに関係なく
  61文字以上の $...$ を違反として扱う（通貨記号などの誤検出を許容してでも厳格にしたい場合）。
"""
import os
import re
import sys

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
# Code タブがインライン数式として描画する、区切りの内側の最大文字数
INLINE_MAX = 60
# \[ ... \] の独立数式の開始（行頭、インデント可）
BRACKET_DISPLAY = re.compile(r"^[ \t]*\\\[", re.MULTILINE)

STRICT = os.environ.get("FORMAT_CHECK_STRICT") == "1"


def remove_fenced_blocks(text: str) -> str:
    """フェンス付きコードブロックの中身を取り除く。
    コード内の $ や \[ を数式と誤検出しないため。"""
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

    # 1) インライン数式（コード・独立ブロックを除いた残りを検査）
    stripped = remove_fenced_blocks(text)
    stripped = INLINE_CODE.sub(" ", stripped)
    stripped = DISPLAY_MATH.sub(" ", stripped)
    for m in INLINE_MATH.finditer(stripped):
        content = m.group(1)
        if len(content) <= INLINE_MAX:
            continue
        if STRICT or LATEX_SIGNAL.search(content):
            snippet = m.group(0)[:57] + "..."
            violations.append(
                f"[inline-math] 文中の $...$ が{len(content)}文字あり、{INLINE_MAX}文字を超えると描画されません: "
                f"{snippet}  → $$...$$ を単独行に置くか、式を短く分けてください。"
            )

    # 2) \[...\] の独立数式（コードを除いた残りを検査）
    for m in BRACKET_DISPLAY.finditer(stripped):
        line_no = stripped.count("\n", 0, m.start()) + 1
        violations.append(
            f"[bracket-math] {line_no}行目付近（コード除外後）: \\[...\\] は Claude Code で"
            "描画されません。$$...$$ を単独行に置いてください。"
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
