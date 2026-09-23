#!/usr/bin/env python3
"""从 bazi_core/tables/shensha_tags.json 生成人读的规则表 references/神煞_叙事标签.md。

    python scripts/build_shensha_tags_md.py

JSON 是唯一来源（tag 自起草，classic 逐字取自神煞卡的位置变体），md 只是投影，改表改 JSON 再重生成。
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "scripts" / "bazi_core" / "tables" / "shensha_tags.json"
OUT = ROOT / "references" / "神煞_叙事标签.md"


def main() -> int:
    t = json.loads(TABLE.read_text(encoding="utf-8"))
    n = sum(len(e["variants"]) for e in t["entries"])
    lines = ["# 神煞叙事标签表", "",
             f"生成：{date.today().isoformat()}，来源 `scripts/bazi_core/tables/shensha_tags.json`（{len(t['entries'])} 种神煞、{n} 个变体）。",
             "", "用途：人物档案「特色标签」的取材。命盘层由 `shensha_tags.for_chart` 按落柱、十二宫、同柱神煞、旬空、六冲、十神、性别、重数求值，"
             "命中的变体带编号进人物档案作溯源。「古籍判词」逐字取自校核卡的位置变体栏（出处随之）；「叙事标签」是自起草的译法，不是古籍原意，"
             "可反用、可弱化，作者是天。没有古籍判词的条目出自 DESIGN 附录 B。", "",
             "条件写法：" + "；".join(f"{k} = {v}" for k, v in t["conditionVocabulary"].items()), ""]
    for e in t["entries"]:
        lines += [f"## {e['shensha']}", "", f"核心用法：{e['core']}", "",
                  "| 编号 | 条件 | 叙事标签 | 古籍判词 | 出处 |", "|---|---|---|---|---|"]
        for v in e["variants"]:
            cond = "，".join(f"{k}={'、'.join(x) if isinstance(x, list) else x}" for k, x in v["when"].items())
            lines.append(f"| {v['id']} | {cond} | {v['tag']} | {v['classic'] or ''} | {v['source']} |")
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(t['entries'])} 种 {n} 个变体 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
