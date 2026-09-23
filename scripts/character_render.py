#!/usr/bin/env python3
"""人物档案 JSON → markdown。JSON 是主产物（人物/{角色}.json），md 是投影。

    python scripts/character_render.py 人物/沈砚.json                 → 作者本 人物/沈砚.md（每条特质带溯源编号）
    python scripts/character_render.py 人物/沈砚.json --reader        → 读者本 人物/沈砚.读者本.md（剥掉编号与作者本段落）
    python scripts/character_render.py 人物/沈砚.json --out 路径

JSON 形态（bazi-character/v1）：
    {"schema": "bazi-character/v1", "name": "沈砚", "chart": "命盘/沈砚.json", "profile": "webnovel|literary",
     "summary": "一句话人物真相",
     "sections": [{"title": "性格表里", "traits": [{"text": "……", "sources": ["T-月干-正印", "S-中和"], "note": "可选"}]}, ...]}
必备段落十二个（DESIGN 3.2），可选段落按 profile（DESIGN 3.4）；字段在场、值可以待补充（traits 为空列表）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REQUIRED = ["性格表里", "童年事件", "谎言", "秘密", "需要与想要", "抵抗线", "亲密关系模式", "说话方式",
            "能力与漏洞", "意象系统", "他人眼中的他", "年表与两难"]
AUTHOR_ONLY = {"年表与两难": False}  # 目前没有只给作者看的段落；溯源编号本身是作者本才有的东西


def render(doc: dict, reader: bool) -> str:
    lines = [f"# {doc['name']}", ""]
    if not reader:
        lines += [f"人物档案（作者本）· 写法轮廓 {doc.get('profile', 'webnovel')} · 命盘 `{doc.get('chart', '')}`", ""]
    if doc.get("summary"):
        lines += [doc["summary"], ""]
    for sec in doc["sections"]:
        lines += [f"## {sec['title']}", ""]
        traits = sec.get("traits", [])
        if not traits:
            lines += ["（待补充）", ""]
            continue
        for t in traits:
            text = t.get("text") or "（待补充）"
            if reader:
                lines.append(f"- {text}")
            else:
                src = "、".join(t.get("sources", []))
                note = f"（{t['note']}）" if t.get("note") else ""
                lines.append(f"- {text}{note} ｜溯源 {src}" if src else f"- {text}{note}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("doc")
    ap.add_argument("--reader", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    src = Path(a.doc)
    doc = json.loads(src.read_text(encoding="utf-8"))
    out = Path(a.out) if a.out else src.with_name(src.stem + (".读者本.md" if a.reader else ".md"))
    out.write_text(render(doc, a.reader), encoding="utf-8")
    print("→", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
