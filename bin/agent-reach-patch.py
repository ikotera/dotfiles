#!/usr/bin/env python3
"""Agent Reach（Panniantong/Agent-Reach）の手元の改変を、インストール済みのパッケージに当てる。

`agent-reach update` や `uv tool upgrade` で元に戻るので、そのたびに実行する（何度実行してもよい）。

使い方: agent-reach-patch [--update] [--check] [--rate-limit-seconds N]
  --update               先に `agent-reach update` を実行してから当てる
  --check                当たっているかを表示するだけ（書き換えない）
  --rate-limit-seconds   429 を受けたあとチャネルを止める秒数（既定 600。上流は 3600）

改変の内容:
  1. runtime/dispatch.py: RATE_LIMIT_SECONDS を上流の 3600 から N 秒へ。
  2. channels/youtube.py:
     - subtitle の既定の言語を `orig`（動画の元の言語）にする。
     - 字幕は動画情報から1本だけ選び、その1本だけを取りに行く。上流は --sub-langs に一致する
       字幕（自動翻訳の字幕を含む）を全部取りに行き、自動翻訳の字幕で HTTP 429 になりやすい。
     - read の raw に元の言語（language）を入れる。
上流の書き方が変わって目印が見つからないときは、何も書き換えずに止まる。
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

MARK = "dotfiles-patch"

SUBTITLE_NEW = '''    def _ytdlp_subtitle(self, *, target: str, lang: str, timeout: float) -> list:
        # dotfiles-patch: 動画情報から字幕を1本だけ選び、その1本だけを取りに行く（既定は元の言語）。
        import time

        started = time.monotonic()
        url = _video_url(target)
        wanted = [x.strip() for x in (lang or "orig").split(",") if x.strip()] or ["orig"]
        with private_temporary_directory(prefix="agent-reach-subs-") as tmp:
            out = _run_ytdlp(["--skip-download", "--dump-json", url], timeout, cwd=tmp)
            info = json.loads(out.splitlines()[-1])
            code, auto = _pick_subtitle_track(info, wanted)
            if code is None:
                raise ReachError(NOT_FOUND, f"no subtitles in {', '.join(wanted)} for this video")
            info_path = os.path.join(tmp, "info.json")
            with open(info_path, "w", encoding="utf-8") as fh:
                json.dump(info, fh)
            _run_ytdlp(
                [
                    "--load-info-json", info_path,
                    "--skip-download", "--no-simulate",
                    "--write-auto-subs" if auto else "--write-subs",
                    "--sub-langs", re.escape(code), "--sub-format", "vtt",
                    "-o", "%(id)s.%(ext)s",
                ],
                max(10.0, timeout - (time.monotonic() - started)),
                cwd=tmp,
            )
            files = [f for f in os.listdir(tmp) if f.endswith(".vtt")]
            if not files:
                raise ReachError(NOT_FOUND, f"subtitle track {code} could not be downloaded")
            with open(os.path.join(tmp, files[0]), encoding="utf-8", errors="replace") as fh:
                text = vtt_to_text(fh.read())
        return [make_item(title=info.get("title"), url=info.get("webpage_url") or url, text=text,
                          raw={"lang": code, "auto": auto, "original_language": info.get("language")})]

'''

PICK_FN = '''

def _pick_subtitle_track(info: dict, wanted: list):
    """dotfiles-patch: 希望の順に、実在する字幕を1本選ぶ。`orig` は動画の元の言語。

    戻り値は (言語コード, 自動字幕か)。見つからなければ (None, False)。
    """
    manual = {k for k in (info.get("subtitles") or {}) if k != "live_chat"}
    auto = set(info.get("automatic_captions") or {})
    orig = (info.get("language") or "").strip()

    def candidates(token: str) -> list:
        if token.lower() != "orig":
            return [(token, False), (token, True)]
        found = []
        if orig:
            base = orig.split("-")[0]
            found.append((orig, False))
            found += [(k, False) for k in sorted(manual) if k != orig and k.split("-")[0] == base]
            found += [(orig + "-orig", True), (orig, True)]
        found += [(k, True) for k in sorted(auto) if k.endswith("-orig")]
        if len(manual) == 1:
            found.append((next(iter(manual)), False))
        return found

    for token in wanted:
        for code, is_auto in candidates(token):
            if code in (auto if is_auto else manual):
                return code, is_auto
    return None, False
'''


def package_dir() -> Path:
    tools = subprocess.run(["uv", "tool", "dir"], capture_output=True, text=True, check=True).stdout.strip()
    hits = sorted(Path(tools, "agent-reach").glob("lib/python*/site-packages/agent_reach"))
    if not hits:
        sys.exit("agent-reach が uv tool に見つからない（uv tool install で入れてから実行する）")
    return hits[-1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"目印が見つからない（上流の変更の可能性）: {label}")
    return text.replace(old, new)


def patch_dispatch(text: str, seconds: int) -> str:
    pat = re.compile(r"^RATE_LIMIT_SECONDS = \d+.*$", re.M)
    if len(pat.findall(text)) != 1:
        raise SystemExit("目印が見つからない（上流の変更の可能性）: RATE_LIMIT_SECONDS")
    return pat.sub(f"RATE_LIMIT_SECONDS = {seconds}  # {MARK}: upstream 3600", text)


def patch_youtube(text: str) -> str:
    if MARK in text:
        return text
    text = replace_once(
        text,
        '_RAW_KEYS = ("id", "duration", "view_count", "like_count", "channel_id", "tags", "categories")',
        '_RAW_KEYS = ("id", "duration", "view_count", "like_count", "channel_id", "tags", "categories", "language")',
        "_RAW_KEYS",
    )
    text = replace_once(
        text,
        'Param("lang", "preferred languages, comma separated", required=False, default="zh-Hans,zh,en,en-orig")',
        'Param("lang", "preferred languages, comma separated; orig = the video\'s original language",'
        ' required=False, default="orig")',
        "subtitle lang default",
    )
    m = re.search(r"    def _ytdlp_subtitle\(.*?(?=    def _whisper_transcribe\()", text, re.S)
    if not m:
        raise SystemExit("目印が見つからない（上流の変更の可能性）: _ytdlp_subtitle")
    text = text[: m.start()] + SUBTITLE_NEW + text[m.end():]
    anchor = "\n\ndef _video_url("
    return replace_once(text, anchor, PICK_FN + anchor, "_video_url")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--rate-limit-seconds", type=int, default=600)
    args = ap.parse_args()

    if args.update and not args.check:
        out = subprocess.run(["agent-reach", "update"], capture_output=True, text=True)
        try:
            res = json.loads(out.stdout.strip().splitlines()[-1])
            print(f"agent-reach update: ok={res.get('ok')} error={res.get('error')}")
        except (ValueError, IndexError):
            print(out.stdout, out.stderr, sep="\n")

    pkg = package_dir()
    files = {
        pkg / "runtime" / "dispatch.py": lambda t: patch_dispatch(t, args.rate_limit_seconds),
        pkg / "channels" / "youtube.py": patch_youtube,
    }
    for path, fn in files.items():
        old = path.read_text(encoding="utf-8")
        new = fn(old)
        name = path.relative_to(pkg)
        if args.check:
            print(f"{name}: {'patched' if MARK in old else 'NOT patched'}")
        elif new != old:
            compile(new, str(path), "exec")
            path.write_text(new, encoding="utf-8")
            print(f"{name}: patched")
        else:
            print(f"{name}: already patched")


if __name__ == "__main__":
    main()
