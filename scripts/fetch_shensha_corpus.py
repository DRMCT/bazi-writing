#!/usr/bin/env python3
"""从维基文库取《三命通会》《渊海子平》里论神煞的篇章，切成校核语料 references/校核/语料/。

    python scripts/fetch_shensha_corpus.py            → 下载并写语料
    python scripts/fetch_shensha_corpus.py --offline  → 用 --cache 目录里已下载的 wikitext

维基文库正文为公有领域古籍，页面文本按 CC BY-SA 4.0 再利用，语料文件头注明来源与取得日期。
只做切篇与去 wiki 标记，不改字：维基文库这个本子是简体录入，形近误字（已/巳、戍/戌）照录，校核时对照。
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "references" / "校核" / "语料"
UA = "bazi-writing corpus fetch (+https://github.com/DRMCT/bazi-writing)"

# 书 → (页面标题列表, 要切的篇名, 输出文件)。篇名按维基文库的 == 标题 ==，简体。
BOOKS = {
    "三命通会": {
        "pages": ["三命通會/卷二", "三命通會/卷三", "三命通會/卷六"],
        # 论太极贵里有「文昌贵」口诀；总论诸神煞里有阴阳差错煞十二日与桃花红艳煞
        "sections": ["论支元三合", "论将星华盖", "论咸池", "论驿马", "论天乙贵人", "论天月德", "论太极贵", "论学堂词馆",
                     "论劫煞亡神", "论羊刃", "论空亡", "论孤辰寡宿", "总论诸神煞", "魁罡", "论阳刃（前论羊刃煞与此参看）"],
        "out": "三命通会_神煞.txt",
    },
    "渊海子平": {
        "pages": ["淵海子平"],
        "sections": ["论阳刃", "论日刃", "论日贵", "论日德", "论魁罡", "论金神", "喜忌篇"],
        "out": "渊海子平_神煞.txt",
    },
    # 神峰通考页面无 == 标题，神煞歌诀连排在一段，按首尾段落切
    "神峰通考": {
        "pages": ["神峰通考"],
        "sections": [],
        "ranges": [("神煞歌诀（天德至孤虚神）", "天德  解曰", "孤虚神  解曰")],
        "out": "神峰通考_神煞.txt",
    },
}


def fetch(title: str, cache: Path) -> str:
    cache.mkdir(parents=True, exist_ok=True)
    f = cache / (title.replace("/", "_") + ".txt")
    if f.exists():
        return f.read_text(encoding="utf-8")
    url = "https://zh.wikisource.org/w/index.php?title=" + urllib.parse.quote(title) + "&action=raw"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8")
    f.write_text(text, encoding="utf-8")
    return text


def strip_wiki(s: str) -> str:
    s = re.sub(r"\{\{[^}]*\}\}", "", s)
    s = re.sub(r"</?onlyinclude>", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"'{2,}", "", s)
    # 维基文库按原书行宽换行，段内合并成一行；空行分段
    paras = [re.sub(r"\s*\n\s*", "", p).strip() for p in re.split(r"\n\s*\n", s)]
    return "\n\n".join(p for p in paras if p)


def split_sections(wikitext: str) -> dict[str, str]:
    out: dict[str, str] = {}
    parts = re.split(r"(?m)^==+\s*(.+?)\s*==+\s*$", wikitext)
    for i in range(1, len(parts) - 1, 2):
        out[parts[i].strip()] = parts[i + 1]
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--cache", default=str(ROOT / "source" / "wikisource"))
    a = ap.parse_args(argv)
    cache = Path(a.cache)
    for book, spec in BOOKS.items():
        found: dict[str, tuple[str, str]] = {}
        for page in spec["pages"]:
            if a.offline and not (cache / (page.replace("/", "_") + ".txt")).exists():
                print(f"缺缓存：{page}", file=sys.stderr)
                return 1
            text = fetch(page, cache)
            secs = split_sections(text)
            for name in spec["sections"]:
                if name in secs and name not in found:
                    found[name] = (page, strip_wiki(secs[name]))
            for name, start, end in spec.get("ranges", []):
                i, j = text.find(start), text.find(end)
                if i >= 0 and j > i:
                    j = text.find("\n\n", j)
                    found[name] = (page, strip_wiki(text[i:j if j > 0 else None]))
        wanted = spec["sections"] + [r[0] for r in spec.get("ranges", [])]
        missing = [n for n in wanted if n not in found]
        lines = [f"# 《{book}》神煞篇章语料",
                 f"来源：维基文库 zh.wikisource.org，页面 {'、'.join(spec['pages'])}，取得日期 {date.today().isoformat()}。"
                 "正文为公有领域古籍，录入文本按 CC BY-SA 4.0。简体录入本，形近误字照录未改。", ""]
        for name in wanted:
            if name not in found:
                continue
            page, body = found[name]
            lines += [f"## {name}", f"（{page}）", "", body, ""]
        out = OUT_DIR / spec["out"]
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"{book}: {len(found)} 篇 → {out}" + (f"；未找到：{'、'.join(missing)}" if missing else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
