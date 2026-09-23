#!/usr/bin/env python3
"""从十卷校对本抽《穷通宝鉴评注》例盘，写成测试夹具 bazi_core/tests/fixtures/qiongtong_lipan.json。

    python scripts/extract_lipan.py            → 写夹具与报告 references/校核/例盘_抽取报告.md
    python scripts/extract_lipan.py --check    → 只打印报告

例盘段在校对本里打 [例盘] 标签：第一行四柱（"戊寅，甲寅，甲辰，乙亥。孝廉。"），
后面或有生年月日时（"光绪十六年正月二十三日寅时"）、断语、"按：……"。
例盘段的 OCR 残留（已/巳、成/戌、葵/癸、王/壬、卵/卯）未回校，这里按干支位置归一，
并把改动记在 ocrFixed 里；归一后仍不成四柱的例盘列在报告里，不入夹具。

夹具每条：id、dayMaster（卷）、section（所在月份标题给出的月支）、page、pillars、raw、
judgment（四柱行余下文字与后续断语行，不含"按："行）、note（"按："行）、name（"某某命"）、
date（原文纪年行）、lunar（解析出的农历年月日时，year 为公历年份，leap 为闰月）、flags（自检疑点）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
TEXT = ROOT / "source" / "text"
OUT = ROOT / "scripts" / "bazi_core" / "tests" / "fixtures" / "qiongtong_lipan.json"
REPORT = ROOT / "references" / "校核" / "例盘_抽取报告.md"

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEM_FIX = {"王": "壬", "葵": "癸", "已": "己", "巳": "己", "于": "壬", "戌": "戊", "戍": "戊"}
BRANCH_FIX = {"已": "巳", "己": "巳", "成": "戌", "戍": "戌", "卵": "卯", "末": "未", "戊": "戌", "西": "酉"}
STEM_ANY = STEMS + "".join(STEM_FIX)
BRANCH_ANY = BRANCHES + "".join(BRANCH_FIX)
PILLAR = rf"([{STEM_ANY}])([{BRANCH_ANY}])"
LINE = re.compile(rf"^\[例盘\]\s*{PILLAR}[，,]\s*{PILLAR}[，,]\s*{PILLAR}[，,]\s*{PILLAR}[。，,]?\s*(.*)$")
LOOKS_LIKE = re.compile(rf"^\[例盘\]\s*[{STEM_ANY}][{BRANCH_ANY}]?[，,]")
PAGE = re.compile(r"<!-- p(\d+) -->")

MONTHS = {"正": "寅", "一": "寅", "二": "卯", "三": "辰", "四": "巳", "五": "午", "六": "未",
          "七": "申", "八": "酉", "九": "戌", "十": "亥", "十一": "子", "冬": "子", "十二": "丑", "腊": "丑"}
MONTHS_NUM = {"正": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
              "十一": 11, "冬": 11, "十二": 12, "腊": 12}
SEASONS = {"三春": "寅卯辰", "三夏": "巳午未", "三秋": "申酉戌", "三冬": "亥子丑"}
# 年号 → 元年公历。明清与民国，够书里用。
ERAS = {"万历": 1573, "天启": 1621, "崇祯": 1628, "顺治": 1644, "康熙": 1662, "雍正": 1723, "乾隆": 1736,
        "嘉庆": 1796, "道光": 1821, "咸丰": 1851, "同治": 1862, "光绪": 1875, "宣统": 1909, "民国": 1912}
NUM = {"元": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
       "廿": 20, "卅": 30, "两": 2}
DATE = re.compile(r"(?:明|清)?(" + "|".join(ERAS) + r")([元一二三四五六七八九十廿卅]+)年(闰)?"
                  r"(十一|十二|正|冬|腊|[一二三四五六七八九十])月"
                  r"(初|廿|卅|二十|三十|十)?([一二三四五六七八九十])?日?([子丑寅卯辰巳午未申酉戌亥])时")


def cn_num(s: str) -> int:
    """「十六」「廿三」「三十」「元」→ 整数。"""
    if s == "元":
        return 1
    total = 0
    for ch in s:
        v = NUM[ch]
        if ch == "十":
            total = (total or 1) * 10
        elif ch in ("廿", "卅"):
            total = v
        else:
            total += v
    return total


def parse_date(s: str) -> dict | None:
    m = DATE.search(s)
    if not m:
        return None
    era, yr, leap, mon, day_hi, day_lo, hour = m.groups()
    year = ERAS[era] + cn_num(yr) - 1
    month = MONTHS_NUM[mon]
    if day_hi is None and day_lo is None:
        return None
    base = {"初": 0, "廿": 20, "二十": 20, "卅": 30, "三十": 30, "十": 10, None: 0}[day_hi]
    day = base + (cn_num(day_lo) if day_lo else 0)
    if day == 0:
        return None
    return {"year": year, "month": month, "day": day, "leap": bool(leap), "hourBranch": hour, "era": f"{era}{yr}年"}


def section_of(title: str) -> tuple[str | None, str]:
    """标题 → 单月支（正月丁火 → 寅），季论给三支，卷名等给 None。"""
    m = re.match(r"^(十一|十二|正|冬|腊|[一二三四五六七八九十])月", title)
    if m:
        return MONTHS[m.group(1)], title
    for k, v in SEASONS.items():
        if title.startswith(k):
            return v, title
    return None, title


def normalize_pillars(groups: list[str]) -> tuple[dict, list[str]]:
    fixed = []
    out = {}
    for i, key in enumerate(("year", "month", "day", "hour")):
        s, b = groups[2 * i], groups[2 * i + 1]
        if s not in STEMS:
            fixed.append(f"{s}→{STEM_FIX[s]}")
            s = STEM_FIX[s]
        if b not in BRANCHES:
            fixed.append(f"{b}→{BRANCH_FIX[b]}")
            b = BRANCH_FIX[b]
        out[key] = s + b
    return out, fixed


def extract_volume(dm: str) -> tuple[list[dict], list[str]]:
    lines = (TEXT / f"{dm}.md").read_text(encoding="utf-8").splitlines()
    cases, problems = [], []
    page = None
    section, section_title = None, ""
    cur: dict | None = None
    seq = 0
    for ln, line in enumerate(lines, 1):
        pm = PAGE.search(line)
        if pm:
            page = int(pm.group(1))
            continue
        if line.startswith("[标题]"):
            section, section_title = section_of(line[4:].strip())
            cur = None
            continue
        if not line.startswith("[例盘]"):
            cur = None
            continue
        m = LINE.match(line)
        if m:
            pillars, fixed = normalize_pillars(list(m.groups()[:8]))
            seq += 1
            cur = {"id": f"{dm}-{seq:03d}", "dayMaster": dm, "section": section, "sectionTitle": section_title,
                   "page": page, "line": ln, "pillars": pillars, "raw": line[4:].strip(), "ocrFixed": fixed,
                   "judgment": [], "note": [], "name": None, "date": None, "lunar": None}
            rest = m.group(9).strip()
            if rest:
                cur["judgment"].append(rest)
            cases.append(cur)
            continue
        if LOOKS_LIKE.match(line):
            problems.append(f"{dm}.md:{ln} 四柱行归一后仍不成四柱：{line[4:].strip()[:40]}")
            cur = None
            continue
        if cur is None:
            continue
        body = line[4:].strip()
        if body.startswith("按："):
            cur["note"].append(body)
            continue
        if body.startswith("以上"):
            continue
        d = parse_date(body)
        if d:
            cur["date"] = body
            cur["lunar"] = d
            continue
        nm = re.match(r"^(\S{2,7}?)命[，,。]", body)
        if nm and cur["name"] is None:
            cur["name"] = nm.group(1)
        cur["judgment"].append(body)
    # 后处理：日主、月支、时支自检
    for c in cases:
        flags = []
        if c["pillars"]["day"][0] != dm:
            flags.append(f"日干{c['pillars']['day'][0]}≠卷{dm}")
        if c["section"] and c["pillars"]["month"][1] not in c["section"]:
            flags.append(f"月支{c['pillars']['month'][1]}不在标题{c['sectionTitle']}")
        if c["lunar"] and c["lunar"]["hourBranch"] != c["pillars"]["hour"][1]:
            flags.append(f"时支{c['pillars']['hour'][1]}≠纪年行{c['lunar']['hourBranch']}时")
        c["flags"] = flags
    return cases, problems


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    all_cases, all_problems = [], []
    for dm in STEMS:
        cases, problems = extract_volume(dm)
        all_cases.extend(cases)
        all_problems.extend(problems)
    n = len(all_cases)
    n_date = sum(1 for c in all_cases if c["lunar"])
    n_fix = sum(1 for c in all_cases if c["ocrFixed"])
    flagged = [c for c in all_cases if c["flags"]]
    per = "、".join(f"{dm} {sum(1 for c in all_cases if c['dayMaster'] == dm)}" for dm in STEMS)
    head = ["# 例盘抽取报告", "",
            f"生成：{date.today().isoformat()}。十卷共 {n} 张例盘入夹具（{per}），其中带纪年 {n_date} 张、四柱有 OCR 归一 {n_fix} 张；"
            f"归一后仍不成四柱、未入夹具 {len(all_problems)} 行；自检有疑 {len(flagged)} 张（日干与卷不符、月支不在所属标题、时支与纪年行不符）。",
            "", "夹具：`scripts/bazi_core/tests/fixtures/qiongtong_lipan.json`，来源校对本 `source/text/{日主}.md`（gitignore）。", "",
            "## 未入夹具", ""] + [f"- {p}" for p in all_problems] + ["", "## 自检有疑（已入夹具，带 flags）", ""]
    for c in flagged:
        head.append(f"- {c['id']} p{c['page']} {c['raw'][:24]} ：{'；'.join(c['flags'])}")
    print("\n".join(head))
    if not a.check:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema": "qiongtong-lipan/1", "generated": date.today().isoformat(),
                   "source": "《穷通宝鉴评注》徐乐吾评注本例盘，校对本 source/text/{日主}.md，scripts/extract_lipan.py 抽取",
                   "cases": all_cases}
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        REPORT.write_text("\n".join(head) + "\n", encoding="utf-8")
        print(f"\n→ {OUT}\n→ {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
