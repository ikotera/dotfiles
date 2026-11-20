#!/usr/bin/env python3
"""quota-status.py — Claude と ChatGPT の両サブスクリプションの使用率を1度に表示する。

使い方:
  quota-status.py            人が読む表（オーケストレーターが委任先を決める前に使う）
  quota-status.py --json     機械可読
  quota-status.py --alert 80 どれかの枠が 80% 以上になったときだけ出力（cron 用。同じ枠・同じリセット時刻では1回だけ）

値は `hermes usage --provider <p> --json` から取る。AI を呼ばないので枠は消費しない。
"""
import json, os, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

PROVIDERS = {
    "claude": "claude-subscription-directsdk-experimental",
    "openai": "openai-codex",
}
HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
STATE = HOME / "cache" / "quota-alert-state.json"


def hermes_bin():
    for c in (shutil.which("hermes"), str(Path.home() / ".local/bin/hermes")):
        if c and Path(c).exists():
            return c
    sys.exit("hermes が見つかりません")


def fetch(provider):
    try:
        out = subprocess.run([hermes_bin(), "usage", "--provider", provider, "--json"],
                             capture_output=True, text=True, timeout=60)
        return json.loads(out.stdout) if out.returncode == 0 else {"error": out.stderr.strip()[:200]}
    except Exception as e:  # 取得失敗は表示して続ける
        return {"error": str(e)[:200]}


def local(ts):
    if not ts:
        return "-"
    return datetime.fromisoformat(ts).astimezone().strftime("%m/%d %H:%M")


def collect():
    rows = []
    for short, prov in PROVIDERS.items():
        d = fetch(prov)
        if "error" in d or not d.get("windows"):
            rows.append({"account": short, "plan": None, "window": "?", "used": None, "resets": None,
                         "error": d.get("error") or d.get("unavailable_reason")})
            continue
        for w in d["windows"]:
            rows.append({"account": short, "plan": d.get("plan"), "window": w["label"],
                         "used": w.get("used_percent"), "resets": w.get("resets_at")})
    return rows


def main(argv):
    rows = collect()
    if "--json" in argv:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if "--alert" in argv:
        th = float(argv[argv.index("--alert") + 1])
        state = json.loads(STATE.read_text()) if STATE.exists() else {}
        msgs = []
        for r in rows:
            if r.get("used") is not None and r["used"] >= th:
                key = f'{th:g}:{r["account"]}:{r["window"]}:{r["resets"]}'
                if key not in state:
                    state[key] = datetime.now(timezone.utc).isoformat()
                    msgs.append(f'⚠ {r["account"]} {r["window"]}: {r["used"]:.0f}%（リセット {local(r["resets"])}）')
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state))
        if msgs:
            text = "サブスクリプションの使用率が閾値を超えました\n" + "\n".join(msgs)
            print(text)
            if "--notify" in argv and shutil.which("osascript"):  # macOS の通知センターにも出す
                body = " / ".join(m.lstrip("⚠ ") for m in msgs).replace('"', "'")
                subprocess.run(["osascript", "-e", f'display notification "{body}" with title "Hermes: 使用率の警告"'],
                               capture_output=True, timeout=10)
        return
    for r in rows:
        used = "取得失敗: " + str(r.get("error")) if r.get("used") is None else f'{r["used"]:.0f}%'
        print(f'{r["account"]:<7} {str(r["plan"] or ""):<5} {r["window"]:<16} {used:>6}  reset {local(r["resets"])}')


if __name__ == "__main__":
    main(sys.argv[1:])
