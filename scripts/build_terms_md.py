#!/usr/bin/env python3
"""从 bazi_core/tables/terms.json 生成人读的 references/去术语词表.md。JSON 是唯一来源，md 只是投影。

    python scripts/build_terms_md.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "scripts" / "bazi_core" / "tables" / "terms.json"
OUT = ROOT / "references" / "去术语词表.md"


def main() -> int:
    t = json.loads(TABLE.read_text(encoding="utf-8"))
    n = sum(len(g["terms"]) for g in t["groups"])
    lines = ["# 去术语词表", "",
             f"生成：{date.today().isoformat()}，来源 `scripts/bazi_core/tables/terms.json`（{len(t['groups'])} 组 {n} 词）。检查器 `scripts/check-terms.js`，对 `人物/` 与导出本要求 error 级零命中，对 `命盘/` 用 `--expect-hits` 反向自检。", "",
             t["source"], "",
             "| 级别 | 含义 |", "|---|---|"] + [f"| {k} | {v} |" for k, v in t["levels"].items()] + [""]
    for g in t["groups"]:
        lines += [f"## {g['name']}（{g['level']}）", ""]
        if g.get("note"):
            lines += [g["note"], ""]
        lines += ["、".join(g["terms"]), ""]
    lines += ["## 放行", "", "历史题材的纪年干支、意象里的桃花、对白里的算命先生，用 `--allow 词` 或 `--allowlist 文件` 逐词放行，放行记录在项目里，不改词表。", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(t['groups'])} 组 {n} 词 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
