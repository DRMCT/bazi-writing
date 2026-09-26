#!/usr/bin/env python3
"""开发期工具：从校对本 source/text/子平真诠_人鉴.md 抽《人鉴·命理存验》67 例成夹具 tests/fixtures/ziping_renjian.json。

    python scripts/extract_ziping_renjian.py

每例：id（人鉴-01）、name、page、pillars（年月日时）、dayun（[{age, pillar}]，age 是起运岁）、taiyuan、mingGong（立命宫支）、
comment（林庚白判词，跨页的并成一段）、flags（自检：四柱不合法、大运干支不连续或起运岁不递增）。
校对本的 [解说] 只是占位，不进夹具。报告 references/校核/人鉴_抽取报告.md。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bazi_core.dayun import pillar_name, sexagenary_index  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEXT = ROOT / "source" / "text" / "子平真诠_人鉴.md"
FIXTURE = ROOT / "scripts" / "bazi_core" / "tests" / "fixtures" / "ziping_renjian.json"
REPORT = ROOT / "references" / "校核" / "人鉴_抽取报告.md"

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
LEGAL = {pillar_name(i) for i in range(60)}
RE_PAGE = re.compile(r"<!-- (p\d{3})")
RE_TITLE = re.compile(r"^\[标题\]\s*([一二三四五六七八九十]{1,3})、(\S+)")
RE_DAYUN = re.compile(r"([初十廿卅一二三四五六七八九]{1,3})([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])")
CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn_num(s: str) -> int:
    """一 → 1，十 → 10，十六 → 16，廿一 → 21，卅四 → 34，四四 → 44，六十七 → 67。"""
    n, tens = 0, 0
    if s.startswith("廿"):
        tens, s = 20, s[1:]
    elif s.startswith("卅"):
        tens, s = 30, s[1:]
    elif s.startswith("十"):
        tens, s = 10, s[1:]
    elif len(s) >= 2 and s[1] == "十":
        tens, s = CN[s[0]] * 10, s[2:]
    elif len(s) == 2 and s[0] in CN and s[1] in CN:     # 四四、五三 一类：十位个位并写
        return CN[s[0]] * 10 + CN[s[1]]
    if s:
        n = CN.get(s, 0)
    return tens + n


def age_of(s: str) -> int:
    if s.startswith("初"):
        return cn_num(s[1:]) if s[1:] != "十" else 10
    return cn_num(s)


def parse_lipan(text: str) -> dict:
    parts = [x.strip() for x in text.split("|")]
    pillars = parts[0].split()
    dayun = [{"age": age_of(a), "pillar": gz} for a, gz in RE_DAYUN.findall(parts[1] if len(parts) > 1 else "")]
    tail = parts[2] if len(parts) > 2 else ""
    m1 = re.search(r"胎元([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])", tail)
    m2 = re.search(r"立命([子丑寅卯辰巳午未申酉戌亥])", tail)
    return {"pillars": pillars, "dayun": dayun, "taiyuan": m1.group(1) if m1 else None, "mingGong": m2.group(1) if m2 else None}


def check(c: dict) -> list[str]:
    flags = []
    if len(c["pillars"]) != 4 or any(p not in LEGAL for p in c["pillars"]):
        flags.append("四柱不合法或不齐")
    ages = [d["age"] for d in c["dayun"]]
    if ages and any(b - a != 10 for a, b in zip(ages, ages[1:])):
        flags.append("起运岁不按十年递增")
    idx = [sexagenary_index(d["pillar"]) for d in c["dayun"] if d["pillar"] in LEGAL]
    if len(idx) >= 2:
        steps = {(b - a) % 60 for a, b in zip(idx, idx[1:])}
        if steps not in ({1}, {59}):
            flags.append("大运干支不连续")
        elif len(c["pillars"]) == 4 and c["pillars"][1] in LEGAL:
            m = sexagenary_index(c["pillars"][1])
            if (idx[0] - m) % 60 not in (1, 59):
                flags.append("首步大运不接月柱")
    if not c["dayun"]:
        flags.append("无大运")
    return flags


def main() -> int:
    if not TEXT.exists():
        sys.exit(f"缺校对本 {TEXT}，先 apply_fixes.py 子平真诠_人鉴")
    cases: list[dict] = []
    page = None
    cur: dict | None = None
    for line in TEXT.read_text(encoding="utf-8").splitlines():
        pm = RE_PAGE.search(line)
        if pm:
            page = int(pm.group(1)[1:]); continue
        tm = RE_TITLE.match(line)
        if tm:
            cur = {"id": f"人鉴-{cn_num(tm.group(1)):02d}", "seq": cn_num(tm.group(1)), "name": tm.group(2), "page": page,
                   "pillars": [], "dayun": [], "taiyuan": None, "mingGong": None, "comment": ""}
            cases.append(cur); continue
        if cur is None:
            continue
        if line.startswith("[例盘]"):
            cur.update(parse_lipan(line[4:].strip()))
        elif line.startswith("[判词]"):
            cur["comment"] += line[4:].strip()
    for c in cases:
        c["flags"] = check(c)
    FIXTURE.write_text(json.dumps({"source": "《子平真诠评注》附录《人鉴·命理存验》67 例（林庚白著），校对本 source/text/子平真诠_人鉴.md，印刷页 311–487",
                                   "generated": date.today().isoformat(), "cases": cases}, ensure_ascii=False, indent=1), encoding="utf-8")
    flagged = [c for c in cases if c["flags"]]
    seqs = [c["seq"] for c in cases]
    missing = sorted(set(range(1, 68)) - set(seqs))
    lines = ["# 《人鉴·命理存验》例盘抽取报告", "",
             f"生成：{date.today().isoformat()}。校对本抽出 {len(cases)} 例（应 67），缺号 {missing or '无'}；带大运 {sum(1 for c in cases if c['dayun'])} 例、"
             f"带胎元 {sum(1 for c in cases if c['taiyuan'])} 例、带立命 {sum(1 for c in cases if c['mingGong'])} 例；自检有疑 {len(flagged)} 例。",
             "", f"夹具：`{FIXTURE.relative_to(ROOT)}`。判词是林庚白原判（已过保护期），今人意译与解说不入。", "",
             "## 自检有疑", ""]
    lines += [f"- {c['id']} {c['name']} p{c['page']} {' '.join(c['pillars'])}｜大运 {' '.join(d['pillar'] for d in c['dayun'])}：{'；'.join(c['flags'])}" for c in flagged] or ["- 无"]
    lines += ["", "## 逐例", "", "| 例 | 姓名 | 页 | 四柱 | 起运岁 | 大运 | 胎元 | 立命 | 判词字数 |", "|---|---|---|---|---|---|---|---|---|"]
    lines += [f"| {c['id']} | {c['name']} | {c['page']} | {' '.join(c['pillars'])} | {c['dayun'][0]['age'] if c['dayun'] else ''} | "
              f"{' '.join(d['pillar'] for d in c['dayun'])} | {c['taiyuan'] or ''} | {c['mingGong'] or ''} | {len(c['comment'])} |" for c in cases]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:3]))
    print(f"→ {FIXTURE}\n→ {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
