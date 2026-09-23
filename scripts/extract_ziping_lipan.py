#!/usr/bin/env python3
"""开发期工具：从《子平真诠评注》校对本抽出徐评里的命例，写成测试夹具，并拿八格章的命例校 determine_structure 的取格。

    python scripts/extract_ziping_lipan.py            → 写 bazi_core/tests/fixtures/ziping_lipan.json 与 references/校核/格局_例盘报告.md
    python scripts/extract_ziping_lipan.py --check    → 只打印

每张例盘：id（章号-序）、四柱、章名、印刷页、书中判词（紧随其后的徐评段首句，二十章体例是说明在前则取前一段）。
八格章（三十一至四十六）的例盘另带 expectedStructures：按章名给出应取的格（财格分正偏、印格分正偏、建禄月劫分两格），
与 shishen.determine_structure 的结果比对，一致率写进报告；不一致的逐张列出，供人看是取格代码的问题还是徐评另有取法。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bazi_core.shishen import determine_structure  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROOF = ROOT / "source" / "text" / "子平真诠_格局.md"
FIXTURE = ROOT / "scripts" / "bazi_core" / "tests" / "fixtures" / "ziping_lipan.json"
REPORT = ROOT / "references" / "校核" / "格局_例盘报告.md"

GANZHI = re.compile(r"^[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]$")
CHAPTER_STRUCT = {
    "论正官": ["正官格"], "论财": ["正财格", "偏财格"], "论印绶": ["正印格", "偏印格"], "论食神": ["食神格"],
    "论偏官": ["七杀格"], "论伤官": ["伤官格"], "论阳刃": ["月刃格"], "论建禄月劫": ["建禄格", "月劫格"],
}


def chapter_key(title: str) -> str | None:
    t = re.sub(r"[①-⑩]", "", title)
    m = re.match(r"^[一二三四五六七八九十]+、(论\S+?)(取运)?$", t)
    if not m:
        return None
    return m.group(1)


def _cn_num(t: str) -> int:
    """中文章号转数：八 → 8，三十二 → 32，四十八 → 48。"""
    d = {c: i for i, c in enumerate("零一二三四五六七八九")}
    if "十" not in t:
        return d.get(t, 0)
    tens, _, ones = t.partition("十")
    return (d.get(tens, 1) if tens else 1) * 10 + (d.get(ones, 0) if ones else 0)


def extract() -> list[dict]:
    lines = PROOF.read_text(encoding="utf-8").splitlines()
    cases: list[dict] = []
    chapter, chapter_no, page, seq = "", "", "", 0
    for i, line in enumerate(lines):
        m = re.match(r"<!-- (p\d{3}) -->", line)
        if m:
            page = m.group(1); continue
        if line.startswith("[标题] "):
            t = line[5:].strip()
            if re.match(r"^[一二三四五六七八九十]+、", t):
                chapter, seq = t, 0
                chapter_no = t.split("、")[0]
            continue
        if not line.startswith("[例盘] "):
            continue
        parts = line[5:].strip().split()
        if len(parts) != 4 or not all(GANZHI.match(p) for p in parts):
            continue
        seq += 1
        # 干支阴阳不配（"丙亥"）是原书误印或校对残留，标出来不比取格；p253 甲申乙亥丙亥庚寅已对图，书即如此，徐评"寅戌拱午"知当作丙戌
        bad = [x for x in parts if "甲乙丙丁戊己庚辛壬癸".index(x[0]) % 2 != "子丑寅卯辰巳午未申酉戌亥".index(x[1]) % 2]
        # 判词：本书两种排法。三十一章以前徐评在前、例盘在后（"此伍廷芳之造也……[例盘]"）；
        # 八格取运各章例盘在前、徐评在后（"[例盘]……此为论正官篇薛相公命"）。按章号定先后，取不到再取另一边。
        def _find(rng):
            for j in rng:
                if lines[j].startswith("[徐评] "):
                    return lines[j][5:].strip()
                if lines[j].startswith("[例盘] ") or lines[j].startswith("[标题] ") or lines[j].startswith("[原文] "):
                    return ""
            return ""
        after = range(i + 1, min(i + 4, len(lines)))
        before = range(i - 1, max(i - 4, -1), -1)
        comment = (_find(before) or _find(after)) if _cn_num(chapter_no) < 31 else (_find(after) or _find(before))
        key = chapter_key(chapter)
        case = {"id": f"{chapter_no}-{seq:02d}", "pillars": parts, "chapter": chapter, "page": page,
                "comment": comment, "flags": ["干支阴阳不配：" + "、".join(bad)] if bad else []}
        if bad:
            cases.append(case); continue
        if key in CHAPTER_STRUCT and not chapter.startswith(("八、", "九、")):
            case["expectedStructures"] = CHAPTER_STRUCT[key]
            s = determine_structure(*parts)
            case["computedStructure"] = s.name
            case["monthBase"] = s.base
            case["variation"] = s.variation
            case["also"] = s.also or []
            case["structureBasis"] = s.basis
        cases.append(case)
    return cases


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    cases = extract()
    graded = [c for c in cases if "expectedStructures" in c]
    hit_base = [c for c in graded if c["monthBase"] in c["expectedStructures"]]
    miss = [c for c in graded if c["monthBase"] not in c["expectedStructures"]]
    hit_name = [c for c in graded if c["computedStructure"] in c["expectedStructures"]]
    varied = [c for c in graded if c["variation"]]
    lines = ["# 子平真诠例盘抽取与取格比对", "",
             f"生成：{date.today().isoformat()}。校对本 `source/text/子平真诠_格局.md` 的 [例盘] 段共 {len(cases)} 张四柱齐全的命例；"
             f"八格章（三十一至四十六）{len(graded)} 张，月令本格（base）与章名相符 {len(hit_base)} 张，不符 {len(miss)} 张；"
             f"变格（name）与章名相符 {len(hit_name)} 张，带变格的 {len(varied)} 张。", "",
             "## 取格口径（2026-09-23 按本表裁定）", "",
             "徐评归章按**月令本格**：生地（寅申巳亥）与专气（子午卯酉）依本气当旺之神，不问透否（\"先用当旺之神，次及得气之神，乃一定之次序\"，论用神变化徐评）；"
             "杂气（辰戌丑未）透干取之，按五行认（\"甲生辰月，透壬为印\"），兼透则兼用，格名本气先、次官煞、次藏干序，皆不透以本气土论；本气比劫无可取者为月劫格。",
             "**变格**另记：月支与另两支会成三合三会且非日主同气，随局取格（\"寅午戌三合变化在前\"）；生地本气不透而中气余气透，舍本气用透者（\"不透甲而透丙，则同知得以作主\"）。"
             "禄刃劫不变格。成败救应条件按变格查，本格不同时一并带出（monthBase），杂气兼用格带出（also）。", "",
             "裁前口径是\"本气不透看中气余气何者透\"，本气未透而中气透的 13 张只中 5 张；裁后本格中 12 张。杂气两张（三十二-01、四十二-10）徐评按透干归章，与生地相反，故分类处理。", "",
             "## 本格与章名不符", "",
             "| 例盘 | 章 | 页 | 四柱 | 本格 | 变格 | 兼用 | 依据 | 判词 |", "|---|---|---|---|---|---|---|---|---|"]
    for c in miss:
        lines.append(f"| {c['id']} | {c['chapter']} | {c['page']} | {' '.join(c['pillars'])} | {c['monthBase']} | {c['computedStructure'] if c['variation'] else ''} | {'、'.join(c['also'])} | {c['structureBasis']} | {c['comment'][:40]} |")
    lines += ["", "## 带变格的例盘（本格即章名，变格是徐评判词里实际论的格）", "",
              "| 例盘 | 章 | 四柱 | 本格 | 变格 | 路径 | 判词 |", "|---|---|---|---|---|---|---|"]
    for c in varied:
        lines.append(f"| {c['id']} | {c['chapter']} | {' '.join(c['pillars'])} | {c['monthBase']} | {c['computedStructure']} | {c['variation']} | {c['comment'][:40]} |")
    flagged = [c for c in cases if c["flags"]]
    if flagged:
        lines += ["", "## 干支阴阳不配（原书误印或校对残留，已对图的注在脚本里）", ""] + [f"- {c['id']} {c['page']} {' '.join(c['pillars'])}：{c['flags'][0]}" for c in flagged]
    by_chapter: dict[str, int] = {}
    for c in cases:
        by_chapter[c["chapter"]] = by_chapter.get(c["chapter"], 0) + 1
    lines += ["", "## 各章例盘数", ""] + [f"- {k}：{v}" for k, v in by_chapter.items()]
    print("\n".join(lines[:4]))
    if not a.check:
        FIXTURE.write_text(json.dumps({"schema": "ziping-lipan/1", "generated": date.today().isoformat(),
                                       "source": "source/text/子平真诠_格局.md 的 [例盘] 段，徐乐吾评注命例", "cases": cases},
                                      ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("→", FIXTURE, REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
