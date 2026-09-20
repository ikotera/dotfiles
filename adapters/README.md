# 出力整形フック（本体＋アダプタ）

3社（Claude Code / Codex / Gemini CLI）で出力整形ルールを共有するための構成。

```text
.agents/
  policy/
    check_formatting.py     # 本体（ベンダ非依存）: テキストを受け取り違反を返す。3社で共有。
  adapters/
    claude/
      stop_hook.py          # Claude Code 用アダプタ: Stop フックの JSON を本体に橋渡し。
    codex/                  # （将来）Codex 用。config.toml の [hooks.Stop] から呼ぶ。
    gemini/                 # （将来）Gemini 用。settings.json の stop/turn 系から呼ぶ。
```

## 役割分担

- **本体** `policy/check_formatting.py`
  - 標準入力でテキストを受け取り、違反を1件ずつ標準出力へ。
  - 終了コード `0`=違反なし / `1`=違反あり。
  - どのハーネスにも依存しない。**共有するのはこのファイル。**
- **アダプタ** `adapters/<harness>/...`
  - 各社のフック JSON を読み、検査対象テキストを取り出して本体に渡し、
    結果を各社の差し戻し方法（exit code / JSON）に変換する。
  - **薄く保つ。** ロジックは本体に置く。

## 検査ルール

1. ` ```mermaid ` フェンス → Claude Code では図にならないため禁止（SVGに置換）。
2. 文中の単一 `$...$` 数式 → 描画されないため禁止（`$$...$$` の独立行はOK）。

環境変数 `FORMAT_CHECK_STRICT=1` で、LaTeX らしさに関係なく全 `$...$` を違反扱い。

## Claude Code への登録

`~/.claude/settings.json`（ユーザ全体）または各プロジェクトの
`.claude/settings.json` に以下を追記する。

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [
          { "type": "command",
            "command": "python3 \"$HOME/Github/dotfiles/adapters/claude/stop_hook.py\"" }
      ] }
    ]
  }
}
```

## 動作確認（本体の単体テスト）

```bash
# 違反あり → 終了コード1、違反内容を出力
printf 'これは $E=mc^2$ です。\n```mermaid\ngraph LR\n```\n' \
  | python3 ~/Github/dotfiles/policy/check_formatting.py; echo "exit=$?"

# 違反なし → 終了コード0、無出力
printf 'これは独立式です。\n$$\nE=mc^2\n$$\n' \
  | python3 ~/Github/dotfiles/policy/check_formatting.py; echo "exit=$?"
```
