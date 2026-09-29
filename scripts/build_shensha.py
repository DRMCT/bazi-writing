#!/usr/bin/env python3
"""从神煞校核卡（references/校核/神煞_*.md）的「采用规则」生成机器表 bazi_core/tables/shensha.json。

    python scripts/build_shensha.py            → 写 tables/shensha.json 与 references/校核/神煞_抽取报告.md
    python scripts/build_shensha.py --check    → 只打印报告

采用规则的写法（子代理任务_神煞.md 定）：一行，先查法类型再表，表项以「；」分隔，键值以「→」连接，多值以「、」分隔，
括号内是标签（如 亥子丑→寅（孤辰）、戌（寡宿））。查法类型：
    日干查地支 | 三合局查地支 | 月支查干支 | 日柱 | 日柱旬空 | 年支三会查地支
三合局查地支另有一句「原文取年支 / 日支 / 未明言」，解析成 basis。
每条带 source 指向卡号，没有卡的条目不允许进表（DESIGN-命盘层 3.2）。
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
CARDS = ROOT / "references" / "校核"
OUT = ROOT / "scripts" / "bazi_core" / "tables" / "shensha.json"
REPORT = CARDS / "神煞_抽取报告.md"

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
METHODS = {
    "日干查地支": ("dayStem", "branch"),
    "三合局查地支": ("trioOf", "branch"),
    "月支查干支": ("monthBranch", "stemOrBranch"),
    "日柱": ("dayPillar", None),
    "日柱旬空": ("xun", "branch"),
    "年支三会查地支": ("yearBranchGroup", "branch"),
}
GZ = re.compile(rf"^[{STEMS}][{BRANCHES}]$")


# 裁决时保留的另说表，进 alternates 字段，运行时不用，只供切换与对照（卡上裁决栏有理由）
ALTERNATES: dict[str, list[dict]] = {
    "文昌": [{"source": "通行本文昌（食神禄位），初稿 yueyuan WEN_CHANG；主会话审 2026-09-22 留作另说",
             "table": {"甲": ["巳"], "乙": ["午"], "丙": ["申"], "丁": ["酉"], "戊": ["申"], "己": ["酉"],
                       "庚": ["亥"], "辛": ["子"], "壬": ["寅"], "癸": ["卯"]}}],
    "红艳": [{"source": "《神峰通考》红艳杀歌诀，与初稿口诀同源；主会话裁 2026-09-22 从三命通会，此表留作另说",
             "table": {"乙": ["申"], "戊": ["辰"], "壬": ["子"]}}],
}


# 日柱类查哪些柱：默认只查日柱；阴差阳错原文"月日时两重或三重犯之，极重"，主会话审 2026-09-22 定为月日时都查
SCOPES: dict[str, list[str]] = {"阴差阳错": ["month", "day", "hour"]}


def split_items(s: str) -> list[str]:
    return [x.strip() for x in re.split(r"[；;]", s) if x.strip()]


def parse_value(v: str) -> tuple[str, str | None]:
    """「戌（寡宿）」→ ("戌", "寡宿")；「原文未列」→ ("", None)。"""
    v = v.strip()
    m = re.match(r"^([^（(]+)[（(]([^）)]+)[）)]$", v)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return v, None


def parse_rule(rule: str) -> dict:
    out: dict = {"method": None, "table": {}, "list": [], "basis": None, "notes": [], "unlisted": []}
    # 只取第一行：另说、说明都写在后面的行。括号里超过四个字的是给人读的说明，不是格子标签（标签如「孤辰」「寡宿」）
    body = rule.strip().split("\n")[0]
    body = re.sub(r"[（(]([^（）()]*)[）)]", lambda m: m.group(0) if len(m.group(1)) <= 4 else "", body).strip()
    m = re.match(r"^(日干查地支|三合局查地支|月支查干支|日柱旬空|日柱|年支三会查地支)\s*[：:]\s*(.*)$", body, re.S)
    if not m:
        out["notes"].append("查法类型不认得：" + body[:40])
        return out
    method, rest = m.group(1), m.group(2)
    out["method"] = method
    # 三合局的年支/日支说明
    bm = re.search(r"原文取?支?[：:]?\s*(年支或日支|年支与日支|年支|日支|未明言)", rest)
    if method == "三合局查地支":
        out["basis"] = {"年支": "year", "日支": "day", "年支或日支": "both", "年支与日支": "both", "未明言": "unspecified"}.get(bm.group(1), "unspecified") if bm else "unspecified"
    # 去掉表之后的说明句（第一个句号之后）
    table_part = re.split(r"[。]", rest, maxsplit=1)[0]
    if method == "日柱":
        for v in re.split(r"[、，,]", table_part):
            v = v.strip()
            if GZ.match(v):
                out["list"].append(v)
            elif v:
                out["notes"].append("日柱项不认得：" + v)
        return out
    for item in split_items(table_part):
        if "→" not in item:
            out["notes"].append("无箭头：" + item)
            continue
        key, vals = [x.strip() for x in item.split("→", 1)]
        key = key.replace("旬", "").strip()
        entries = []
        for v in re.split(r"[、,，]", vals):
            val, label = parse_value(v)
            if not val or "未列" in val:
                out["unlisted"].append(key)
                continue
            entries.append({"value": val, "label": label} if label else val)
        out["table"][key] = entries
    return out


def build() -> tuple[dict, list[str]]:
    entries, report = [], []
    for f in sorted(CARDS.glob("神煞_*.md")):
        if f.name.endswith("抽取报告.md"):
            continue
        for c in parse_cards(f.read_text(encoding="utf-8")):
            name = c["id"].split("-", 1)[1]
            fields = c["fields"]
            rule = fields.get("采用规则", "").strip()
            parsed = parse_rule(rule)
            e = {"name": name, "source": c["id"], "file": f.name, "status": fields.get("状态", "").strip(),
                 "method": parsed["method"], "methodKey": METHODS.get(parsed["method"], (None, None))[0],
                 "table": parsed["table"], "list": parsed["list"], "basis": parsed["basis"],
                 "unlisted": parsed["unlisted"], "alternates": ALTERNATES.get(name, []),
                 "scope": SCOPES.get(name, ["day"]) if parsed["method"] == "日柱" else None, "rule": rule}
            entries.append(e)
            if parsed["notes"] or not parsed["method"]:
                report.append(f"- **{c['id']}**（{f.name}）：" + "；".join(parsed["notes"] or ["无法解析"]) + f" ｜ 原文：{rule[:80]}")
            elif parsed["unlisted"]:
                report.append(f"- {c['id']}：原文未列 {'、'.join(parsed['unlisted'])}")
    return {"schema": "shensha/1", "generated": date.today().isoformat(),
            "source": "references/校核/神煞_{组}.md 采用规则字段；《四库版足本三命通会》校核卡", "entries": entries}, report


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    table, report = build()
    n = len(table["entries"])
    by = {}
    for e in table["entries"]:
        by[e["status"]] = by.get(e["status"], 0) + 1
    head = ["# 神煞机器表抽取报告", "",
            f"生成：{date.today().isoformat()}，{n} 条；状态分布 {by}。", "",
            "下面是解析器吃不动或原文未列全的条目，人核。", ""]
    print("\n".join(head + report))
    if not a.check:
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
        REPORT.write_text("\n".join(head + report) + "\n", encoding="utf-8")
        print(f"\n→ {OUT}\n→ {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
