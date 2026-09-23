#!/usr/bin/env python3
"""开发期工具：把 source/ziping/ocr/p{页}.json 合并成带标签文本，供子代理对图校对与建卡。

标签（每段一个）：
  [标题]   章名（"三十一、论正官"，字大居中）
  [原文]   沈孝瞻原文
  [徐评]   徐乐吾评注，书里以"【徐评】"起头；徐评可多段，直到下一个原文段（段前有空行）
  [例盘]   徐评里的命例四柱与大运（干支占大半的段）
  [注释]   今人注释块（"【注释】"起），有版权，只留占位不留内容
  [白话]   今人白话释意块（"【白话释意】"起），有版权，只留占位不留内容
  [?]      特征不明，交校对者定

注释与白话两块从块首起一直到下一章标题，中间跨页也算，脚本按页序带状态。
输出 source/text/子平真诠_{名}.tagged.md，带页码标记 <!-- p127 -->（印刷页）。
用法：python scripts/tag_ziping.py 格局 86 158 199 310
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
OCR = ROOT / "source" / "ziping" / "ocr"
OUT = ROOT / "source" / "text"

RE_HEADER = re.compile(r"^\s*(子平真诠|子平真[诠谈维]?|[一二三四五六七八九十]+、论\S*|\d{1,3})\s*$")
RE_XU = re.compile(r"^\s*[【\[［]\s*徐评\s*[】\]］]\s*")
RE_ZHU = re.compile(r"^\s*[【\[［]\s*注释\s*[】\]］]")
RE_BAIHUA = re.compile(r"^\s*[【\[［]\s*白话(释意)?\s*[】\]］]")
RE_TITLE = re.compile(r"^[一二三四五六七八九十百]+、")
GANZHI = set("甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥")
PUNCT = re.compile(r"[，。：；！？、“”「」《》（）()]")
PUNCT_TITLE = re.compile(r"[，。：；！？“”「」《》（）()]")   # 章名里有顿号（"九、论……"），不算标点


def is_pillar(text: str) -> bool:
    """命例左栏的一柱（"丁亥"）或带序的大运（"初七丙辰"）。"""
    t = re.sub(r"[\s，。、]", "", text)
    return 2 <= len(t) <= 6 and sum(c in GANZHI for c in t) >= 2 and all(c in GANZHI or c in "初十廿卅一二三四五六七八九" for c in t)


def paragraphs(data: dict) -> list[dict]:
    """按缩进、行距、字号分段。lines 已按版面排序。命例左栏的干支短行单独归拢成一段（lipan=True），插在其右栏说明之前。"""
    W = data["width"]
    H = data["height"]
    # 页眉（页顶 9% 内）与页码（页底 8% 内）按位置删；章名在页中，同样的字样要留
    body = [l for l in data["lines"]
            if not (RE_HEADER.match(l["text"]) and (l["box"][0][1] < H * 0.09 or l["box"][0][1] > H * 0.92))
            and l["box"][0][0] < W * 0.88         # 右侧竖排书名"子平真诠"按位置删
            and not (l["text"].strip() == "子平真诠" and (l["box"][2][1] - l["box"][0][1]) > 90)]
    if not body:
        return []
    prose = [l for l in body if not is_pillar(l["text"])] or body
    heights = sorted((l["box"][2][1] - l["box"][0][1]) for l in prose)
    lh = heights[len(heights) // 2] or 30
    xs = sorted(l["box"][0][0] for l in prose if (l["box"][2][1] - l["box"][0][1]) <= lh * 1.5)
    margin = xs[len(xs) // 10] if xs else 0
    ys = sorted(l["box"][0][1] for l in prose)
    diffs = sorted(b - a for a, b in zip(ys, ys[1:]) if b - a > lh * 0.5)
    pitch = diffs[len(diffs) // 2] if diffs else lh * 1.6
    paras: list[dict] = []
    pillars: list[dict] = []
    prev_y0 = None
    prev_x0 = margin

    def flush_pillars() -> None:
        if pillars:
            paras.append({"lines": list(pillars), "big": False, "gap": False, "lipan": True})
            pillars.clear()

    for l in body:
        x0, y0 = l["box"][0]; x1, y1 = l["box"][2]
        h = y1 - y0
        text = l["text"].strip()
        if is_pillar(text) and x0 - margin < W * 0.45:
            if len(pillars) >= 4:          # 一例四柱，第五柱起是下一例
                flush_pillars()
            pillars.append(l)
            prev_y0 = y0               # 左栏干支也占一行，行距照算，免得右栏说明被判成空行隔开
            continue
        indent = x0 - prev_x0 > lh * 1.2
        gap = prev_y0 is not None and (y0 - prev_y0) > pitch * 1.45
        centered = abs((x0 + x1) / 2 - W / 2) < W * 0.08 and (x1 - x0) < W * 0.5
        big = (h > lh * 1.3 or centered) and len(text) <= 16 and not PUNCT_TITLE.search(text)
        marker = bool(RE_XU.match(text) or RE_ZHU.match(text) or RE_BAIHUA.match(text))
        if not paras or indent or gap or big or marker or paras[-1]["big"]:
            if gap or big or marker or len(pillars) >= 4:
                flush_pillars()
            paras.append({"lines": [l], "big": bool(big), "gap": bool(gap), "lipan": False})
        else:
            paras[-1]["lines"].append(l)
        prev_y0, prev_x0 = y0, x0
    flush_pillars()
    for p in paras:
        joiner = " " if p["lipan"] else ""
        p["text"] = joiner.join(x["text"].strip() for x in p["lines"])
        p["conf"] = round(min(x["conf"] for x in p["lines"]), 3)
    return paras


def is_lipan(text: str) -> bool:
    core = PUNCT.sub("", text)
    return len(core) >= 8 and sum(c in GANZHI for c in core) / len(core) >= 0.6


def main(argv: list[str]) -> int:
    if len(argv) < 3 or len(argv) % 2 == 0:
        print(__doc__); return 2
    name = argv[0]
    ranges = [(int(argv[i]), int(argv[i + 1])) for i in range(1, len(argv), 2)]
    OUT.mkdir(exist_ok=True)
    chunks = [f"# 《子平真诠评注》{name}相关页，OCR 自动分段与打标，待校对\n",
              "页码是印刷页码，页图在 source/ziping/pages/p{页}.png。标签：[原文] 沈孝瞻原文；[徐评] 徐乐吾评注；[例盘]；[标题]；[注释] [白话] 今人著作只留占位；[?] 待定。行末括号是 OCR 最低置信度。\n"]
    stats = {"原文": 0, "徐评": 0, "例盘": 0, "标题": 0, "注释": 0, "白话": 0, "?": 0}
    mode = "原文"       # 原文 | 徐评 | 注释 | 白话，跨页保持
    for lo, hi in ranges:
        for n in range(lo, hi + 1):
            f = OCR / f"p{n:03d}.json"
            if not f.exists():
                chunks.append(f"\n<!-- p{n:03d} 缺 OCR -->\n"); continue
            data = json.loads(f.read_text(encoding="utf-8"))
            chunks.append(f"\n<!-- p{n:03d} -->\n")
            for p in paragraphs(data):
                t = p["text"]
                if p["big"] and (RE_TITLE.match(t) or "论" in t):
                    tag, mode = "标题", "原文"
                elif RE_ZHU.match(t):
                    tag, mode = "注释", "注释"
                elif RE_BAIHUA.match(t):
                    tag, mode = "白话", "白话"
                elif mode in ("注释", "白话"):
                    tag = mode
                elif RE_XU.match(t):
                    tag, mode = "徐评", "徐评"
                    t = RE_XU.sub("", t)
                elif p["lipan"] or is_lipan(t):
                    tag = "例盘"
                elif mode == "徐评" and not p["gap"]:
                    tag = "徐评"
                elif p["big"]:
                    tag = "?"
                else:
                    tag, mode = "原文", "原文"
                if tag == "徐评" and not t.strip():
                    continue                       # "【徐评】"单独占一行，去掉标签后是空段，下一段已按状态标徐评
                stats[tag] += 1
                if tag in ("注释", "白话"):
                    chunks.append(f"[{tag}] （今人{tag}，不入语料，略）\n") if RE_ZHU.match(p["text"]) or RE_BAIHUA.match(p["text"]) else None
                    continue
                chunks.append(f"[{tag}] {t}  （{p['conf']}）\n")
    dst = OUT / f"子平真诠_{name}.tagged.md"
    dst.write_text("".join(chunks), encoding="utf-8")
    print(dst, stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
