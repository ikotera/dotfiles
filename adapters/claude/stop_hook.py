#!/usr/bin/env python3
"""
stop_hook.py — Claude Code 用 Stop フック「アダプタ」

役割:
  Claude Code の Stop フックから標準入力で渡される JSON を受け取り、
  トランスクリプトから「直近のアシスタント発言（地の文）」を取り出して、
  ベンダ非依存の本体 policy/check_formatting.py に渡す。
  違反があれば Claude Code に差し戻して、書き直しを促す。

  ＝ ここが「各社で別々に書く薄いアダプタ」。本体のロジックは一切持たない。
     Codex 版・Gemini 版は、同じ本体を呼びつつ、各社の JSON 形と
     差し戻し方法（exit code / JSON）の違いだけをここで吸収する。

settings.json への登録（~/.claude/settings.json などに追記）:
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

差し戻しの仕様:
  Stop フックで {"decision": "block", "reason": "..."} を stdout に出すと、
  Claude Code は「停止」を取り消し、reason を指示として受け取って続行する。
  違反がなければ何も出さず exit 0（そのまま停止させる）。
"""
import json
import os
import re
import subprocess
import sys
import tempfile

# 本体スクリプトの場所（このファイルから見た相対位置を解決）
BODY = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "policy", "check_formatting.py",
    )
)

# --- 無限ループ回避 -------------------------------------------------------
# 差し戻すたびにモデルは書き直すが、直し切れないと Stop→block→Stop... と
# 無限ループになりうる。そこで session_id ごとに差し戻し回数を一時ファイルで
# 数え、上限を超えたらフェイルオープン（通す）。適合できたらカウンタを消す。
MAX_RETRIES = int(os.environ.get("FORMAT_HOOK_MAX_RETRIES", "3"))
STATE_DIR = os.path.join(tempfile.gettempdir(), "claude_format_hook")


def _state_file(session_id: str):
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", session_id or "")
    return os.path.join(STATE_DIR, f"{safe}.count") if safe else None


def _read_count(path: str) -> int:
    try:
        with open(path) as f:
            return int(f.read().strip() or "0")
    except (OSError, ValueError):
        return 0


def _write_count(path: str, n: int) -> None:
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(path, "w") as f:
            f.write(str(n))
    except OSError:
        pass


def _clear(path) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def last_assistant_text(transcript_path: str) -> str:
    """トランスクリプト（JSONL）から直近のアシスタント発言のテキストを連結して返す。"""
    try:
        with open(transcript_path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return ""

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "assistant":
            continue
        content = obj.get("message", {}).get("content", [])
        if isinstance(content, str):
            return content
        parts = [
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        if parts:
            return "\n".join(parts)
    return ""


def main():
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)  # 解釈できない入力では何もしない（フェイルオープン）

    state = _state_file(event.get("session_id", ""))

    text = last_assistant_text(event.get("transcript_path", ""))
    if not text.strip():
        sys.exit(0)

    try:
        proc = subprocess.run(
            [sys.executable, BODY],
            input=text,
            capture_output=True,
            text=True,
        )
    except OSError:
        sys.exit(0)  # 本体が起動できない場合もフェイルオープン

    if proc.returncode == 0:
        _clear(state)  # 適合できた → カウンタをリセットして停止させる
        sys.exit(0)

    # --- 違反あり: 無限ループ回避つきで差し戻す ---
    if state is not None:
        count = _read_count(state) + 1
        if count > MAX_RETRIES:
            # 上限到達 → これ以上は止めずに通す（暴走回避）。カウンタは消す。
            _clear(state)
            sys.exit(0)
        _write_count(state, count)
        suffix = f"\n（修正リトライ {count}/{MAX_RETRIES}。これ以降は自動で通します）"
    else:
        # session_id が取れない場合のフォールバック: 継続中なら一度きりで諦める
        if event.get("stop_hook_active"):
            sys.exit(0)
        suffix = ""

    reason = (
        "出力整形の規約違反が見つかりました。次を直して出し直してください:\n"
        + proc.stdout.strip()
        + suffix
    )
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
