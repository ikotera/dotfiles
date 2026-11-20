"""dotfiles-bridge — dotfiles を Hermes に橋渡しする薄いアダプタ（Hermes プラグイン）。

役割:
  1. 共通規約の注入
     instructions/shared-instructions.md（全エージェント共通の正本）と
     instructions/hermes-instructions.md（Hermes 固有の差分）を、新しいセッションが
     作られるたびにファイルから読み、システムプロンプトの節として注入する。
     Claude Code / Codex の `@import` に相当する。中身のコピーは持たないので、
     正本を編集すれば次のセッションから反映される（既存セッションは凍結されたまま）。
  2. RTK の自動適用
     terminal ツールのコマンドを `rtk rewrite` に通し、RTK 版があれば書き換える。
     Claude Code の PreToolUse フック `rtk hook claude` に相当する。

Hermes の制約（2026-11 時点のソースで確認）:
  - プラグインの節は 1 節 4,000 字、全節の合計 8,000 字（見出し込み）まで。
    超える分は省き、read_file で正本を読むよう案内を付ける。
  - pre_tool_call のコールバックは時間切れになると「ブロック」扱いになるため、
    rtk の呼び出しは短いタイムアウトで包み、失敗したら何もしない（フェイルオープン）。

環境変数:
  DOTFILES_DIR             dotfiles の場所（既定: このファイルの位置から解決）
  DOTFILES_HERMES_RTK=0    RTK の自動書き換えを止める
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

def _find_dotfiles() -> Path:
    """dotfiles ルートを探す。Hermes がプラグインを一時ディレクトリへ写して読み込む場合が
    あるため、このファイルの位置（adapters/hermes/plugin → 3階層上）だけには頼らない。"""
    here = Path(__file__).resolve()
    candidates = [os.environ.get("DOTFILES_DIR"), here.parents[3] if len(here.parents) > 3 else None,
                  "~/.agents", "~/Github/dotfiles", "~/dotfiles"]
    for c in candidates:
        if c and (Path(c).expanduser() / "instructions" / "shared-instructions.md").is_file():
            return Path(c).expanduser().resolve()
    return Path("~/Github/dotfiles").expanduser()


_DOTFILES = _find_dotfiles()
SHARED = _DOTFILES / "instructions" / "shared-instructions.md"
HERMES = _DOTFILES / "instructions" / "hermes-instructions.md"

SECTION_MAX = 4000      # Hermes の 1 節あたり上限
TOTAL_BUDGET = 7400     # 合計 8,000 字から見出し等の余白を引いた、本文の目安
CHUNK_TARGET = 3800     # 1 節に詰める本文の目安


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as e:
        logger.warning("dotfiles-bridge: %s を読めません: %s", path, e)
        return ""


def _split_top_level(text: str) -> list[str]:
    """`# ` 見出し（フェンス外）ごとに分ける。区切り線 `---` は捨てる。"""
    blocks, cur, fenced = [], [], False
    for line in text.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
        if not fenced and line.startswith("# ") and cur:
            blocks.append("\n".join(cur).strip())
            cur = []
        if not fenced and line.strip() == "---":
            continue
        cur.append(line)
    if cur:
        blocks.append("\n".join(cur).strip())
    return [b for b in blocks if b]


def _pack(blocks: list[str], budget: int) -> tuple[list[str], bool]:
    """ブロックを CHUNK_TARGET ごとの節に詰める。budget を超えたら打ち切り、省略の有無を返す。"""
    chunks, cur, used = [], "", 0
    for b in blocks:
        if len(b) > CHUNK_TARGET:          # 1 ブロックが大きすぎる場合は切り詰める
            b = b[:CHUNK_TARGET - 40] + "\n…（以下省略）"
        if used + len(b) > budget:
            if cur:
                chunks.append(cur)
            return chunks, True
        if cur and len(cur) + 2 + len(b) > CHUNK_TARGET:
            chunks.append(cur)
            cur = b
        else:
            cur = f"{cur}\n\n{b}" if cur else b
        used += len(b) + 2
    if cur:
        chunks.append(cur)
    return chunks, False


def _render() -> list[str]:
    """[hermes 差分, 共通規約 1, 共通規約 2, ...] の順で節の本文を返す。"""
    hermes = _read(HERMES)[:SECTION_MAX - 200]
    pointer = (f"\n\n（共通規約の一部を省略。全文は read_file で {SHARED} を読む）")
    chunks, truncated = _pack(_split_top_level(_read(SHARED)),
                              TOTAL_BUDGET - len(hermes) - len(pointer))
    if truncated and chunks:
        chunks[-1] += pointer
    head = (f"出典: {SHARED}（Claude Code・Codex・Gemini と共有する正本）。"
            "Hermes 固有の差分は別節「dotfiles.hermes」を優先する。\n\n")
    if chunks:
        chunks[0] = head + chunks[0]
    return [hermes] + chunks


# 登録時点の節の数で枠を確保する（ファイルが増えて枠が足りなくなったら省略＋案内になる）
def _slot(i: int):
    def render(_session_info) -> str:
        parts = _render()
        return parts[i] if i < len(parts) else ""
    return render


_TERMINAL_TOOLS = {"terminal"}
_RTK = shutil.which("rtk") or next(
    (p for p in (os.path.expanduser("~/.local/bin/rtk"), "/opt/homebrew/bin/rtk")
     if os.access(p, os.X_OK)), None)


def _rtk_rewrite(tool_name=None, args=None, **_kwargs):
    if tool_name not in _TERMINAL_TOOLS or not _RTK or os.environ.get("DOTFILES_HERMES_RTK") == "0":
        return None
    if not isinstance(args, dict):
        return None
    cmd = args.get("command")
    if not isinstance(cmd, str) or not cmd.strip() or cmd.lstrip().startswith("rtk "):
        return None
    try:
        # rtk rewrite: 0=書き換え（自動許可）、3=書き換え（要確認）、1=対応なし
        proc = subprocess.run([_RTK, "rewrite", cmd], capture_output=True, text=True, timeout=3)
    except Exception as e:  # noqa: BLE001 — フェイルオープン
        logger.debug("dotfiles-bridge: rtk rewrite failed: %s", e)
        return None
    new = proc.stdout.strip()
    if proc.returncode in (0, 3) and new and new != cmd.strip():
        return {"action": "modify", "args": {"command": new}}
    return None


def register(ctx):
    n = len(_render())
    ctx.register_system_prompt_section("dotfiles.hermes", _slot(0), max_chars=SECTION_MAX)
    for i in range(1, n):
        ctx.register_system_prompt_section(f"dotfiles.shared-{i}", _slot(i), max_chars=SECTION_MAX)
    ctx.register_hook("pre_tool_call", _rtk_rewrite)
