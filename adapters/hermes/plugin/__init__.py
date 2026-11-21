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
     リポジトリへ push され、Claude Code・Codex も読むため、採否は両者への影響を見て判断する。
     Hermes 自身のスキル（~/.hermes/skills/）・メモリー・curator には干渉しない。
     反映は write_file / patch で行う（編集時の承認は提案の採否とは別）。
  4. 提案の通知
     未処理の提案が増えたら、今回の依頼に答えた後（急ぎ・別件の作業中なら区切りのよいとき）に
     dotfiles-skill-proposals の手順で処理し、判断に迷う提案だけユーザーに尋ねるよう指示を添える。
     pre_llm_call を使い、システムプロンプトは変えないのでキャッシュを崩さない。
     同じ提案を知らせるのは 1 セッションにつき 1 回。新しい提案が増えたときだけ再び知らせる。
  5. 残量の表示と委任先の自動切替
     親セッションの活動中は3分ごとに Claude / OpenAI の5時間枠・週枠を観測し、
     使用率・消費速度・リセットまでの予測から、新しい委任だけを設定済みのルートに振り替える。
     Desktop のステータスバーに使用率を表示し、指揮役には状態が変わったとき・逼迫中に通知する。
     取得はバックグラウンドで行い、フックと画面は残量の取得を待たない。
  6. 専用 Edge の自動起動・自動終了
     Hermes がブラウザのツールを使う直前に、専用 Edge（scripts/hermes-edge.sh、
     ~/.hermes/edge-profile、ポート 9222）が起動していなければ、前面に出さずに起動して待つ。
     このプラグインが起動した Edge は、ブラウザを使わない時間が一定（既定 10 分）続くと終了する。
     手で起動した Edge は終了しない。Hermes 自身に起動させない（--use-mock-keychain が付き、ログイン Cookie が消える）。

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
  DOTFILES_HERMES_QUOTA_INTERVAL_SEC  残量の取得間隔（秒、既定 180）
  DOTFILES_HERMES_QUOTA_ACTIVE_MIN    最後の親セッションの活動から監視を続ける時間（分、既定 30）
  DOTFILES_HERMES_QUOTA_ROUTING=0     委任先の振替だけを止める（観測・表示は継続）
  DOTFILES_HERMES_EDGE=0   専用 Edge の自動起動・自動終了を止める
  DOTFILES_HERMES_EDGE_IDLE_MIN  自動終了までの分数（既定 10、0 で自動終了しない）
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import signal
import threading
import time
import urllib.request
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import quota

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
               f"直接書き換えない。変更内容は提案として {saved} に保存した。"
               "ユーザーとの会話中なら、dotfiles-skill-proposals の手順で処理する。")
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


def _notify_proposals(session_id=None, platform=None, parent_session_id=None, **_kwargs):
    # サブエージェント（親セッションを持つ）には出さない。出すと委任の回答に通知文が混ざる
    if os.environ.get("DOTFILES_HERMES_NOTIFY") == "0" or platform == "cron" or parent_session_id:
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
        "これはユーザーの発言ではなく自動の通知。今回の依頼に答えた後、"
        "スキル dotfiles-skill-proposals の手順で処理する。"
        "急ぎの依頼や別件の作業中なら、区切りのよいときに処理する。"
        "判断に迷う提案だけユーザーに尋ねる。"
    )}


# ---------------------------------------------------------------------------
# 5. 残量の観測と、新規委任先の振替（取得はフックの外で行う）
# ---------------------------------------------------------------------------
_quota_cond = threading.Condition()
_quota_thread = None
_quota_schedule = {}  # home → (最終活動時刻, 次に観測する時刻)。時計の補正に左右されない。
_quota_announced = {}
_QUOTA_NOTICE_SEC = 180
_QUOTA_HISTORY_SEC = 6 * 3600


def _quota_options():
    try:
        from hermes_cli.config import load_config_readonly
        cfg = load_config_readonly()['delegation']
        if cfg.get('backend') == 'model_map' and os.environ.get('DOTFILES_HERMES_QUOTA_ROUTING') != '0':
            return tuple(o['name'] for o in cfg['backends']['model_map']['options']
                         if isinstance(o, dict) and isinstance(o.get('name'), str))
    except (ImportError, KeyError, TypeError, ValueError):
        pass
    return ()


def _positive_int(key, default):
    try:
        value = int(os.environ.get('DOTFILES_HERMES_QUOTA_' + key, str(default)))
        return value if 0 < value < threading.TIMEOUT_MAX / 60 else default
    except ValueError:
        return default


