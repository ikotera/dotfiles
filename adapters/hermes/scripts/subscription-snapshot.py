#!/usr/bin/env python3
"""subscription-snapshot.py — 両サブスクリプションで今使えるモデルの一覧・プラン名・現在のルート設定を出力する。

週次の確認ジョブ（cron「subscription-review」）がこの出力を前回分と比べ、変更案を作る。
AI を呼ばない（Claude はモデル一覧の取得時の初期化だけで、Messages リクエストは送らない）。
"""
import json, os, subprocess
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
PY = HOME / "hermes-agent" / "venv" / "bin" / "python"
CODE = r"""
import json
from hermes_cli.models import provider_model_ids
out = {}
for p in ['claude-subscription-directsdk-experimental', 'openai-codex']:
    try: out[p] = sorted(provider_model_ids(p))
    except Exception as e: out[p] = 'error: %s' % e
print(json.dumps(out))
"""


def run(cmd, timeout=120):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(HOME / "hermes-agent"))
    return r.stdout.strip()


models = json.loads(run([str(PY), "-c", CODE]) or "{}")
plans = {}
for p in models:
    try:
        u = json.loads(run(["hermes", "usage", "--provider", p, "--json"], 60))
        plans[p] = {"plan": u.get("plan"), "details": [d for d in u.get("details", []) if "spent" not in d and "by surface" not in d]}
    except Exception as e:
        plans[p] = {"error": str(e)[:200]}
routes = run(["hermes", "delegation", "config", "--show"], 60)
fallback = run(["hermes", "fallback", "list"], 60)
main = run(["hermes", "config", "get", "model.default"], 30)

print("## 使えるモデル")
for p, ids in models.items():
    print(f"- {p}: {ids if isinstance(ids, str) else ', '.join(ids)}")
print("\n## プラン")
for p, v in plans.items():
    print(f"- {p}: {json.dumps(v, ensure_ascii=False)}")
print(f"\n## メインモデル\n{main}\n\n## ルート\n{routes}\n\n## 予備の接続先\n{fallback}")
