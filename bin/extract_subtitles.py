#!/usr/bin/env python3
"""動画ファイルに含まれる字幕を ffprobe で調べ、ffmpeg で .srt として抽出する。

使い方:
  1. このスクリプトを動画のあるフォルダにコピーする。
  2. そのフォルダで `python3 extract_subtitles.py` を実行する。
     （フォルダを引数で指定することもできる: `python3 extract_subtitles.py <フォルダ>`）

動作:
  - フォルダ直下の動画をすべて調べ（サブフォルダは対象外）、
    字幕を「動画と同じ名前.srt」として同じフォルダに保存する。
  - 字幕が複数ある動画は、抽出を始める前にどれを抽出するか確認する。
  - 一度選んだ字幕と「同じ Stream 番号・同じ名称」の字幕を持つ動画には、
    同じ選択を自動で適用する（シリーズものでの確認を1回で済ませる）。
    名称はストリームの title タグ、無ければ language タグを使う。
  - 画像形式の字幕（PGS、DVD、DVB など）は SRT に変換できないため対象外。
  - 既に同名の .srt がある動画は飛ばす（--overwrite で上書き）。

必要なもの: Python 3.8 以上、ffmpeg / ffprobe（PATH が通っていること）。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

VIDEO_EXTS = {
    ".mkv", ".mp4", ".m4v", ".mov", ".avi", ".webm", ".ts", ".m2ts",
    ".mts", ".wmv", ".flv", ".mpg", ".mpeg", ".ogv", ".3gp",
}
# SRT（テキスト）に変換できない画像形式の字幕
BITMAP_CODECS = {
    "hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub",
    "dvb_teletext", "pgssub", "vobsub",
}


@dataclass
class SubStream:
    index: int          # ファイル内の Stream 番号（全ストリーム通しの番号）
    codec: str
    language: str
    title: str
    default: bool
    forced: bool

    @property
    def name(self) -> str:
        return self.title or self.language or "(名称なし)"

    @property
    def key(self) -> tuple[int, str]:
        """シリーズ間で同じ字幕かを判定するキー（Stream 番号, 名称）。"""
        return (self.index, self.name)

    @property
    def is_text(self) -> bool:
        return self.codec not in BITMAP_CODECS

    def label(self) -> str:
        parts = [f"Stream #{self.index}"]
        if self.language:
            parts.append(f"[{self.language}]")
        if self.title:
            parts.append(f'"{self.title}"')
        parts.append(f"({self.codec})")
        flags = [f for f, on in (("default", self.default), ("forced", self.forced)) if on]
        if flags:
            parts.append("{" + ",".join(flags) + "}")
        return " ".join(parts)


@dataclass
class Plan:
    video: Path
    stream: SubStream | None
    note: str


def natural_key(p: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]


def probe_subtitles(video: Path) -> list[SubStream]:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "s",
        "-show_entries",
        "stream=index,codec_name:stream_tags=language,title:stream_disposition=default,forced",
        "-of", "json", str(video),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "ffprobe が失敗しました")
    streams = []
    for s in json.loads(res.stdout or "{}").get("streams", []):
        tags = {k.lower(): v for k, v in (s.get("tags") or {}).items()}
        disp = s.get("disposition") or {}
        streams.append(SubStream(
            index=int(s["index"]),
            codec=s.get("codec_name", "unknown"),
            language=tags.get("language", ""),
            title=tags.get("title", ""),
            default=bool(disp.get("default")),
            forced=bool(disp.get("forced")),
        ))
    return streams


def ask_choice(video: Path, candidates: list[SubStream], others: list[SubStream]) -> SubStream | None:
    print(f"\n▶ {video.name} には抽出できる字幕が {len(candidates)} 種類あります。")
    for i, s in enumerate(candidates, 1):
        print(f"   {i}) {s.label()}")
    for s in others:
        print(f"   -) {s.label()}  ※画像形式のため SRT に変換できません")
    while True:
        ans = input(f"   抽出する字幕の番号を入力してください [1-{len(candidates)}]"
                    "（s = この動画は抽出しない, q = 中止）: ").strip().lower()
        if ans == "q":
            print("中止しました。何も抽出していません。")
            sys.exit(1)
        if ans == "s":
            return None
        if ans.isdigit() and 1 <= int(ans) <= len(candidates):
            return candidates[int(ans) - 1]
        print("   入力が正しくありません。")


def build_plans(videos: list[Path], overwrite: bool) -> list[Plan]:
    chosen_keys: list[tuple[int, str]] = []     # 選ばれた順に記録
    skipped_sets: set[tuple] = set()            # 「抽出しない」と答えた字幕の組み合わせ
    plans: list[Plan] = []

    for video in videos:
        out = video.with_suffix(".srt")
        if out.exists() and not overwrite:
            plans.append(Plan(video, None, f"{out.name} が既にあるため飛ばす（--overwrite で上書き）"))
            continue
        try:
            subs = probe_subtitles(video)
        except Exception as e:  # noqa: BLE001
            plans.append(Plan(video, None, f"調査に失敗: {e}"))
            continue

        text_subs = [s for s in subs if s.is_text]
        bitmap_subs = [s for s in subs if not s.is_text]

        if not subs:
            plans.append(Plan(video, None, "字幕なし"))
            continue
        if not text_subs:
            plans.append(Plan(video, None, "画像形式の字幕のみ（SRT に変換できない）"))
            continue
        if len(text_subs) == 1:
            plans.append(Plan(video, text_subs[0], "字幕が1種類のみ"))
            continue

        # 以前に選んだ字幕（同じ Stream 番号・同じ名称）があれば、それを適用する
        by_key = {s.key: s for s in text_subs}
        remembered = next((by_key[k] for k in chosen_keys if k in by_key), None)
        if remembered:
            plans.append(Plan(video, remembered, "以前の選択を適用"))
            continue
        set_key = tuple(sorted(by_key))
        if set_key in skipped_sets:
            plans.append(Plan(video, None, "以前の選択（抽出しない）を適用"))
            continue

        choice = ask_choice(video, text_subs, bitmap_subs)
        if choice is None:
            skipped_sets.add(set_key)
            plans.append(Plan(video, None, "抽出しないを選択"))
        else:
            chosen_keys.append(choice.key)
            plans.append(Plan(video, choice, "選択"))
    return plans


def extract(video: Path, stream: SubStream) -> tuple[bool, str]:
    out = video.with_suffix(".srt")
    cmd = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video), "-map", f"0:{stream.index}", "-c:s", "srt", str(out),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        out.unlink(missing_ok=True)
        return False, res.stderr.strip().splitlines()[-1] if res.stderr.strip() else "ffmpeg が失敗しました"
    return True, out.name


def main() -> int:
    ap = argparse.ArgumentParser(description="フォルダ内の動画から字幕を .srt として抽出する")
    ap.add_argument("folder", nargs="?", help="対象フォルダ（省略時はこのスクリプトがあるフォルダ）")
    ap.add_argument("--overwrite", action="store_true", help="既存の .srt を上書きする")
    ap.add_argument("-y", "--yes", action="store_true", help="最後の実行確認を省く")
    args = ap.parse_args()

    for tool in ("ffprobe", "ffmpeg"):
        if shutil.which(tool) is None:
            print(f"エラー: {tool} が見つかりません。ffmpeg をインストールし、PATH を通してください。")
            return 2

    folder = Path(args.folder).resolve() if args.folder else Path(__file__).resolve().parent
    videos = sorted((p for p in folder.iterdir()
                     if p.is_file() and p.suffix.lower() in VIDEO_EXTS and not p.name.startswith(".")),
                    key=natural_key)
    if not videos:
        print(f"{folder} に動画ファイルが見つかりません。")
        return 0

    # 同じ名前（拡張子違い）の動画があると .srt の名前がぶつかるので警告する
    stems: dict[str, list[str]] = {}
    for v in videos:
        stems.setdefault(v.stem, []).append(v.name)
    for names in stems.values():
        if len(names) > 1:
            print(f"注意: {', '.join(names)} は同じ .srt 名になるため、後の動画で上書きされます。")

    print(f"対象フォルダ: {folder}")
    print(f"動画 {len(videos)} 本を調べます。")

    plans = build_plans(videos, args.overwrite)

    print("\n===== 抽出の計画 =====")
    for p in plans:
        target = p.stream.label() if p.stream else "—"
        print(f"  {p.video.name}\n      → {target}  （{p.note}）")
    todo = [p for p in plans if p.stream]
    if not todo:
        print("\n抽出する字幕はありません。")
        return 0

    if not args.yes:
        ans = input(f"\n{len(todo)} 本の動画から字幕を抽出します。実行しますか？ [Y/n]: ").strip().lower()
        if ans not in ("", "y", "yes"):
            print("中止しました。何も抽出していません。")
            return 1

    ok = 0
    for p in todo:
        success, msg = extract(p.video, p.stream)
        mark = "✓" if success else "✗"
        print(f"  {mark} {p.video.name} → {msg}")
        ok += success
    print(f"\n完了: {ok} / {len(todo)} 本で抽出に成功しました。")
    return 0 if ok == len(todo) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n中断しました。")
        sys.exit(130)
