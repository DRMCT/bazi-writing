#!/usr/bin/env python3
"""開發期工具：把 source/ocr/pNNN.json 合併成按日主分的帶標籤文本，供子代理校對與抽取。

標籤（每段一個）：
  [标题]  月份或卷名標題（行高大、字少）
  [正文]  余春台正文（楷體：aniso 高；或與網上通行本語料相似度高）
  [徐注]  徐樂吾評注（宋體：aniso 低）
  [例盘]  四柱干支列表及其後的評語、按語
  [校记]  頁腳 ①②③ 校記
  [?]     兩個特徵打架或都不夠明確，交校對者定

輸出 source/text/{日主}.tagged.md，帶頁碼標記 <!-- pNNN -->。只在校核階段用。
用法：python scripts/tag_ocr.py 乙 [--start 68 --end 99]
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_cards as cc  # noqa: E402

RANGES = {"甲": (34, 67), "乙": (68, 99), "丙": (100, 133), "丁": (134, 159), "戊": (160, 185),
          "己": (186, 207), "庚": (208, 235), "辛": (236, 265), "壬": (266, 295), "癸": (296, 321)}
# OCR 常見誤讀先歸一再匹配干支：成→戌、已/巳→己、王→壬、末→未、葵→癸、卵→卯、康→庚
OCR_FIX = str.maketrans({"成": "戌", "已": "己", "巳": "己", "王": "壬", "末": "未", "葵": "癸", "卵": "卯", "康": "庚"})
GZ = "[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰己午未申酉戌亥]"
RE_LIPAN = re.compile(rf"^\s*{GZ}\s*[，,]\s*{GZ}\s*[，,]\s*{GZ}\s*[，,]\s*{GZ}")
RE_JIAOJI = re.compile(r"^\s*[①②③④⑤⑥⑦⑧⑨⑩]")
RE_HEADER = re.compile(r"四库存目|子平汇刊|命理秘本穷通宝鉴|穷通宝鉴评注|^\s*[•·。.]?\s*\d{1,3}\s*[•·。.:：]?\s*$")
RE_TITLE = re.compile(r"^\s*(三[春夏秋冬]|[正二三四五六七八九十]{1,3}月)?\s*[甲乙丙丁戊己庚辛壬癸][木火土金水]\s*(总论)?\s*$|^\s*[正二三四五六七八九十]{1,3}月\s*$")
KAI_AT, SONG_AT, SIM_AT = 0.80, 0.72, 0.60


def load_corpus(dm: str) -> list[str]:
    p = Path("references/校核/语料") / f"穷通宝鉴_正文_{dm}.txt"
    return [cc.normalize(s) for s in re.split(r"[。；！？\n]", p.read_text(encoding="utf-8")) if len(cc.normalize(s)) >= 6]


def best_sim(text: str, corpus: list[str]) -> float:
    n = cc.normalize(text)
    if len(n) < 6:
        return 0.0
    # 段落可能跨多句：按句取最高相似度的平均
    sents = [cc.normalize(s) for s in re.split(r"[。；！？]", text) if len(cc.normalize(s)) >= 6] or [n]
    scores = [max((difflib.SequenceMatcher(None, s, c).ratio() for c in corpus), default=0.0) for s in sents]
    return sum(scores) / len(scores)


def paragraphs(lines: list[dict]) -> list[dict]:
    """按縮進與行距分段。lines 已按版面排序。"""
    body = [l for l in lines if not RE_HEADER.search(l["text"])]
    if not body:
        return []
    heights = sorted((l["box"][2][1] - l["box"][0][1]) for l in body)
    lh = heights[len(heights) // 2] or 24
    xs = sorted(l["box"][0][0] for l in body if (l["box"][2][1] - l["box"][0][1]) <= lh * 1.5)
    margin = xs[len(xs) // 10] if xs else 0  # 取第 10 百分位，避開偶發的框偏移
    # 行距：相鄰行 y0 之差的中位數；段間距明顯大於行距才算分段
    ys = sorted(l["box"][0][1] for l in body)
    diffs = sorted(b - a for a, b in zip(ys, ys[1:]) if b - a > lh * 0.5)
    pitch = diffs[len(diffs) // 2] if diffs else lh * 1.6
    paras: list[dict] = []
    prev_y0 = None
    for l in body:
        x0, y0 = l["box"][0]; y1 = l["box"][2][1]
        h = y1 - y0
        indent = x0 - margin > lh * 1.2  # 首行縮進兩字，續行貼邊
        gap = prev_y0 is not None and (y0 - prev_y0) > pitch * 1.45
        big = h > lh * 1.35 and len(l["text"]) <= 12
        if not paras or indent or gap or big or paras[-1]["big"]:
            paras.append({"lines": [l], "big": big})
        else:
            paras[-1]["lines"].append(l)
        prev_y0 = y0
    for p in paras:
        p["text"] = "".join(x["text"] for x in p["lines"])
        w = [len(x["text"]) for x in p["lines"]]
        p["aniso"] = round(sum(x["aniso"] * n for x, n in zip(p["lines"], w)) / max(1, sum(w)), 3)
        p["conf"] = round(min(x["conf"] for x in p["lines"]), 3)
    return paras


def classify(p: dict, corpus: list[str], in_lipan: bool) -> tuple[str, float]:
    t = p["text"].strip()
    sim = best_sim(t, corpus)
    if RE_JIAOJI.match(t):
        return "校记", sim
    if p["big"] or RE_TITLE.match(t):
        return "标题", sim
    if RE_LIPAN.match(t.translate(OCR_FIX)):
        return "例盘", sim
    if in_lipan and (t.startswith("按") or re.match(r"^\s*(光绪|同治|咸丰|道光|嘉庆|乾隆|康熙|雍正|民国|明|清|宣统)", t) or p["aniso"] <= SONG_AT):
        return "例盘", sim
    a = p["aniso"]
    if sim >= SIM_AT:
        return "正文", sim
    if a >= KAI_AT:
        return "正文", sim
    if a <= SONG_AT:
        return "徐注", sim
    return "?", sim


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("day_master")
    ap.add_argument("--start", type=int); ap.add_argument("--end", type=int)
    a = ap.parse_args(argv)
    dm = a.day_master
    lo, hi = RANGES[dm]
    lo, hi = a.start or lo, a.end or hi
    corpus = load_corpus(dm)
    out = Path("source/text"); out.mkdir(exist_ok=True)
    chunks = [f"# 《穷通宝鉴评注》{dm} 日主，PDF 第 {lo}–{hi} 页，OCR 自动分段与打标，待校对\n",
              "标签含义：[正文] 余春台正文（楷体）；[徐注] 徐乐吾评注（宋体）；[例盘] 命造与按语；[标题]；[校记]；[?] 待定。\n",
              "行末括号是（笔画比, 语料相似度, OCR 置信度）。\n"]
    stats = {"正文": 0, "徐注": 0, "例盘": 0, "标题": 0, "校记": 0, "?": 0}
    in_lipan = False  # 例盤清單可跨頁，不按頁重置
    for n in range(lo, hi + 1):
        f = Path("source/ocr") / f"p{n:03d}.json"
        if not f.exists():
            chunks.append(f"\n<!-- p{n:03d} 缺 OCR -->\n"); continue
        data = json.loads(f.read_text(encoding="utf-8"))
        chunks.append(f"\n<!-- p{n:03d} -->\n")
        for p in paragraphs(data["lines"]):
            tag, sim = classify(p, corpus, in_lipan)
            in_lipan = tag == "例盘" or (in_lipan and tag not in ("标题", "正文"))
            stats[tag] += 1
            chunks.append(f"[{tag}] {p['text']}  （{p['aniso']}, {sim:.2f}, {p['conf']}）\n")
    dst = out / f"{dm}.tagged.md"
    dst.write_text("".join(chunks), encoding="utf-8")
    print(dst, stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
