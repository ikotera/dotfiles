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
  3. 共有スキルの保護（提案してから反映）
     Hermes の自動スキル改善（background review）や skill_manage が、dotfiles の
     スキル（skills/・adapters/hermes/skills/）を書き換えようとしたら止め、変更内容を
     $HERMES_HOME/skill-proposals/ に提案として保存する。dotfiles は自動同期で公開
     リポジトリへ push され、Claude Code・Codex も読むため、採否はユーザーが決める。
     Hermes 自身のスキル（~/.hermes/skills/）・メモリー・curator には干渉しない。
     採用は write_file / patch で dotfiles のファイルを直接編集する（その際は承認を求める）。
  4. 提案の通知
     未処理の提案が増えたら、次のユーザー発言に「返答の最後で一行だけ確認を勧める」
     指示を添える（pre_llm_call。システムプロンプトは変えないのでキャッシュを崩さない）。
     同じ提案を知らせるのは 1 セッションにつき 1 回。新しい提案が増えたときだけ再び知らせる。

Hermes の制約（2026-11 時点のソースで確認）:
  - プラグインの節は 1 節 4,000 字、全節の合計 8,000 字（見出し込み）まで。
    超える分は省き、read_file で正本を読むよう案内を付ける。
  - pre_tool_call のコールバックは時間切れになると「ブロック」扱いになるため、
    rtk の呼び出しは短いタイムアウトで包み、失敗したら何もしない（フェイルオープン）。

環境変数:
  DOTFILES_DIR             dotfiles の場所（既定: このファイルの位置から解決）
  DOTFILES_HERMES_RTK=0    RTK の自動書き換えを止める
  DOTFILES_HERMES_GUARD=0  共有スキルの保護を止める
  DOTFILES_HERMES_NOTIFY=0 提案の通知を止める
