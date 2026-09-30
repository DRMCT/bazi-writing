#!/usr/bin/env python3
"""戏用页 JSON → markdown（DESIGN-戏剧层 5）。JSON 是主产物（人物/{角色}.戏用页.json），md 是投影。

    python scripts/drama_render.py 人物/甲.戏用页.json            → 人物/甲.戏用页.md（写手与排戏的人读，不带编号）
    python scripts/drama_render.py 人物/甲.戏用页.json --author   → 人物/甲.戏用页.作者本.md（每行带来历与编号）
    python scripts/drama_render.py 人物/甲.戏用页.json --out 路径

十问的键一律写"他"，渲染时按 pronoun 换成她或它。第六问按线分组，每根线下面依拍子的次序排；破带 by 时标出谁来破。
belief 为信条的页，第四问的标题写成"他信的那句话"。附问有答的才渲染，排在十问后面。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ASKS = ("他要什么", "谁挡着", "他怎么去要", "他信的那句假话", "他真正缺的", "碰哪里会疼", "他瞒着什么", "他怎么说话", "别人拿他当什么", "他从哪儿走到哪儿")
BEATS = ("碰线", "身体先动", "盖法", "破", "余波")
EXTRAS = ("他被叫什么", "他知道哪一层", "他信错了谁", "他对谁演什么", "他跟谁怎么交手", "他独一份的是什么", "他怎么被记住")
HURT = "碰哪里会疼"
BELIEF_TITLE = {"他信的那句假话": "他信的那句话"}
_NUM = "一二三四五六七八九十"


def _tail(line: dict) -> str:
    if line.get("origin") == "盘":
        return " ｜盘 " + "、".join(line.get("sources", []))
    return " ｜定 " + (line.get("ref") or "")


def render(doc: dict, author: bool) -> str:
    who = doc.get("pronoun") or "他"
    out = [f"# {doc['name']} · 戏用页", ""]
    if author:
        out += [f"作者本 · 命盘 `{doc.get('chart', '')}` · 每行末尾是来历：盘带编号，定写出处", ""]
    if doc.get("summary"):
        out += [doc["summary"], ""]
    by = {a["ask"]: a for a in doc.get("asks", [])}
    creed = doc.get("belief") == "信条"
    for i, key in enumerate(ASKS):
        a = by.get(key) or {"lines": []}
        title = BELIEF_TITLE.get(key, key) if creed else key
        out += [f"## {_NUM[i]}、{title.replace('他', who)}", ""]
        lines = a.get("lines") or []
        if not lines:
            out += ["（待补充）", ""]
            continue
        if key == HURT:
            groups: dict[str, list[dict]] = {}
            for ln in lines:
                groups.setdefault(ln.get("line") or "", []).append(ln)
            for name, ls in groups.items():
                out.append(f"- {name}")
                for ln in sorted(ls, key=lambda x: BEATS.index(x["beat"]) if x.get("beat") in BEATS else 9):
                    beat = ln.get("beat", "") + (f"（{ln['by']}）" if ln.get("by") and ln["by"] != "自己" else "")
                    out.append(f"  - {beat}：{ln['text']}" + (_tail(ln) if author else ""))
            out.append("")
            continue
        for ln in lines:
            out.append(f"- {ln['text']}" + (_tail(ln) if author else ""))
        out.append("")
    for key in EXTRAS:
        lines = (by.get(key) or {}).get("lines") or []
        if not lines:
            continue
        out += [f"## 附：{key.replace('他', who)}", ""]
        for ln in lines:
            out.append(f"- {ln['text']}" + (_tail(ln) if author else ""))
        out.append("")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("doc")
    ap.add_argument("--author", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    src = Path(a.doc)
    doc = json.loads(src.read_text(encoding="utf-8"))
    base = src.name[:-len(".json")] if src.name.endswith(".json") else src.stem
    out = Path(a.out) if a.out else src.with_name(base + (".作者本.md" if a.author else ".md"))
    out.write_text(render(doc, a.author), encoding="utf-8", newline="\n")
    print("→", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
