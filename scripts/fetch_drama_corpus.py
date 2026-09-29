#!/usr/bin/env python3
"""从维基文库取金圣叹《读第五才子书法》，写成戏剧层校核卡的语料 references/校核/语料/读第五才子书法.txt。

用法：
    python scripts/fetch_drama_corpus.py            # 联网取（缓存在 source/wikisource/，gitignore）
    python scripts/fetch_drama_corpus.py --offline  # 只用缓存

繁体录入本，只去 wiki 标记，不改字、不转简体：卡的引文栏抄繁体原文，问法与落点用简体。
正文为公有领域古籍，页面文本按 CC BY-SA 4.0 再利用。李渔《闲情偶寄》结构第一的语料另由 extract_xianqing.py 从作者自备的整理本抽原文。
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_shensha_corpus import fetch, strip_wiki  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "references" / "校核" / "语料" / "读第五才子书法.txt"
PAGE = "讀第五才子書法"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--cache", default=str(ROOT / "source" / "wikisource"))
    a = ap.parse_args(argv)
    cache = Path(a.cache)
    if a.offline and not (cache / (PAGE + ".txt")).exists():
        print(f"缺缓存：{PAGE}", file=sys.stderr)
        return 1
    body = strip_wiki(fetch(PAGE, cache))
    head = ["# 金圣叹《读第五才子书法》语料",
            f"来源：维基文库 zh.wikisource.org，页面 {PAGE}，取得日期 {date.today().isoformat()}。"
            "正文为公有领域古籍，录入文本按 CC BY-SA 4.0。繁体录入本，只去 wiki 标记，不改字。", ""]
    OUT.write_text("\n".join(head) + body + "\n", encoding="utf-8", newline="\n")
    print(f"{OUT}: {len(body)} 字，{body.count(chr(10) + chr(10)) + 1} 段")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