"""
from __future__ import annotations

import datetime as _dt
import json
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


# ---------------------------------------------------------------------------
# 3. 共有スキルの保護
# ---------------------------------------------------------------------------
def _hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home())
    except Exception:  # noqa: BLE001
        return Path(os.environ.get("HERMES_HOME") or "~/.hermes").expanduser()


def _shared_skill_roots() -> list[Path]:
    return [p.resolve() for p in (_DOTFILES / "skills", _DOTFILES / "adapters" / "hermes" / "skills",
                                  _DOTFILES / "shared-references") if p.is_dir()]


def _shared_skill_dir(name: object):
    """name が dotfiles のスキルを指すなら、その実体のディレクトリを返す。
    Hermes はローカル（~/.hermes/skills）を外部より優先するので、同名のローカルスキルがあれば None。"""
    if not isinstance(name, str) or not name.strip():
        return None
    base = name.strip().rstrip("/").split("/")[-1]
    local = _hermes_home() / "skills"
    if local.is_dir() and any(local.glob(f"**/{base}/SKILL.md")):
        return None
    for root in _shared_skill_roots():
        cand = root / base
        if (cand / "SKILL.md").is_file():
            return cand
    return None


def _under_shared(path_str) -> bool:
    if not isinstance(path_str, str) or not path_str:
        return False
    try:
        p = Path(path_str).expanduser()
        p = p.resolve() if p.exists() else p.parent.resolve() / p.name
    except OSError:
        return False
    return any(p == r or r in p.parents for r in _shared_skill_roots())


def _save_proposal(ops: list, session_id, task_id) -> Path:
    d = _hermes_home() / "skill-proposals"
    d.mkdir(parents=True, exist_ok=True)
    now = _dt.datetime.now().astimezone()
    names = "-".join(sorted({re.sub(r"[^A-Za-z0-9._-]", "_", str(o.get("name"))) for o in ops}))[:80]
    path = d / f"{now:%Y%m%d-%H%M%S}-{names}.md"
    n = 2
    while path.exists():  # 同じ秒に同じスキルへの提案が重なった場合
        path = d / f"{now:%Y%m%d-%H%M%S}-{names}-{n}.md"
        n += 1
    lines = [f"# スキル変更の提案: {', '.join(sorted({str(o.get('name')) for o in ops}))}", "",
             f"- 日時: {now.isoformat(timespec='seconds')}",
             f"- セッション: {session_id or '-'}（task: {task_id or '-'}）",
             f"- 対象: dotfiles の共有スキル（{_DOTFILES}）",
             "- 状態: 未処理", "",
             "Hermes が skill_manage で書き換えようとした内容。dotfiles-bridge が止めて保存した。", ""]
    for i, op in enumerate(ops, 1):
        lines += [f"## 操作 {i}: {op.get('action')} {op.get('name')}"
                  + (f" ({op.get('file_path')})" if op.get("file_path") else ""), ""]
        for key in ("old_string", "new_string", "content", "file_content"):
            if isinstance(op.get(key), str):
                lines += [f"### {key}", "", "``````text", op[key], "``````", ""]
        rest = {k: v for k, v in op.items()
                if k not in ("old_string", "new_string", "content", "file_content")}
        lines += ["### その他の引数", "", "```json", json.dumps(rest, ensure_ascii=False, indent=1), "```", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _guard_shared_skills(tool_name=None, args=None, session_id=None, task_id=None, **_kwargs):
    if os.environ.get("DOTFILES_HERMES_GUARD") == "0" or not isinstance(args, dict):
        return None
    if tool_name == "skill_manage":
        ops = args.get("operations")
        if not isinstance(ops, list):
            ops = [args]  # 旧形式（1操作を直接渡す）
        ops = [o for o in ops if isinstance(o, dict)]
        hits = [o for o in ops if _shared_skill_dir(o.get("name")) is not None]
        if not hits:
            return None
        try:
            saved = _save_proposal(hits, session_id, task_id)
        except OSError as e:
            saved = f"（保存に失敗: {e}）"
        others = len(ops) - len(hits)
        msg = (f"dotfiles の共有スキル（{', '.join(sorted({str(o.get('name')) for o in hits}))}）は "
               "Claude Code・Codex と共有し、自動同期で公開リポジトリへ push されるため、Hermes からは"
               f"直接書き換えない。変更内容は提案として {saved} に保存した。採否はユーザーが決める。"
               "ユーザーとの会話中なら、提案を保存したことを一言伝える。")
        if others:
            msg += f" 同じ呼び出しに含まれていた他の {others} 件の操作も実行していないので、必要ならそれだけを再実行する。"
        return {"action": "block", "message": msg}
    if tool_name in ("write_file", "patch"):
        paths = [args.get("path")]
        if isinstance(args.get("patch"), str):  # V4A 形式の複数ファイル
            paths += re.findall(r"^\*\*\* (?:Update|Add|Delete) File: (.+)$", args["patch"], re.M)
        if any(_under_shared(p) for p in paths):
            return {"action": "approve", "rule_key": "dotfiles:shared-skill-edit",
                    "message": "dotfiles の共有スキル（Claude Code・Codex と共有、公開リポジトリ）を編集します。"}
    return None


# ---------------------------------------------------------------------------
# 4. 提案の通知
# ---------------------------------------------------------------------------
_announced: dict[str, set[str]] = {}   # session_id -> 知らせ済みの提案ファイル名
_ANNOUNCED_MAX = 500                    # 常駐プロセスで増え続けないように


def _pending_proposals() -> list[Path]:
    d = _hermes_home() / "skill-proposals"
    try:
        return sorted(p for p in d.glob("*.md") if p.is_file())
    except OSError:
        return []


def _proposal_skill(p: Path) -> str:
    # 20261120-140647-obsidian-moc.md / 同秒の重複は末尾 -2 など
    m = re.match(r"^\d{8}-\d{6}-(.+?)(?:-\d+)?\.md$", p.name)
    return m.group(1) if m else p.stem


def _notify_proposals(session_id=None, platform=None, **_kwargs):
    if os.environ.get("DOTFILES_HERMES_NOTIFY") == "0" or platform == "cron":
        return None
    pending = _pending_proposals()
    if not pending:
        return None
    key = str(session_id or "-")
    seen = _announced.setdefault(key, set())
    new = [p for p in pending if p.name not in seen]
    if not new:
        return None
    if len(_announced) > _ANNOUNCED_MAX:
        _announced.clear()
        _announced[key] = seen
    seen.update(p.name for p in pending)
    skills = sorted({_proposal_skill(p) for p in pending})
    oldest = pending[0].name[:8]
    return {"context": (
        "[dotfiles-bridge] dotfiles の共有スキルへの変更提案が未処理で "
        f"{len(pending)} 件ある（対象: {', '.join(skills)}。最も古いもの: {oldest[:4]}-{oldest[4:6]}-{oldest[6:]}。"
        f"保存先: {_hermes_home() / 'skill-proposals'}）。"
        "これはユーザーの発言ではなく自動の通知。今回の依頼にまず答え、返答の最後に一行だけ"
        "「共有スキルの変更提案が N 件あります。確認しますか？」の形で確認を勧める。"
        "依頼の内容が急ぎ・別件の作業の途中なら、それを妨げない短さにする。"
        "ユーザーが了承したらスキル dotfiles-skill-proposals の手順で処理する。"
        "この通知に触れるのは今回の返答だけでよい。"
    )}


def register(ctx):
    n = len(_render())
    ctx.register_system_prompt_section("dotfiles.hermes", _slot(0), max_chars=SECTION_MAX)
    for i in range(1, n):
        ctx.register_system_prompt_section(f"dotfiles.shared-{i}", _slot(i), max_chars=SECTION_MAX)
    ctx.register_hook("pre_tool_call", _rtk_rewrite)
    ctx.register_hook("pre_tool_call", _guard_shared_skills)
    ctx.register_hook("pre_llm_call", _notify_proposals)
