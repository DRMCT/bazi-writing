#!/usr/bin/env python3
"""把 narrative-table/v1 形态的机器表投影成 references/*.md，并核对 anchors 指向的校核卡号存在。

表：tables/shishen_traits.json → references/十神性格.md
    tables/wuxing_body.json   → references/五行体质气质.md
    tables/liuqin_childhood.json → references/六亲宫位与童年.md
    tables/rizhi_intimacy.json → references/日支亲密关系.md
    tables/lies.json          → references/谎言候选.md
    tables/arc_match.json     → references/弧光匹配.md
    tables/imagery.json       → references/意象系统.md
    tables/stage_overlay.json → references/阶段状态.md
    tables/yunqi_body.json    → references/五运六气体质.md
    tables/yunqi_year.json    → references/五运六气年景.md
    tables/response_tendency.json → references/回应倾向.md
两种形态：单表 {format, title, intro, columns, rows, modifiers?}；多分表 {format, title, intro, sections:[{key, title, columns, rows}]}。
rows 里列表值用"、"连接，anchors 为空写"无"。锚点对 references/校核/*.md 里所有 "### 卡号" 标题核对（滴天髓、神煞、格局、刑冲合害、长生纳音各卡）。
用法：python scripts/build_narrative_md.py [--check]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
TABLES = ROOT / "scripts" / "bazi_core" / "tables"
REFS = ROOT / "references"
TARGETS = {
    "shishen_traits.json": "十神性格.md",
    "wuxing_body.json": "五行体质气质.md",
    "liuqin_childhood.json": "六亲宫位与童年.md",
    "rizhi_intimacy.json": "日支亲密关系.md",
    "lies.json": "谎言候选.md",
    "arc_match.json": "弧光匹配.md",
    "imagery.json": "意象系统.md",
    "stage_overlay.json": "阶段状态.md",
    "yunqi_body.json": "五运六气体质.md",
    "yunqi_year.json": "五运六气年景.md",
    "response_tendency.json": "回应倾向.md",
}


def card_ids() -> set[str]:
    ids = set()
    for f in (ROOT / "references" / "校核").glob("*.md"):
        ids.update(re.findall(r"(?m)^### (\S+-\S+)", f.read_text(encoding="utf-8")))
    return ids


def cell(v) -> str:
    if isinstance(v, list):
        return "、".join(str(x) for x in v) if v else "无"
    return str(v).replace("|", "｜")


def table_rows(t: dict) -> list[dict]:
    if "sections" in t:
        return [r for s in t["sections"] for r in s["rows"]]
    return t["rows"] + t.get("modifiers", [])


def render_table(columns: list[dict], rows: list[dict]) -> list[str]:
    lines = ["| " + " | ".join(c["label"] for c in columns) + " |", "|" + "---|" * len(columns)]
    for r in rows:
        lines.append("| " + " | ".join(cell(r.get(c["key"], "")) for c in columns) + " |")
    return lines


def main(check_only: bool) -> int:
    ids = card_ids()
    bad = 0
    for src, dst in TARGETS.items():
        path = TABLES / src
        if not path.exists():
            print("缺表", src); continue
        t = json.loads(path.read_text(encoding="utf-8"))
        assert t.get("format") == "narrative-table/v1", src
        rows = table_rows(t)
        missing = [(r.get(next(iter(r))), a) for r in rows for a in r.get("anchors", []) if a not in ids]
        bad += len(missing)
        lines = [f"# {t['title']}", "", t["intro"], ""]
        if "sections" in t:
            for s in t["sections"]:
                lines += [f"## {s['title']}", ""] + render_table(s["columns"], s["rows"]) + [""]
        else:
            lines += render_table(t["columns"], t["rows"])
            if t.get("modifiers"):
                keys = [k for k in t["modifiers"][0].keys()]
                lines += ["", "## 修正项", ""] + render_table([{"key": k, "label": k} for k in keys], t["modifiers"])
        lines += ["", f"源文件 scripts/bazi_core/tables/{src}，由 build_narrative_md.py 生成本文。", ""]
        if not check_only:
            (REFS / dst).write_text("\n".join(lines), encoding="utf-8", newline="\n")
        n_mod = len(t.get("modifiers", [])) if "sections" not in t else 0
        print(f"{src}: {len(rows)} 行" + (f"（修正项 {n_mod}）" if n_mod else "") + f"，锚点缺卡 {len(missing)}" + ("" if check_only else f" → {dst}"))
        for name, a in missing:
            print("  缺卡", name, a)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main("--check" in sys.argv[1:]))
