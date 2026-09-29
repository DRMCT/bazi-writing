#!/usr/bin/env python3
"""把 tables/suiyun_events.json（岁运事件类型表）投影成 references/岁运事件类型.md，并核对 anchors 指向的卡号存在。

机制名须与 bazi_core/timeline.py 输出的机制一致，领域名须与 timeline.DOMAINS 一致，不一致时报错退出。
用法：python scripts/build_suiyun_md.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from bazi_core.timeline import DOMAINS  # noqa: E402

TABLE = ROOT / "scripts" / "bazi_core" / "tables" / "suiyun_events.json"
DOC = ROOT / "references" / "岁运事件类型.md"
MECH_IN_CODE = ("冲提纲", "冲日支", "冲年支", "冲时支", "天克地冲", "伏吟", "刑", "害", "合日支",
                "岁运并临", "岁运相冲", "换运", "合绊用神", "合化为用", "忌神透干", "用神到位")


def card_ids() -> set[str]:
    ids = set()
    for f in list((ROOT / "references" / "校核").glob("滴天髓_*.md")) + list((ROOT / "references" / "校核").glob("三命通会_*.md")):
        ids.update(re.findall(r"(?m)^### (\S+-\S+)", f.read_text(encoding="utf-8")))
    return ids


def main() -> int:
    t = json.loads(TABLE.read_text(encoding="utf-8"))
    mech_names = [m["name"] for m in t["mechanisms"]]
    if set(mech_names) != set(MECH_IN_CODE):
        print("机制名与 timeline.py 不一致：", set(mech_names) ^ set(MECH_IN_CODE)); return 1
    dom_names = [d["name"] for d in t["domains"]]
    if dom_names != list(DOMAINS):
        print("领域名与 timeline.DOMAINS 不一致"); return 1
    ids = card_ids()
    missing = []
    for row in t["mechanisms"] + t["domains"]:
        for a in row["anchors"]:
            if a not in ids:
                missing.append((row["name"], a))
    for c in t["cells"]:
        if c["mechanism"] not in mech_names or c["domain"] not in dom_names or any(s not in dom_names for s in c["sub"]):
            print("cell 名字错：", c); return 1
    lines = ["# 岁运事件类型表", "",
             "机制说怎么发生，领域说赌注是什么（DESIGN-命盘层 第 5 节）。机制名与年表脚本（bazi_core/timeline.py）输出的一致，领域名与其九领域一致；"
             "年表每年给出的机制与领域编号（L-…-机制、L-…-域-领域）对着本表读。形态、赌注、两难模板三栏是自起草的叙事映射；"
             "锚点指向 references/校核/滴天髓_*.md 的卡号，只作古籍旁证。源文件 scripts/bazi_core/tables/suiyun_events.json，由 build_suiyun_md.py 生成本文。", "",
             "## 机制轴", "", "| 机制 | 怎么算的 | 形态（自起草） | 节奏 | 古籍锚点 |", "|---|---|---|---|---|"]
    for m in t["mechanisms"]:
        lines.append(f"| {m['name']} | {m['what']} | {m['form']} | {m['tempo']} | {'、'.join(m['anchors']) or '无'} |")
    lines += ["", "## 领域轴", "", "| 领域 | 赌注 | 常见事件类型（自起草） | 古籍锚点 |", "|---|---|---|---|"]
    for d in t["domains"]:
        lines.append(f"| {d['name']} | {d['stake']} | {'、'.join(d['events'])} | {'、'.join(d['anchors']) or '无'} |")
    lines += ["", "## 两难怎么合成", "", t["compose"], "", "## 两难给谁", "", t["use"], "",
              "## 两难模板精选（机制 × 主领域）", "", "| 机制 | 主领域 | 形态 | 两头（只写方向，押什么按处境落） | 常配的副领域 |", "|---|---|---|---|---|"]
    for c in t["cells"]:
        lines.append(f"| {c['mechanism']} | {c['domain']} | {c['shape']} | {c['sides'][0]} ｜ {c['sides'][1]} | {'、'.join(c['sub'])} |")
    lines += ["", "未列的格按上面的合成规则临场写；写进人物档案时引年表的 L- 编号，本表不产生编号。", ""]
    DOC.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"机制 {len(mech_names)}，领域 {len(dom_names)}，两难模板 {len(t['cells'])}，锚点缺卡 {len(missing)}")
    for name, a in missing:
        print("  缺卡", name, a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
