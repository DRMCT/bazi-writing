#!/usr/bin/env python3
"""从维基文库取《黄帝内经素问》运气七篇（天元纪、五运行、六微旨、气交变、五常政、六元正纪、至真要），切成校核语料
references/校核/语料/素问_运气.txt，供五运六气校核卡（references/校核/运气_*.md）抄引文与 check_cards.py 核对。

用法：
    python scripts/fetch_yunqi_corpus.py            # 联网取（缓存在 source/wikisource/，gitignore）
    python scripts/fetch_yunqi_corpus.py --offline  # 只用缓存

维基文库《黃帝內經》分卷页面是繁体录入本，每篇一个 == 标题 ==；同卷的刺法论、本病论不取。
正文为公有领域古籍，页面文本按 CC BY-SA 4.0 再利用。只做切篇与去 wiki 标记，不改字、不转简体：
引文栏抄繁体原文，采用规则与叙事译法用简体。取用与去标记函数复用 fetch_shensha_corpus.py。
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_shensha_corpus import fetch, split_sections, strip_wiki  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "references" / "校核" / "语料" / "素问_运气.txt"

# 页面 → 要切的篇名（按维基文库的 == 标题 ==，含篇序）
PAGES = {
    "黃帝內經/素問第十九卷": ["天元紀大論六十六", "五運行大論六十七", "六微旨大論六十八"],
    "黃帝內經/素問第二十卷": ["氣交變大論六十九", "五常政大論七十"],
    "黃帝內經/素問第二十一卷": ["六元正紀大論七十一"],
    "黃帝內經/素問第二十二卷": ["至真要大論七十四"],
}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--cache", default=str(ROOT / "source" / "wikisource"))
    a = ap.parse_args(argv)
    cache = Path(a.cache)
    lines = ["# 《素问》运气七篇语料",
             f"来源：维基文库 zh.wikisource.org，页面 {'、'.join(PAGES)}，取得日期 {date.today().isoformat()}。"
             "正文为公有领域古籍，录入文本按 CC BY-SA 4.0。繁体录入本，只切篇与去 wiki 标记，不改字。"
             "本书七篇论岁气、物候与民病，没有「某年生人禀某气」之文；以生年运气推人的底子是后世运气家的引申，卡的叙事译法栏自起草。", ""]
    for page, names in PAGES.items():
        if a.offline and not (cache / (page.replace("/", "_") + ".txt")).exists():
            print(f"缺缓存：{page}", file=sys.stderr)
            return 1
        secs = split_sections(fetch(page, cache))
        for name in names:
            if name not in secs:
                print(f"缺篇：{page} {name}", file=sys.stderr)
                return 1
            lines += [f"## {name}", f"（{page}）", "", strip_wiki(secs[name]), ""]
    OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    body = OUT.read_text(encoding="utf-8")
    print(f"{OUT}: {len(body)} 字，{sum(1 for ln in body.splitlines() if ln.startswith('## '))} 篇")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
