#!/usr/bin/env python3
"""开发期工具：把《子平真诠评注》附录《人鉴·命理存验》67 例（印刷页 311–487）的 OCR 合并成带标签文本，供子代理对图校对。

附录版面（每例）：居中标题"一、曹汝霖"；左上是命盘表（十神 | 天干 | 地支 | 藏干十神，四行，有的例只有干支两列）；
表右是大运列（"初四壬寅"，前两字是起运岁）；表下一行"胎元壬辰 立命卯宫"；表右与其后是林庚白的判词；
再后是今人写的"【意译与解说】"块（流年表、生平、白话），一直到下一例标题，有版权，只留占位。

标签：
  [标题]   例号与姓名
  [例盘]   四柱 | 大运 | 胎元立命。四柱由表格里的干支字按行拼出，OCR 常把表格切碎，拼不出的柱写 □□，校对者按图重写整行
  [判词]   林庚白原判（1930 年代作，作者 1941 年卒，已过保护期）
  [解说]   今人意译与解说块，只留占位
  [?]      特征不明

输出 source/text/子平真诠_人鉴.tagged.md，页码标记 <!-- p311 -->（印刷页）。用法：
    python scripts/tag_ziping_renjian.py 311 487
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
OCR = ROOT / "source" / "ziping" / "ocr"
OUT = ROOT / "source" / "text" / "子平真诠_人鉴.tagged.md"

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
GZ = set(STEMS + BRANCHES)
RE_TITLE = re.compile(r"^[一二三四五六七八九十干□]{1,3}、\S{1,8}$")   # 干：OCR 把"十"认成"干"；□：标题整行漏认时的占位
RE_DAYUN = re.compile(r"^[初十廿卅一二三四五六七八九]{1,3}[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]$")
RE_JIESHUO = re.compile(r"^\s*[【\[［]\s*意译与解说\s*[】\]］]")
RE_TAIYUAN = re.compile(r"胎元|立命")
RE_HEADER = re.compile(r"^(附录[：:]?.*|子平真诠|\d{1,3})$")
# 表格里的非干支字：十神与藏干标签、"元"（日元）、神煞名
LABELS = set("比劫食伤财才官杀煞印枭元库")


def clean(t: str) -> str:
    return re.sub(r"[\s，。、；：]", "", t)


def body_lines(data: dict) -> list[dict]:
    W, H = data["width"], data["height"]
    out = []
    for l in data["lines"]:
        x0, y0 = l["box"][0]; x1, y1 = l["box"][2]
        t = l["text"].strip()
        if x0 > W * 0.88 and (y1 - y0) > (x1 - x0):     # 右侧竖排书名
            continue
        if RE_HEADER.match(clean(t)) and (y0 < H * 0.09 or y0 > H * 0.90):   # 书眉、页码
            continue
        if y0 < H * 0.09 and "命理存验" in t:
            continue
        out.append(l)
    return out


def pillars_from(region: list[dict], W: int) -> str:
    """表格区（左半、大运列以左）的干支字按行拼四柱；每行取第一个天干与第一个地支。"""
    rows: list[list[dict]] = []
    for l in sorted(region, key=lambda l: (l["box"][0][1], l["box"][0][0])):
        y = l["box"][0][1]
        if rows and abs(rows[-1][0]["box"][0][1] - y) < 40:
            rows[-1].append(l)
        else:
            rows.append([l])
    pillars = []
    for row in rows:
        chars = "".join(clean(l["text"]) for l in sorted(row, key=lambda l: l["box"][0][0]))
        stem = next((c for c in chars if c in STEMS), None)
        branch = next((c for c in chars if c in BRANCHES), None)
        if stem or branch:
            pillars.append((stem or "□") + (branch or "□"))
    while len(pillars) < 4:
        pillars.append("□□")
    return " ".join(pillars[:4])


def tag_page(data: dict, state: dict) -> list[str]:
    W, H = data["width"], data["height"]
    lines = body_lines(data)
    wide = sorted(l["box"][0][0] for l in lines if (l["box"][2][0] - l["box"][0][0]) > W * 0.5)
    margin = wide[len(wide) // 10] if wide else W * 0.13     # 奇偶页左边距不同（装订侧），按通栏行取
    out: list[str] = []
    i = 0
    judg: list[str] = []          # 判词行，攒成段
    judg_conf = 1.0

    def flush_judg() -> None:
        nonlocal judg, judg_conf
        if judg:
            out.append(f"[判词] {''.join(judg)}  （{judg_conf:.3f}）")
            judg, judg_conf = [], 1.0

    while i < len(lines):
        l = lines[i]
        t = l["text"].strip()
        x0, y0 = l["box"][0]; x1, y1 = l["box"][2]
        ct = clean(t)
        if state["mode"] == "解说" and RE_DAYUN.match(ct):
            # 解说块里冒出大运列，说明这一例的标题整行没被 OCR 认出：补一个占位标题，校对者按图改
            lines.insert(i, {"text": "□、□", "conf": 0.0, "box": [[int(W * 0.4), y0 - 200], [int(W * 0.6), y0 - 200], [int(W * 0.6), y0 - 160], [int(W * 0.4), y0 - 160]]})
            continue
        tt = re.sub(r"\s", "", t)     # 标题里的顿号要留着认
        centered = abs((x0 + x1) / 2 - W / 2) < W * 0.12
        if RE_TITLE.match(tt) and centered:
            flush_judg()
            state["mode"] = "判词"
            state["in_table"] = True
            out.append(f"[标题] {tt}  （{l['conf']}）")
            # 表格区：标题之后到"胎元/立命"行（含）之间、x < 0.6W 的行
            j = i + 1
            table, dayun, taiyuan = [], [], []
            end = None
            dayun_boxes = [m for m in lines[i + 1:i + 40] if RE_DAYUN.match(clean(m["text"]))]
            dx = min((m["box"][0][0] for m in dayun_boxes), default=W * 0.45)      # 大运列左缘：四柱在其左
            right_x = max((m["box"][2][0] for m in dayun_boxes), default=W * 0.55)  # 大运列右缘：判词在其右
            while j < len(lines):
                m = lines[j]; mt = clean(m["text"])
                mx0, my0 = m["box"][0]
                if RE_TITLE.match(re.sub(r"\s", "", m["text"])) or RE_JIESHUO.match(m["text"]):
                    break
                if mx0 < right_x - 20:
                    if RE_TAIYUAN.search(mt):
                        taiyuan.append(mt); end = j
                        # 胎元与立命可能是两个框
                        k = j + 1
                        while k < len(lines) and abs(lines[k]["box"][0][1] - my0) < 30 and lines[k]["box"][0][0] < right_x - 20:
                            taiyuan.append(clean(lines[k]["text"])); k += 1
                        end = k - 1
                        break
                    if RE_DAYUN.match(mt):
                        dayun.append(mt)
                    elif (m["box"][2][1] - my0) > 2.2 * (m["box"][2][0] - mx0):
                        pass   # 竖排藏干列
                    elif (m["box"][2][0] - mx0) > W * 0.5:
                        break  # 通栏正文，表格已结束（无胎元行的例）
                    else:
                        table.append(m)
                j += 1
            if end is None:
                end = j - 1
            table = [m for m in table if m["box"][0][0] < dx - 10]   # 大运列以左才是四柱
            conf = min([l["conf"]] + [m["conf"] for m in lines[i + 1:end + 1]]) if end > i else l["conf"]
            out.append(f"[例盘] {pillars_from(table, W)} | {' '.join(dayun)} | {' '.join(taiyuan)}  （{conf:.3f}）")
            # 表格区右栏的判词行（x >= 0.6W）按顺序进判词
            for m in lines[i + 1:end + 1]:
                if m["box"][0][0] >= right_x - 20 and not RE_DAYUN.match(clean(m["text"])):
                    judg.append(m["text"].strip()); judg_conf = min(judg_conf, m["conf"])
            i = end + 1
            continue
        if RE_JIESHUO.match(t):
            flush_judg()
            state["mode"] = "解说"
            out.append("[解说] （今人意译与解说，不入语料，略）")
            i += 1
            continue
        if state["mode"] == "解说":
            i += 1
            continue
        # 判词：右栏或通栏；段首缩进（x0 比左边距大）另起一段
        if judg and x0 - margin > 40 and x0 < W * 0.5:
            flush_judg()
        judg.append(t); judg_conf = min(judg_conf, l["conf"])
        i += 1
    flush_judg()
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__); return 2
    lo, hi = int(argv[0]), int(argv[1])
    chunks = ["# 《子平真诠评注》附录《人鉴·命理存验》67 例，OCR 自动分段与打标，待校对\n",
              "页码是印刷页码，页图在 source/ziping/pages/p{页}.png。标签：[标题] 例号姓名；[例盘] 四柱 | 大运 | 胎元立命；[判词] 林庚白原判；[解说] 今人意译与解说只留占位。行末括号是 OCR 最低置信度。\n"]
    stats = {"标题": 0, "例盘": 0, "判词": 0, "解说": 0}
    state = {"mode": "判词", "in_table": False}
    for n in range(lo, hi + 1):
        f = OCR / f"p{n:03d}.json"
        if not f.exists():
            chunks.append(f"\n<!-- p{n:03d} 缺 OCR -->\n"); continue
        data = json.loads(f.read_text(encoding="utf-8"))
        chunks.append(f"\n<!-- p{n:03d} -->\n")
        for line in tag_page(data, state):
            stats[line[1:3]] = stats.get(line[1:3], 0) + 1
            chunks.append(line + "\n")
    OUT.write_text("".join(chunks), encoding="utf-8")
    print(OUT, stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
