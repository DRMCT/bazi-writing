#!/usr/bin/env python3
"""从十二长生纳音校核卡（references/校核/十二长生纳音.md）的「采用规则」生成机器表
bazi_core/tables/changsheng.json（十干乘十二支的十二宫）与 bazi_core/tables/nayin.json（六十甲子纳音）。

    python scripts/build_changsheng.py            → 写两张表
    python scripts/build_changsheng.py --check    → 只打印，不写

采用规则写法：
    长生位：甲→亥；乙→午；……；阳干顺行，阴干逆行      十二宫由长生位起，阳干顺数、阴干逆数
    十二宫：长生；沐浴；……；养                          宫名与次序
    纳音：甲子乙丑→海中金；……                            三十对，每对两柱同一纳音，五行取名末字
每条带 source 指向卡号与卡状态。装了 tyme4py 时顺手与其比对（开发期交叉核对，运行期不依赖）。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_cards import parse_cards  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CARD = ROOT / "references" / "校核" / "十二长生纳音.md"
TABLES = ROOT / "scripts" / "bazi_core" / "tables"
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def items(rule: str) -> tuple[str, list[str]]:
    head, _, body = rule.strip().splitlines()[0].partition("：")
    return head.strip(), [p.strip() for p in body.split("；") if p.strip()]


def build() -> tuple[dict, dict, list[str]]:
    cards = {c["id"]: c for c in parse_cards(CARD.read_text(encoding="utf-8"))}
    notes: list[str] = []

    cid = "长生-十二宫序"
    _, stages = items(cards[cid]["fields"]["采用规则"])
    assert len(stages) == 12, stages

    cid_pos = "长生-十干长生位"
    _, parts = items(cards[cid_pos]["fields"]["采用规则"])
    birth = {}
    for p in parts:
        if "→" in p:
            a, b = p.split("→")
            birth[a] = b
    assert set(birth) == set(STEMS), birth
    table = {}
    for si, s in enumerate(STEMS):
        step = 1 if si % 2 == 0 else -1
        start = BRANCHES.index(birth[s])
        table[s] = {BRANCHES[(start + step * k) % 12]: stages[k] for k in range(12)}
    changsheng = {"schema": "changsheng/1", "generated": date.today().isoformat(),
                  "source": "references/校核/十二长生纳音.md 采用规则字段；《四库版足本三命通会》卷二校核卡",
                  "stages": stages, "birthBranch": birth, "rule": "阳干顺行，阴干逆行",
                  "table": table,
                  "cards": {cid_pos: cards[cid_pos]["fields"]["状态"].strip(), cid: cards[cid]["fields"]["状态"].strip()}}

    cid = "纳音-六十甲子"
    _, pairs = items(cards[cid]["fields"]["采用规则"])
    entries = {}
    for p in pairs:
        gz, name = p.split("→")
        assert len(gz) == 4 and name[-1] in "金木水火土", p
        for pillar in (gz[:2], gz[2:]):
            entries[pillar] = {"name": name, "element": name[-1]}
    assert len(entries) == 60, len(entries)
    nayin = {"schema": "nayin/1", "generated": date.today().isoformat(),
             "source": "references/校核/十二长生纳音.md 采用规则字段；《四库版足本三命通会》卷一释六十甲子小标题",
             "card": cid, "status": cards[cid]["fields"]["状态"].strip(), "entries": entries}

    try:
        from tyme4py.sixtycycle import EarthBranch, HeavenStem, SixtyCycle
    except ImportError:
        notes.append("tyme4py 未装，跳过交叉核对")
        return changsheng, nayin, notes
    for s in STEMS:
        for b in BRANCHES:
            t = HeavenStem.from_name(s).get_terrain(EarthBranch.from_name(b)).get_name()
            if t != table[s][b]:
                notes.append(f"十二宫 {s}{b}：表 {table[s][b]}，tyme4py {t}")
    for i in range(60):
        sc = SixtyCycle.from_index(i)
        n, t = sc.get_name(), sc.get_sound()
        if t.get_name()[-1] != entries[n]["element"]:
            notes.append(f"纳音 {n}：表 {entries[n]['name']}，tyme4py {t.get_name()}")
        elif t.get_name() != entries[n]["name"]:
            notes.append(f"纳音 {n} 名目异写：表 {entries[n]['name']}，tyme4py {t.get_name()}")
    return changsheng, nayin, notes


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    cs, ny, notes = build()
    print(f"十二宫 {len(cs['table'])} 干 × 12 支，纳音 {len(ny['entries'])} 条")
    for n in notes:
        print("  ", n)
    if not a.check:
        (TABLES / "changsheng.json").write_text(json.dumps(cs, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        (TABLES / "nayin.json").write_text(json.dumps(ny, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("wrote", TABLES / "changsheng.json", TABLES / "nayin.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
