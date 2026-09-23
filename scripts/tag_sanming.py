#!/usr/bin/env python3
"""开发期工具：把 source/sanming/ocr/{册}{页}.json 合并成带标签文本，供子代理对图校对与建卡。

标签（每段一个）：
  [标题]   篇名、卷名（字大、居中、短）
  [正文]   四库本正文
  [校者注] 页脚"校者注"及其后的①②③各条（闵兆才编校）
  [表格]   表格页，按行拼，格间用 ｜
  [?]      特征不明，交校对者定

输出 source/text/三命通会_{名}.tagged.md，带页码标记 <!-- 上146 -->。
用法：python scripts/tag_sanming.py 神煞 上 125 200 中 346 351 374 378
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
OCR = ROOT / "source" / "sanming" / "ocr"
OUT = ROOT / "source" / "text"

RE_HEADER = re.compile(r"四库版足本|三命通会|钦定四库全书|^\s*目\s*录\s*$|^\s*\d{1,3}\s*$")
RE_NOTE_START = re.compile(r"^\s*校者注")
RE_NOTE_ITEM = re.compile(r"^\s*[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]")
PUNCT = re.compile(r"[，。：；！？、“”「」《》（）()]")


def paragraphs(data: dict) -> list[dict]:
    """按缩进、行距、字号分段。lines 已按版面排序。"""
    W = data["width"]
    body = [l for l in data["lines"] if not RE_HEADER.search(l["text"]) or len(l["text"]) > 14]
    if not body:
        return []
    heights = sorted((l["box"][2][1] - l["box"][0][1]) for l in body)
    lh = heights[len(heights) // 2] or 30
    xs = sorted(l["box"][0][0] for l in body if (l["box"][2][1] - l["box"][0][1]) <= lh * 1.5)
    margin = xs[len(xs) // 10] if xs else 0
    ys = sorted(l["box"][0][1] for l in body)
    diffs = sorted(b - a for a, b in zip(ys, ys[1:]) if b - a > lh * 0.5)
    pitch = diffs[len(diffs) // 2] if diffs else lh * 1.6
    paras: list[dict] = []
    prev_y0 = None
    for l in body:
        x0, y0 = l["box"][0]; x1, y1 = l["box"][2]
        h = y1 - y0
        text = l["text"].strip()
        indent = x0 - margin > lh * 1.2
        gap = prev_y0 is not None and (y0 - prev_y0) > pitch * 1.45
        centered = abs((x0 + x1) / 2 - W / 2) < W * 0.08 and (x1 - x0) < W * 0.5
        big = (h > lh * 1.3 or centered) and len(text) <= 14 and not PUNCT.search(text)
        small = h < lh * 0.85
        note = RE_NOTE_START.match(text) or RE_NOTE_ITEM.match(text)
        if not paras or indent or gap or big or note or paras[-1]["big"] or (small != paras[-1]["small"]):
            paras.append({"lines": [l], "big": bool(big), "small": bool(small), "note": bool(note)})
        else:
            paras[-1]["lines"].append(l)
        prev_y0 = y0
    for p in paras:
        p["text"] = "".join(x["text"].strip() for x in p["lines"])
        p["conf"] = round(min(x["conf"] for x in p["lines"]), 3)
    return paras


def is_table_page(data: dict) -> bool:
    lines = [l for l in data["lines"] if not RE_HEADER.search(l["text"])]
    if len(lines) < 12:
        return False
    short = sum(1 for l in lines if len(l["text"].strip()) <= 5)
    return short / len(lines) >= 0.5


def table_rows(data: dict) -> list[str]:
    lines = [l for l in data["lines"] if not RE_HEADER.search(l["text"]) or len(l["text"]) > 14]
    rows: list[list[dict]] = []
    for l in sorted(lines, key=lambda l: (l["box"][0][1], l["box"][0][0])):
        y = l["box"][0][1]
        if rows and abs(rows[-1][0]["box"][0][1] - y) < 25:
            rows[-1].append(l)
        else:
            rows.append([l])
    return ["｜".join(x["text"].strip() for x in sorted(r, key=lambda l: l["box"][0][0])) for r in rows]


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print(__doc__); return 2
    name = argv[0]
    specs: list[tuple[str, int, int]] = []
    i = 1
    while i < len(argv):
        vol = argv[i]; i += 1
        while i + 1 < len(argv) and argv[i].isdigit():
            specs.append((vol, int(argv[i]), int(argv[i + 1]))); i += 2
    OUT.mkdir(exist_ok=True)
    chunks = [f"# 《四库版足本三命通会》{name}相关页，OCR 自动分段与打标，待校对\n",
              "页码是印刷页码，页图在 source/sanming/pages/{册}{页}.png。标签：[正文] 四库本正文；[校者注] 闵兆才校注；[标题]；[表格]；[?] 待定。行末括号是 OCR 最低置信度。\n"]
    stats = {"正文": 0, "校者注": 0, "标题": 0, "表格": 0, "?": 0}
    for vol, lo, hi in specs:
        for n in range(lo, hi + 1):
            f = OCR / f"{vol}{n:03d}.json"
            if not f.exists():
                chunks.append(f"\n<!-- {vol}{n:03d} 缺 OCR -->\n"); continue
            data = json.loads(f.read_text(encoding="utf-8"))
            chunks.append(f"\n<!-- {vol}{n:03d} -->\n")
            if is_table_page(data):
                for row in table_rows(data):
                    chunks.append(f"[表格] {row}\n"); stats["表格"] += 1
                continue
            in_note = False
            for p in paragraphs(data):
                t = p["text"]
                if p["note"] or in_note:
                    tag, in_note = "校者注", True
                elif p["big"]:
                    tag = "标题"
                elif p["small"]:
                    tag = "?"
                else:
                    tag = "正文"
                stats[tag] += 1
                chunks.append(f"[{tag}] {t}  （{p['conf']}）\n")
    dst = OUT / f"三命通会_{name}.tagged.md"
    dst.write_text("".join(chunks), encoding="utf-8")
    print(dst, stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
