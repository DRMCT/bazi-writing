#!/usr/bin/env python3
"""从作者自备的《闲情偶寄》译注本 epub 里抽李渔原文，写成戏剧层校核卡的语料
references/校核/语料/闲情偶寄_结构.txt（词曲部结构第一，小序加七款）。

用法：
    python scripts/extract_xianqing.py "路径/闲情偶寄….epub"

只取原文段（epub 里 class 为 normaltext0 的段落）。今人的题解、注释、译文（normaltext1、note1、normaltext2）
一字不取：原文是公有领域，译注属于整理者。原文里的注码（sup）去掉，标点照整理本。
语料目录不进公开库（export_public.py 的 EXCLUDE）。
"""
from __future__ import annotations

import re
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "references" / "校核" / "语料" / "闲情偶寄_结构.txt"
PART = "OEBPS/Text/part0007.xhtml"
START, END = "结构第一", "词采第二"
BLOCK = re.compile(r'<(h\d|p)[^>]*class="([^"]+)"[^>]*>(.*?)</\1>', re.S)


def clean(html: str) -> str:
    s = re.sub(r"<sup.*?</sup>", "", html, flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", "", s).replace("&nbsp;", "")


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    text = zipfile.ZipFile(argv[0]).read(PART).decode("utf-8")
    lines = ["# 《闲情偶寄》词曲部结构第一语料",
             f"来源：作者自备的译注本 epub，只取李渔原文段，题解、注释、译文不取；标点照整理本。取得日期 {date.today().isoformat()}。"
             "原文为公有领域古籍。", ""]
    on, paras, heads = False, 0, 0
    for tag, cls, body in BLOCK.findall(text):
        s = clean(body)
        if tag.startswith("h"):
            if s.startswith(START):
                on = True
                lines += ["## 结构第一（小序）", ""]
                heads += 1
                continue
            if s.startswith(END):
                break
            if on:
                lines += [f"## {s}", ""]
                heads += 1
            continue
        if on and cls == "normaltext0" and s:
            lines += [s, ""]
            paras += 1
    OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"{OUT}: {heads} 节，{paras} 段，{sum(len(x) for x in lines[3:])} 字")
    return 0 if heads == 8 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
