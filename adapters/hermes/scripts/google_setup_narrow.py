"""google-workspace の setup.py を、Gmail とカレンダーの権限だけで実行するラッパー。
setup.py は全権限（Drive・Docs・Sheets・連絡先を含む）を一括で求め、Google の旧来の同意画面では
個別に外せないため、要求する権限（SCOPES）だけを差し替えて同じ処理を呼ぶ。"""
import importlib.util
import os
import sys

SETUP = os.path.expanduser("~/.hermes/skills/productivity/google-workspace/scripts/setup.py")
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]

sys.path.insert(0, os.path.dirname(SETUP))
spec = importlib.util.spec_from_file_location("gw_setup", SETUP)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.SCOPES = SCOPES
sys.argv[0] = SETUP
mod.main()
