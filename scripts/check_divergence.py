#!/usr/bin/env python3
"""换盘测试骨架（DESIGN-人物层 10）：两份人物档案的差异度，按溯源编号集合与特质文本两路算。

    python scripts/check_divergence.py 人物/甲.json 人物/乙.json [--threshold 0.6] [--summary]

为什么要有：模型对任何盘都写出差不多的人，即判失败。同一约束换一个盘，或打乱生日的对照盘，两份档案必须真的不一样。
两路：
- 编号路：两份档案引用的溯源编号去掉柱位与具体干支后的"事实种类"集合（如 T-月干-正印 → T-正印，L-6-庚寅-冲提纲 → L-冲提纲，
  NT-驿马-04-时 → NT-驿马-04），算 Jaccard 距离。不去柱位的话两张不同的盘编号天然不同，量不出解读是否真的跟着盘走；
  去了柱位仍高度重合，说明两份档案抓的是同一批事实种类，解读没有随盘变化。
- 文本路：逐段把特质 text 连起来，按字二元组（bigram）集合算 Jaccard 距离，再按段平均；同名段落两两比，缺席的段落记 1（完全不同）。
  另给 difflib 的序列相似度作参考。
差异度 = 两路的平均。阈值 0.65（2026-09-24 对照实验定，references/校核/换盘_对照报告.md：同盘重写 0.56，同一约束的邻盘 0.72，
无关盘 0.87–0.94；取同盘最大与异盘最小的中点再取整。同日六份档案加阶段状态卡后重跑：同盘 0.53、邻盘 0.75、无关盘 0.83–0.89；体用分层后再跑：同盘 0.52、邻盘 0.74、无关盘 0.82–0.88，阈值不动）。
阶段状态段（stages）的特质与其他段落一样计入两路（traits_of）。不给 --threshold 时只报数不判；`--threshold` 不带数用 0.65，带数用给的；低于阈值退出码 1。
两路里编号路是主信号（同盘 0.28、邻盘 0.56、无关盘 0.82 以上），文本路的字二元组距离连同一人物重写都在 0.85，只能拉开一点点，
等有更多档案再考虑换文本度量。
输出一行 JSON：{"divergence", "idDistance", "textDistance", "sections": {段: 文本距离}, "sharedKinds": [...], "threshold", "pass"}。
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
_GANZHI = re.compile(r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]")
_PILLAR = re.compile(r"^(年|月|日|时)(干|支|柱)?$")
RECOMMENDED_THRESHOLD = 0.65


def id_kind(fid: str) -> str:
    """溯源编号 → 事实种类：去掉柱位、岁数、干支、纪年、人名一类随盘而变的段。"""
    parts = fid.split("-")
    head = parts[0]
    if head == "E":  # E-{A}-{B}-{关系}-…：去两个人名，年份段在下面按数字去
        parts = [head] + parts[3:]
    elif head == "Q":  # Q-{年}-{A}[-{B}]-{原因} 或 Q-{年}-{A}-{月序}月-{机制}：只留最后一段
        return f"Q-{parts[-1]}"
    elif head == "J":  # J-{年}-{A}-{B}：交汇本身就是种类
        return "J"
    keep = [head]
    for p in parts[1:]:
        if _PILLAR.match(p) or _GANZHI.fullmatch(p):
            continue
        if p.isdigit() and head in ("L", "D", "E"):
            continue  # 岁数、大运步序、纪年随盘而变；神煞标签的变体号（NT-驿马-04）是事实种类，留
        keep.append(p)
    return "-".join(keep)


def traits_of(sec: dict) -> list[dict]:
    """段落的特质列表；阶段状态段（stages）把各卡的特质摊平，与其他段落同样计入两路。"""
    if "stages" in sec:
        return [t for st in sec.get("stages", []) for t in st.get("traits", [])]
    return sec.get("traits", [])


def kinds(doc: dict) -> set[str]:
    return {id_kind(s) for sec in doc.get("sections", []) for t in traits_of(sec) for s in t.get("sources", [])}


def bigrams(text: str) -> set[str]:
    text = re.sub(r"\s+", "", text)
    return {text[i:i + 2] for i in range(len(text) - 1)} if len(text) > 1 else {text}


def jaccard_distance(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return round(1 - len(a & b) / len(a | b), 4)


def section_texts(doc: dict) -> dict[str, str]:
    return {sec["title"]: "。".join((t.get("text") or "").strip() for t in traits_of(sec)) for sec in doc.get("sections", [])}


def compare(a: dict, b: dict) -> dict:
    ka, kb = kinds(a), kinds(b)
    id_d = jaccard_distance(ka, kb)
    ta, tb = section_texts(a), section_texts(b)
    secs: dict[str, float] = {}
    ratios: list[float] = []
    for title in sorted(set(ta) | set(tb)):
        x, y = ta.get(title), tb.get(title)
        if x is None or y is None or not x or not y:
            secs[title] = 1.0
            continue
        secs[title] = jaccard_distance(bigrams(x), bigrams(y))
        ratios.append(difflib.SequenceMatcher(None, x, y).ratio())
    text_d = round(sum(secs.values()) / len(secs), 4) if secs else 0.0
    seq = round(1 - sum(ratios) / len(ratios), 4) if ratios else None
    return {"divergence": round((id_d + text_d) / 2, 4), "idDistance": id_d, "textDistance": text_d, "sequenceDistance": seq,
            "sections": secs, "sharedKinds": sorted(ka & kb), "kindsA": len(ka), "kindsB": len(kb)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="两份人物档案的差异度（换盘测试）")
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--threshold", type=float, nargs="?", const=RECOMMENDED_THRESHOLD, default=None,
                    help=f"差异度低于此值即失败；不带数用 {RECOMMENDED_THRESHOLD}；不给只报数")
    ap.add_argument("--summary", action="store_true", help="不列共有的事实种类")
    args = ap.parse_args(argv)
    a = json.loads(Path(args.a).read_text(encoding="utf-8"))
    b = json.loads(Path(args.b).read_text(encoding="utf-8"))
    r = compare(a, b)
    r["a"], r["b"] = args.a, args.b
    r["threshold"] = args.threshold
    r["recommended"] = RECOMMENDED_THRESHOLD
    r["pass"] = None if args.threshold is None else r["divergence"] >= args.threshold
    if args.summary:
        r["sharedKinds"] = len(r["sharedKinds"])
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r["pass"] in (None, True) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
