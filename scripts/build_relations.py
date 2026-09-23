#!/usr/bin/env python3
"""从刑冲合害校核卡（references/校核/刑冲合害.md）的「采用规则」生成机器表 bazi_core/tables/relations.json。

    python scripts/build_relations.py            → 写 tables/relations.json
    python scripts/build_relations.py --check    → 只打印表与差异，不写

采用规则的写法（卡文件体例节定）：一行，`{类型}：{项}；{项}……`，项写 `AB`（无向配对）或 `A→B（标签）`（有向或带所化）。
类型：天干五合 | 六合 | 六冲 | 六害 | 三刑（另有「自刑」段）| 三合 | 三会。
所化写"两存（火、土）"的项 element 为 null、alternates 记两说，报告里点名。每条带 source 指向卡号与卡状态；没有卡的条目不允许进表（DESIGN 7.2）。
生成后与 vendor/yueyuan_relations.py 初稿比对，差异打印出来（应只剩卡上"差异"栏写明的几处）。
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
from check_cards import parse_cards  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CARD = ROOT / "references" / "校核" / "刑冲合害.md"
OUT = ROOT / "scripts" / "bazi_core" / "tables" / "relations.json"
WUXING = set("木火土金水")
ITEM = re.compile(r"^(?P<a>[甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥]+)(?:→(?P<b>[^（）]+?))?(?:（(?P<tag>[^）]+)）)?$")


def parse_rule(rule: str) -> dict[str, list[dict]]:
    """「三刑：寅→巳；……；自刑：辰；午」→ {"三刑": [...], "自刑": [...]}。"""
    out: dict[str, list[dict]] = {}
    section = None
    for piece in rule.strip().splitlines()[0].split("；"):
        piece = piece.strip()
        if "：" in piece:
            section, piece = piece.split("：", 1)
            section = section.strip()
            out.setdefault(section, [])
        m = ITEM.match(piece.strip())
        if not m or section is None:
            raise SystemExit(f"parse fail: {piece!r} in {rule!r}")
        out[section].append({"a": m.group("a"), "b": m.group("b"), "tag": m.group("tag")})
    return out


def build() -> tuple[dict, list[str]]:
    cards = {c["id"]: c for c in parse_cards(CARD.read_text(encoding="utf-8"))}
    notes: list[str] = []

    def src(cid: str) -> dict:
        return {"source": cid, "status": cards[cid]["fields"]["状态"].strip()}

    def elem(v: str | None, cid: str, key: str) -> str | None:
        if v in WUXING:
            return v
        notes.append(f"{cid} {key}：所化「{v}」未定，表中留空")
        return None

    def alternates(i: dict) -> list[str]:
        """「两存（火、土）」→ ["火", "土"]；其余空。"""
        if i["b"] == "两存" and i["tag"]:
            return [x for x in i["tag"].split("、") if x in WUXING]
        return []

    table: dict = {"schema": "relations/1", "generated": date.today().isoformat(),
                   "source": "references/校核/刑冲合害.md 采用规则字段；《四库版足本三命通会》卷二校核卡"}

    cid = "刑冲合害-天干五合"
    r = parse_rule(cards[cid]["fields"]["采用规则"])["天干五合"]
    table["stemHe"] = [{"pair": i["a"], "element": elem(i["b"], cid, i["a"]), "name": i["tag"], **src(cid)} for i in r]

    cid = "刑冲合害-六合"
    r = parse_rule(cards[cid]["fields"]["采用规则"])["六合"]
    table["liuHe"] = [{"pair": i["a"], "element": elem(i["b"], cid, i["a"]), "alternates": alternates(i), **src(cid)} for i in r]

    for key, name in (("liuChong", "六冲"), ("liuHai", "六害")):
        cid = f"刑冲合害-{name}"
        r = parse_rule(cards[cid]["fields"]["采用规则"])[name]
        table[key] = [{"pair": i["a"], **src(cid)} for i in r]

    cid = "刑冲合害-三刑"
    r = parse_rule(cards[cid]["fields"]["采用规则"])
    directed = []
    tag = None
    for i in reversed(r["三刑"]):          # 标签写在每组最后一项，倒着补给前两项
        tag = i["tag"] or tag
        directed.append({"from": i["a"], "to": i["b"], "kind": tag, **src(cid)})
    table["sanXing"] = {"directed": list(reversed(directed)),
                        "self": [{"branch": i["a"], **src(cid)} for i in r["自刑"]]}

    for key, name in (("sanHe", "三合"), ("sanHui", "三会")):
        cid = f"刑冲合害-{name}"
        r = parse_rule(cards[cid]["fields"]["采用规则"])[name]
        table[key] = [{"branches": i["a"], "element": elem(i["b"], cid, i["a"]), "note": i["tag"], **src(cid)} for i in r]
    return table, notes


def diff_vendor(table: dict) -> list[str]:
    from bazi_core.vendor import yueyuan_relations as Y  # noqa: E402
    out = []
    for e in table["liuHe"]:
        if Y.LIU_HE.get(e["pair"][0]) != e["pair"][1]:
            out.append(f"六合 {e['pair']} 初稿无")
    for e in table["liuChong"]:
        if Y.LIU_CHONG.get(e["pair"][0]) != e["pair"][1]:
            out.append(f"六冲 {e['pair']} 初稿无")
    for e in table["liuHai"]:
        if Y.HAI.get(e["pair"][0]) != e["pair"][1]:
            out.append(f"六害 {e['pair']} 初稿无")
    for e in table["sanXing"]["directed"]:
        if e["to"] not in Y.XING.get(e["from"], ()):
            out.append(f"三刑 {e['from']}→{e['to']} 初稿无")
    if {e["branch"] for e in table["sanXing"]["self"]} != set(Y.ZI_XING):
        out.append("自刑与初稿不同")
    for e in table["sanHe"]:
        if Y.SAN_HE.get(e["branches"]) != e["element"]:
            out.append(f"三合 {e['branches']}→{e['element']} 初稿无（{e.get('note') or ''}）")
    for e in table["sanHui"]:
        if Y.SAN_HUI.get(e["branches"]) != e["element"]:
            out.append(f"三会 {e['branches']} 初稿不同")
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    table, notes = build()
    diffs = diff_vendor(table)
    print(f"stemHe {len(table['stemHe'])}，liuHe {len(table['liuHe'])}，liuChong {len(table['liuChong'])}，liuHai {len(table['liuHai'])}，"
          f"sanXing {len(table['sanXing']['directed'])}+{len(table['sanXing']['self'])}，sanHe {len(table['sanHe'])}，sanHui {len(table['sanHui'])}")
    for n in notes:
        print("  留空:", n)
    for d in diffs:
        print("  与初稿差异:", d)
    if not a.check:
        OUT.write_text(json.dumps(table, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
