#!/usr/bin/env python3
"""开发期工具：把 source/ditiansui/ocr/p{印刷页}.json 合并成带标签文本，供子代理对图校对与建卡。

书：《滴天髓阐微》中医古籍出版社 2012 年本（刘基撰、孙正治注译，任铁樵增注）。PDF 页 = 印刷页 + 13。
版面四层：原文黑体加粗、"原注："、"任氏曰："（含例盘与"一曰某某格"小标题）、今人的"【原文白话释意】【原注白话讲解】"等块。
今人块常插在任注的议论与任注的例盘之间，所以遇到小标题、例盘或下一条原文就算今人块结束。

标签（每段一个）：
  [标题]   章名（"二十一、官杀"，字大居中）
  [原文]   《滴天髓》原文，黑体加粗；辅以 mobi 原文（source/ditiansui/mobi_paras.json）做模糊匹配
  [原注]   刘基原注，"原注："起头
  [任注]   任铁樵增注，"任氏曰："起头，多段，含例盘的说明；直到今人块或下一条原文
  [小标题] 任注里的分类小标题（"一曰财滋弱杀格"），加粗短行
  [例盘]   任注命例：四柱（年 月 日 时）加大运
  [今注]   今人块（【…】起头，到小标题、例盘或下一条原文为止），有版权，只留占位；被略去的段数写在页码标记里
  [?]      特征不明，交校对者定

输出 source/text/滴天髓_{名}.tagged.md，带页码标记 <!-- p121 -->（印刷页）。
用法：python scripts/tag_ditiansui.py 官杀 121 133      （印刷页区间，可多组）
依赖 numpy、pillow（算墨量以认加粗），用系统 python 或装了它们的环境跑。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source" / "ditiansui"
OCR = SRC / "ocr"
PAGES = SRC / "pages"
OUT = ROOT / "source" / "text"

RE_TITLE = re.compile(r"^[一二三四五六七八九十]{1,3}[、．.]\s*\S{2,6}$")
RE_YUANZHU = re.compile(r"^\s*原注\s*[：:，,]?\s*")
RE_RENZHU = re.compile(r"^\s*任氏曰\s*[：:，,]?\s*")
RE_MODERN = re.compile(r"^\s*[【\[［]\s*[^】\]］]{2,12}\s*[】\]］]")
RE_SUBHEAD = re.compile(r"^[一二三四五六七八九十]{1,3}曰\S{2,10}[。]?$")
GANZHI = set("甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥")
SHISHEN = set("比劫食伤才财官杀印枭卩")
PUNCT = re.compile(r"[，。：；！？“”「」《》（）()]")
CJK = re.compile(r"[一-鿿]")
INK_BOLD = 0.235          # 加粗行的墨量下限（正文 0.11–0.19，原文与小标题 0.25 以上）


def cjk(s: str) -> str:
    return "".join(CJK.findall(s))


class MobiIndex:
    """mobi 原文段的 6-gram 索引，用来认原文段。"""

    def __init__(self, path: Path):
        self.grams: set[str] = set()
        if not path.exists():
            return
        for p in json.loads(path.read_text(encoding="utf-8")):
            if p.get("kind") != "原文":
                continue
            c = cjk(p["text"])
            for i in range(len(c) - 5):
                self.grams.add(c[i:i + 6])

    def ratio(self, text: str) -> float:
        c = cjk(text)
        n = len(c) - 5
        if n <= 0 or not self.grams:
            return 0.0
        return sum(1 for i in range(n) if c[i:i + 6] in self.grams) / n


def strip_label(t: str) -> str:
    while t and t[0] in SHISHEN:
        t = t[1:]
    while t and t[-1] in SHISHEN:
        t = t[:-1]
    return t


def page_lines(n: int) -> tuple[list[dict], float, float]:
    data = json.loads((OCR / f"p{n:03d}.json").read_text(encoding="utf-8"))
    img = np.array(Image.open(PAGES / f"p{n:03d}.png").convert("L"))
    H, W = img.shape
    lines = []
    for l in data:
        (x0, y0), (x1, y1) = l["box"][0], l["box"][2]
        crop = img[int(y0):int(y1), int(x0):int(x1)]
        ink = float((crop < 128).mean()) if crop.size else 0.0
        lines.append({"text": l["text"].strip(), "conf": float(l["score"]), "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                      "h": y1 - y0, "ink": ink})
    lines.sort(key=lambda l: (l["y0"], l["x0"]))
    return lines, W, H


def paragraphs(n: int, mobi: MobiIndex) -> list[dict]:
    """一页的段落。kind 为 text 或 lipan；例盘右栏的说明与其后整行的续行合成一段 text。"""
    lines, W, H = page_lines(n)
    body = []
    for l in lines:
        t = l["text"]
        if l["y0"] < H * 0.09 or (l["y0"] > H * 0.92 and re.fullmatch(r"\d{1,3}", t)):
            continue                                        # 页眉、页码
        if l["x0"] > W * 0.86 or l["x1"] < W * 0.08:
            continue                                        # 两侧竖排书名与花饰
        if not cjk(t):
            continue                                        # 花饰识成的字母数字
        body.append(l)
    if not body:
        return []
    heights = sorted(l["h"] for l in body if l["x0"] > W * 0.42 or l["h"] < 50)
    lh = (heights[len(heights) // 2] if heights else 40) or 40

    pillars, dayuns, prose = [], [], []
    for l in body:
        tt = re.sub(r"\s", "", l["text"])
        core = strip_label(tt)
        if l["x0"] < W * 0.32 and len(core) == 2 and all(c in GANZHI for c in core) and l["h"] >= lh * 1.2:
            pillars.append({**l, "core": core})
        elif W * 0.30 <= l["x0"] < W * 0.45 and len(tt) == 2 and all(c in GANZHI for c in tt):
            dayuns.append({**l, "core": tt})
        elif l["x0"] < W * 0.45 and (len(cjk(tt)) <= 2 and all(c in SHISHEN for c in cjk(tt))):
            continue                                        # 十神标签
        elif l["x0"] < W * 0.45 and l["h"] > lh * 3 and all(c in SHISHEN or c in GANZHI for c in cjk(tt)):
            continue                                        # 藏干竖排
        elif l["h"] > (l["x1"] - l["x0"]) * 1.2 and len(cjk(tt)) >= 3:
            continue                                        # 其他竖排残片
        else:
            prose.append(l)

    # 例盘分组：四柱一组，柱间纵距突然拉大也分组
    groups: list[dict] = []
    for p in pillars:
        if groups and len(groups[-1]["pillars"]) < 4 and p["y0"] - groups[-1]["pillars"][-1]["y1"] < lh * 1.5:
            groups[-1]["pillars"].append(p)
        else:
            groups.append({"pillars": [p], "dayun": [], "comment": []})
    for g in groups:
        g["top"] = g["pillars"][0]["y0"] - lh
        g["bottom"] = g["pillars"][-1]["y1"]
    for d in dayuns:
        owner = None
        for g in groups:
            if g["top"] <= d["y0"]:
                owner = g
        if owner is not None:
            owner["dayun"].append(d)
            owner["bottom"] = max(owner["bottom"], d["y1"])
    ordinary = []
    for l in prose:
        owner = None
        if l["x0"] > W * 0.42:
            for g in groups:
                if g["top"] <= l["y0"] <= g["bottom"] + lh * 1.2:
                    owner = g
        if owner is not None:
            owner["comment"].append(l)
        else:
            ordinary.append(l)

    xs = sorted(l["x0"] for l in ordinary if l["h"] <= lh * 1.5)
    margin = xs[len(xs) // 10] if xs else 0
    ys = sorted(l["y0"] for l in ordinary)
    diffs = sorted(b - a for a, b in zip(ys, ys[1:]) if b - a > lh * 0.5)
    pitch = diffs[len(diffs) // 2] if diffs else lh * 1.5

    events = [("group", g["top"], g) for g in groups] + [("line", l["y0"], l) for l in ordinary]
    events.sort(key=lambda e: e[1])
    paras: list[dict] = []
    open_comment = False
    prev_y0 = None
    for kind, _, obj in events:
        if kind == "group":
            paras.append({"kind": "lipan", "pillars": [p["core"] for p in obj["pillars"]],
                          "dayun": [d["core"] for d in obj["dayun"]], "big": False})
            if obj["comment"]:
                paras.append({"kind": "text", "lines": list(obj["comment"]), "big": False, "gap": False})
                open_comment = True
                prev_y0 = obj["comment"][-1]["y0"]
            else:
                open_comment = False
                prev_y0 = obj["bottom"]
            continue
        l = obj
        t = l["text"]
        x0, y0, h = l["x0"], l["y0"], l["h"]
        indent = x0 - margin > lh * 1.0
        gap = prev_y0 is not None and (y0 - prev_y0) > pitch * 1.6
        centered = abs((x0 + l["x1"]) / 2 - W / 2) < W * 0.10 and (l["x1"] - x0) < W * 0.5
        big = (h > lh * 1.4 and centered) and len(t) <= 12 and not PUNCT.search(t)
        marker = bool(RE_MODERN.match(t) or RE_YUANZHU.match(t) or RE_RENZHU.match(t))
        if open_comment and not indent and not gap and not big and not marker:
            paras[-1]["lines"].append(l)
        elif not paras or paras[-1]["kind"] != "text" or indent or gap or big or marker or paras[-1]["big"]:
            paras.append({"kind": "text", "lines": [l], "big": bool(big), "gap": bool(gap)})
            open_comment = False
        else:
            paras[-1]["lines"].append(l)
        prev_y0 = y0
    for p in paras:
        if p["kind"] == "text":
            p["text"] = "".join(x["text"] for x in p["lines"])
            p["conf"] = round(min(x["conf"] for x in p["lines"]), 3)
            p["ink"] = round(float(np.median([x["ink"] for x in p["lines"]])), 3)
            p["mobi"] = round(mobi.ratio(p["text"]), 2)
    return paras


def main(argv: list[str]) -> int:
    if len(argv) < 3 or len(argv) % 2 == 0:
        print(__doc__); return 2
    name = argv[0]
    ranges = [(int(argv[i]), int(argv[i + 1])) for i in range(1, len(argv), 2)]
    mobi = MobiIndex(SRC / "mobi_paras.json")
    OUT.mkdir(exist_ok=True)
    chunks = [f"# 《滴天髓阐微》{name}相关页，OCR 自动分段与打标，待校对\n",
              "页码是印刷页码（书页下角花饰里的数字），页图在 source/ditiansui/pages/p{页}.png。标签：[原文] 滴天髓原文；[原注] 刘基原注；[任注] 任铁樵增注；[小标题] 任注里的分类标题；[例盘] 年 月 日 时 | 大运；[今注] 今人白话与注释只留占位，页码标记里记被略去的段数；[标题]；[?] 待定。行末括号是 OCR 最低置信度。\n"]
    stats = {k: 0 for k in ("标题", "原文", "原注", "任注", "小标题", "例盘", "今注", "?")}
    mode = "原文"
    for lo, hi in ranges:
        for n in range(lo, hi + 1):
            if not (OCR / f"p{n:03d}.json").exists():
                chunks.append(f"\n<!-- p{n:03d} 缺 OCR -->\n"); continue
            page_chunks: list[str] = []
            skipped = 0
            for p in paragraphs(n, mobi):
                if p["kind"] == "lipan":
                    if mode == "今注":
                        mode = "任注"
                    t = " ".join(p["pillars"]) + (" | " + " ".join(p["dayun"]) if p["dayun"] else "")
                    stats["例盘"] += 1
                    page_chunks.append(f"[例盘] {t}\n")
                    continue
                t = p["text"]
                bold = p["ink"] >= INK_BOLD
                if p["big"] and RE_TITLE.match(t):
                    tag, mode = "标题", "原文"
                elif RE_MODERN.match(t):
                    tag, mode = "今注", "今注"
                elif RE_YUANZHU.match(t):
                    tag, mode = "原注", "原注"
                elif RE_RENZHU.match(t):
                    tag, mode = "任注", "任注"
                elif RE_SUBHEAD.match(t) or (bold and len(cjk(t)) <= 12 and not PUNCT.search(t)):
                    tag, mode = "小标题", "任注"
                elif p["mobi"] >= 0.5 or (bold and len(cjk(t)) >= 8 and PUNCT.search(t)):
                    tag, mode = "原文", "原文"
                elif mode == "今注":
                    tag = "今注"
                elif mode in ("任注", "原注"):
                    tag = mode
                else:
                    tag = "?"
                stats[tag] += 1
                if tag == "今注":
                    if RE_MODERN.match(t):
                        page_chunks.append("[今注] （今人白话与注释，不入语料，略）\n")
                    else:
                        skipped += 1
                    continue
                page_chunks.append(f"[{tag}] {t}  （{p['conf']}）\n")
            note = f" 今注略 {skipped} 段" if skipped else ""
            chunks.append(f"\n<!-- p{n:03d}{note} -->\n")
            chunks.extend(page_chunks)
    dst = OUT / f"滴天髓_{name}.tagged.md"
    dst.write_text("".join(chunks), encoding="utf-8")
    print(dst, stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