def _atomic_text(path, text):
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as out:
        tmp = Path(out.name)
        try:
            out.write(text)
            out.close()
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)


def _quota_history(path, now):
    samples = []
    if path.exists():
        with path.open(encoding='utf-8') as src:
            for line in src:
                try:
                    s = json.loads(line)
                    if (0 <= now - s['ts'] <= _QUOTA_HISTORY_SEC and s['window'] in quota.WINDOWS[s['account']]
                            and quota.valid_used(s['used']) and quota.reset_ts(s['resets'])):
                        samples.append(s)
                except (ValueError, KeyError, TypeError):
                    continue
    return samples


def _refresh_quota_cache(home, interval):
    try:
        import fcntl
        cache = home / 'cache/quota-status-cache.json'
        cache.parent.mkdir(parents=True, exist_ok=True)
        with cache.with_suffix('.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if cache.exists() and 0 <= time.time() - cache.stat().st_mtime < max(0, interval - 10):
                return
            proc = subprocess.run(['python3', str(home / 'scripts/quota-status.py'), '--json'],
                                  env={**os.environ, 'HERMES_HOME': str(home)}, capture_output=True,
                                  text=True, timeout=130, check=True)
            now = time.time()
            rows = [r for r in json.loads(proc.stdout) if isinstance(r, dict) and 'error' not in r]
            history_path = cache.with_name('quota-history.jsonl')
            history = _quota_history(history_path, now)
            options = _quota_options()
            state = quota.build_state(rows, history, now, options)
            for account, info in state['accounts'].items():
                history.extend(dict(ts=now, account=account, window=w['window'], used=w['used'], resets=w['resets'])
                               for w in info['windows'])
            _atomic_text(history_path, ''.join(json.dumps(s) + '\n' for s in history))
            _atomic_text(cache.with_name('quota-routing-state.json'), json.dumps(state, ensure_ascii=False))
            _atomic_text(cache, json.dumps(rows))  # 更新完了の印。別プロセスはこの mtime を見る。
        from hermes_cli.plugin_events import broadcast_plugin_event
        broadcast_plugin_event('dotfiles-bridge', 'quota.updated',
                               {'updated_at': now, 'summary': state['summary']})
    except (BlockingIOError, ImportError):
        pass
    except Exception as e:  # 取得・通知の失敗は会話へ返さない。
        logger.debug('dotfiles-bridge: 残量の更新失敗: %s', type(e).__name__)


def _quota_poll():
    while True:
        interval = _positive_int('INTERVAL_SEC', 180)
        idle = _positive_int('ACTIVE_MIN', 30) * 60
        with _quota_cond:
            now = time.monotonic()
            for h, (last, _) in list(_quota_schedule.items()):
                if now - last >= idle:
                    del _quota_schedule[h]
            if not _quota_schedule:
                _quota_cond.wait()  # 次の活動まで取得も定期起床もしない。
                continue
            home = min(_quota_schedule, key=lambda h: _quota_schedule[h][1])
            last, due = _quota_schedule[home]
            if due > now:
                _quota_cond.wait(min(due - now, last + idle - now))
                continue
            _quota_schedule[home] = (last, now + interval)
        try:
            # フックと違い、このスレッドには呼出元のプロファイルが束縛されていない。
            if home == _hermes_home():
                _refresh_quota_cache(home, interval)
            else:
                from agent.runtime_scope import bind_profile_scope
                with bind_profile_scope(home, hydrate_secrets=False):
                    _refresh_quota_cache(home, interval)
        except Exception as e:
            logger.debug('dotfiles-bridge: 残量の監視失敗: %s', type(e).__name__)


def _touch_quota(home):
    global _quota_thread
    with _quota_cond:
        now = time.monotonic()
        fresh = home not in _quota_schedule
        due = 0 if fresh else _quota_schedule[home][1]
        _quota_schedule[home] = (now, due)
        if _quota_thread is None or not _quota_thread.is_alive():
            _quota_thread = threading.Thread(target=_quota_poll, name='dotfiles-quota', daemon=True)
            _quota_thread.start()
        elif fresh:
            _quota_cond.notify()


def _top_level(parent_session_id, platform, task_id):
    # pre_tool_call には親 ID と platform が渡らない。子の実行に割り当てる task_id でも除外する。
    if parent_session_id or platform == 'subagent' or re.fullmatch(r'(?:sa|subagent)-\d+-[0-9a-f]{8}', str(task_id)):
        return False
    try:
        from agent.delegation_context import is_delegated_child_context
        return not is_delegated_child_context()
    except ImportError:
        return True


def _read_quota_state(home, now):
    try:
        state = json.loads((home / 'cache/quota-routing-state.json').read_text(encoding='utf-8'))
        if 0 <= now - state['updated_at'] <= quota.STATE_TTL_SEC:
            # 次の測定前に枠が切れたら過去の使用率で振り替えない。
            live = {k: [w for w in a['windows'] if quota.reset_ts(w['resets']) > now]
                    for k, a in state['accounts'].items()}
            if any(len(live[k]) != len(a['windows']) for k, a in state['accounts'].items()):
                return quota.state_from_windows(live, state['updated_at'], state['mapping'])
            return state
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def _route_delegate(tool_name=None, args=None, session_id=None, task_id=None, parent_session_id=None,
                    platform=None, **_kwargs):
    try:
        if not _top_level(parent_session_id, platform, task_id):
            return None
        home = _hermes_home()
        _touch_quota(home)
        if (tool_name != 'delegate_task' or not isinstance(args, dict) or args.get('action', 'spawn') != 'spawn'
                or os.environ.get('DOTFILES_HERMES_QUOTA_ROUTING') == '0'):
            return None
        state = _read_quota_state(home, time.time())
        if not state or not any(k != v for k, v in state['mapping'].items()):
            return None
        tasks = args.get('tasks')
        if (tasks is None or tasks == []) and isinstance(args.get('goal'), str):
            tasks = [{k: args[k] for k in ('goal', 'context', 'images', 'output_schema', 'role', 'option') if k in args}]
        if not isinstance(tasks, list):
            return None
        options = _quota_options()  # 測定後にルートが削除された場合にも、無効な名前を書き込まない。
        changes, result = [], []
        for task in tasks:
            old = task.get('option') if isinstance(task, dict) else None
            if old is None:
                old = 'standard'
            new = state['mapping'].get(old)
            if isinstance(task, dict) and old in options and new in options and new != old:
                changes.append(f'{old}→{new}')
                task = {**task, 'option': new}
            result.append(task)
        if not changes:
            return None
        try:
            log = home / 'logs/quota-routing.log'
            log.parent.mkdir(parents=True, exist_ok=True)
            entry = dict(ts=_dt.datetime.now().astimezone().isoformat(), session=session_id,
                         changes=changes, levels={k: a['level'] for k, a in state['accounts'].items()})
            with log.open('a', encoding='utf-8') as out:
                out.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except OSError:
            pass
        return {'action': 'modify', 'args': {'tasks': result}}
    except Exception as e:
        logger.debug('dotfiles-bridge: 委任先を変更せず続行: %s', type(e).__name__)
        return None


def _notify_quota(session_id=None, parent_session_id=None, platform=None, task_id=None, **_kwargs):
    try:
        if not _top_level(parent_session_id, platform, task_id):
            return None
        home = _hermes_home()
        _touch_quota(home)
        now = time.time()
        state = _read_quota_state(home, now)
        if not state:
            return None
        accounts = state['accounts']
        mapping = {} if os.environ.get('DOTFILES_HERMES_QUOTA_ROUTING') == '0' else state['mapping']
        levels = tuple(accounts[k]['level'] for k in quota.WINDOWS)
        signature = levels, tuple(sorted(mapping.items()))
        key = (home, session_id)
        with _quota_cond:
            previous, last = _quota_announced.get(key, (None, 0))
            if previous == signature and (not {'critical', 'high'}.intersection(levels) or now-last < _QUOTA_NOTICE_SEC):
                return None
            if len(_quota_announced) >= _ANNOUNCED_MAX and key not in _quota_announced:
                del _quota_announced[next(iter(_quota_announced))]
            _quota_announced[key] = signature, now
        text = '[dotfiles-bridge・ユーザーの発言ではない自動通知] 残量: ' + quota.summarize(accounts, mapping)
        if any(w['window'] == 'Current session' and w['used'] >= 80 for w in accounts['claude']['windows']):
            text += ('。自分で行うのは会話・質問への回答と道具を1〜2回使う確認だけとし、要約・下書きも委任する。'
                     '95%を超えそうなら、ユーザーにメインモデルを OpenAI 側へ切り替えるか尋ねる。')
        if any(k != v for k, v in mapping.items()):
            text += ' delegate_task の option は自動で振り替えられる。'
        if state['both_critical']:
            resets = ' / '.join(f"{k} {w['window']}: {w['resets']}" for k, a in accounts.items() for w in a['windows'])
            text += f' リセット時刻（{resets}）を示し、後回しにするかユーザーに尋ねる。'
        return {'context': text}
    except Exception as e:
        logger.debug('dotfiles-bridge: 残量通知を見送り: %s', type(e).__name__)
        return None


# ---------------------------------------------------------------------------
# 6. 専用 Edge の自動起動・自動終了
# ---------------------------------------------------------------------------
_BROWSER_TOOLS = {"browser_exec", "browser_cdp", "browser_dialog", "browser_vault"}
_EDGE_PORT = int(os.environ.get("HERMES_EDGE_PORT") or 9222)
_edge_lock = threading.Lock()
_edge_state = {"pid": None, "last_use": 0.0, "watcher": False}


def _edge_up(timeout: float = 0.5) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{_EDGE_PORT}/json/version", timeout=timeout) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def _edge_pid():
    """専用データフォルダを使っている Edge 本体の pid（SingletonLock のリンク先 "<host>-<pid>"）。"""
    try:
        target = os.readlink(_hermes_home() / "edge-profile" / "SingletonLock")
        pid = int(target.rsplit("-", 1)[1])
        os.kill(pid, 0)
        return pid
    except Exception:  # noqa: BLE001
        return None


def _idle_limit() -> float:
    try:
        return float(os.environ.get("DOTFILES_HERMES_EDGE_IDLE_MIN", "10")) * 60
    except ValueError:
        return 600.0


def _edge_watcher():
    while True:
        time.sleep(30)
        try:
            limit = _idle_limit()
            with _edge_lock:
                pid, last = _edge_state["pid"], _edge_state["last_use"]
                if not pid or limit <= 0 or time.time() - last < limit:
                    continue
                if _edge_pid() == pid:
                    os.kill(pid, signal.SIGTERM)  # Chromium は SIGTERM で通常終了する（Cookie も保存される）
                    logger.info("dotfiles-bridge: idle のため専用 Edge (pid %s) を終了", pid)
                _edge_state["pid"] = None
        except Exception as e:  # noqa: BLE001
            logger.debug("dotfiles-bridge: edge watcher: %s", e)


def _ensure_edge(tool_name=None, **_kwargs):
    if tool_name not in _BROWSER_TOOLS or os.environ.get("DOTFILES_HERMES_EDGE") == "0":
        return None
    with _edge_lock:
        _edge_state["last_use"] = time.time()
        if _edge_up():
            return None
        script = _DOTFILES / "adapters" / "hermes" / "scripts" / "hermes-edge.sh"
        try:
            subprocess.run(["/bin/sh", str(script)], env={**os.environ, "HERMES_EDGE_BACKGROUND": "1"},
                           capture_output=True, timeout=10)
        except Exception as e:  # noqa: BLE001 — 起動できなくてもツールは通す（エラーはツール側で出る）
            logger.warning("dotfiles-bridge: 専用 Edge を起動できません: %s", e)
            return None
        deadline = time.time() + 20
        while time.time() < deadline and not _edge_up():
            time.sleep(0.5)
        if _edge_up():
            _edge_state["pid"] = _edge_pid()
            _edge_state["last_use"] = time.time()
            logger.info("dotfiles-bridge: 専用 Edge を起動 (pid %s)", _edge_state["pid"])
            if not _edge_state["watcher"]:
                threading.Thread(target=_edge_watcher, name="dotfiles-edge-idle", daemon=True).start()
                _edge_state["watcher"] = True
    return None


def _touch_edge(tool_name=None, **_kwargs):
    if tool_name in _BROWSER_TOOLS:
        _edge_state["last_use"] = time.time()


def register(ctx):
    n = len(_render())
    ctx.register_system_prompt_section("dotfiles.hermes", _slot(0), max_chars=SECTION_MAX)
    for i in range(1, n):
        ctx.register_system_prompt_section(f"dotfiles.shared-{i}", _slot(i), max_chars=SECTION_MAX)
    ctx.register_hook("pre_tool_call", _rtk_rewrite)
    ctx.register_hook("pre_tool_call", _guard_shared_skills)
    ctx.register_hook("pre_llm_call", _notify_proposals)
    ctx.register_hook("pre_llm_call", _notify_quota)
    ctx.register_hook("pre_tool_call", _route_delegate)
    ctx.register_hook("pre_tool_call", _ensure_edge)
    ctx.register_hook("post_tool_call", _touch_edge)
