#!/usr/bin/env python3
"""Zed の settings.json に Hermes を ACP の外部エージェントとして登録する（何度実行してもよい）。

settings.json はコメントや末尾のカンマを含む JSONC なので、JSON として読み書きせず、
"agent_servers" の開き括弧の直後へ文字列として差し込む。既に "hermes-agent" があれば何もしない。

使い方: zed-acp.py <hermes の絶対パス> [settings.json のパス]
"""
import json
import re
import shutil
import sys
import time
from pathlib import Path

hermes = sys.argv[1]
path = Path(sys.argv[2] if len(sys.argv) > 2 else Path.home() / ".config/zed/settings.json")

if not path.exists():
    print(f"Zed の設定なし（スキップ）: {path}")
    sys.exit(0)

text = path.read_text()
if '"hermes-agent"' in text:
    print(f"Zed: hermes-agent は登録済み: {path}")
    sys.exit(0)

entry = (
    '    "hermes-agent": {\n'
    '      "type": "custom",\n'
    f'      "command": {json.dumps(hermes)},\n'
    '      "args": ["acp"],\n'
    '    },\n'
)

m = re.search(r'"agent_servers"\s*:\s*\{[ \t]*\n?', text)
if m:
    new = text[: m.end()] + entry + text[m.end():]
else:
    end = text.rstrip().rfind("}")
    if end < 0:
        sys.exit(f"Zed の設定を解釈できません: {path}")
    head = text[:end].rstrip()
    sep = "" if head.endswith(("{", ",")) else ","
    new = head + sep + '\n  "agent_servers": {\n' + entry + "  },\n" + text[end:]

backup = path.with_name(f"{path.name}.pre-hermes.{time.strftime('%Y%m%d%H%M%S')}")
shutil.copy2(path, backup)
path.write_text(new)
print(f"Zed: hermes-agent を登録（退避: {backup.name}）: {path}")
