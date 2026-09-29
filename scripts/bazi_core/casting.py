"""编配候选（DESIGN-戏剧层 4）：几张命盘 → 每对人的张力与牵绊，谁是主动的一头。给写编配表的人当材料，不替他定。

矩阵给的是一条一条有向边；这里把一对人的两条边并起来看戏：
- 同求：两人互看比肩、劫财，要的是同一样东西。
- 压与受：一头看另一头是官杀，另一头看他是财。
- 用忌相反：一头需要对方，对方受不了他；互为忌仇是互相受不了；互为用喜是同盟，没有戏，只记牵绊。
- 日柱：天克地冲、六冲、刑、害是撞；六合是拴。
- 顺逆交错：故事窗里一顺一逆的年数，两人对同一件事记的账不一样；同步忌运是一起在低处，算牵绊。
张力分与牵绊分各自相加。只有张力没有牵绊的一对，撞一回就散了；只有牵绊没有张力的一对是同盟。好的对子两样都有。
主动：身旺记一分，透干里有七杀、伤官、劫财各记一分；一对人里分高的是主动的一头，同分写无。

不产生编号，reasons 里的 ids 都是矩阵的 E- 编号。
命令行（在作者项目根下）：
    python -m bazi_core.casting 命盘/甲.json 命盘/乙.json … --window 2003 2023 > 命盘/群像/编配候选.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import matrix as _mx
from .shishen import STEMS, ten_god

SCHEMA = "bazi-casting-candidates/v1"
SAME = ("比肩", "劫财")
PRESS = ("正官", "七杀")
NEAR = ("用", "喜")
AWAY = ("忌", "仇")
CLASH = {"天克地冲": 3, "六冲": 3, "刑": 2, "自刑": 2, "害": 1}
DRIVE_GODS = ("七杀", "伤官", "劫财")


def initiative(chart: dict) -> dict:
    p = chart["fourPillars"]
    ds = STEMS.index(p["day"][0])
    exposed = [ten_god(ds, STEMS.index(p[k][0])) for k in ("year", "month", "hour") if p.get(k)]
    verdict = (chart.get("strength") or {}).get("verdict")
    why = []
    if verdict == "身旺":
        why.append("身旺")
    why += [f"透{g}" for g in dict.fromkeys(exposed) if g in DRIVE_GODS]
    return {"score": len(why), "why": why}


def _years(spans: list[dict], window: tuple[int, int]) -> int:
    a, b = window
    return sum(max(0, min(s["to"], b) - max(s["from"], a) + 1) for s in spans)


def pair(ab: dict, ba: dict, window: tuple[int, int]) -> dict:
    A, B = ab["from"], ab["to"]
    tension: list[dict] = []
    bond: list[dict] = []

    def t(points: float, text: str, ids: list[str]) -> None:
        tension.append({"points": points, "text": text, "ids": ids})

    def b(points: float, text: str, ids: list[str]) -> None:
        bond.append({"points": points, "text": text, "ids": ids})

    ga, gb = ab["tenGod"], ba["tenGod"]
    ida, idb = f"E-{A}-{B}-十神-{ga}", f"E-{B}-{A}-十神-{gb}"
    if ga in SAME and gb in SAME:
        t(3, f"同求：{A}看{B}为{ga}，{B}看{A}为{gb}，要的是同一样东西", [ida, idb])
    for x, y, g, i in ((A, B, ga, ida), (B, A, gb, idb)):
        if g in PRESS:
            t(2, f"压与受：{x}看{y}为{g}，压力从{y}那头来", [i])
        if g in ("正印", "偏印", "食神"):
            b(1, f"{x}看{y}为{g}，{'靠着' if '印' in g else '护着'}对方", [i])
    ra, rb = ab["yongji"]["role"][0], ba["yongji"]["role"][0]
    ja, jb = f"E-{A}-{B}-用忌-{ra}", f"E-{B}-{A}-用忌-{rb}"
    if ra in NEAR and rb in AWAY:
        t(2, f"用忌相反：{B}是{A}需要的，{A}却是{B}受不了的", [ja, jb])
        b(1, f"{A}离不开{B}", [ja])
    elif rb in NEAR and ra in AWAY:
        t(2, f"用忌相反：{A}是{B}需要的，{B}却是{A}受不了的", [ja, jb])
        b(1, f"{B}离不开{A}", [jb])
    elif ra in AWAY and rb in AWAY:
        t(2, "互相受不了", [ja, jb])
    elif ra in NEAR and rb in NEAR:
        b(2, "互相需要，是同盟", [ja, jb])
    dp = ab["dayPillar"]
    for rel in dp["tags"] + dp["branches"]:
        rid = [f"E-{A}-{B}-日柱-{rel}"]
        if rel == "六冲" and "天克地冲" in dp["tags"]:
            continue  # 天克地冲已含地支相冲，不重复记
        if rel in CLASH:
            t(CLASH[rel], f"日柱{rel}，一碰就是当场的事", rid)
        elif rel == "六合":
            b(2, "日柱六合，拴得住，分不干净", rid)
    if dp["stem"] == "合":
        b(1, "日干相合，黏得住", [f"E-{A}-{B}-日柱-天干合"])
    n_up = _years(ab["aUpBDown"], window)
    n_down = _years(ba["aUpBDown"], window)
    span = window[1] - window[0] + 1
    if n_up + n_down:
        ids = [f"E-{A}-{B}-顺逆-{s['from']}-{s['to']}" for s in ab["aUpBDown"] if s["to"] >= window[0] and s["from"] <= window[1]]
        ids += [f"E-{B}-{A}-顺逆-{s['from']}-{s['to']}" for s in ba["aUpBDown"] if s["to"] >= window[0] and s["from"] <= window[1]]
        t(round(2 * (n_up + n_down) / span, 1), f"顺逆交错：窗内{A}顺{B}逆 {n_up} 年，{B}顺{A}逆 {n_down} 年，同一件事两本账", ids)
    n_sync = _years(ab["syncJi"], window)
    if round(n_sync / span, 1) > 0:
        ids = [f"E-{A}-{B}-同步忌运-{s['from']}-{s['to']}" for s in ab["syncJi"] if s["to"] >= window[0] and s["from"] <= window[1]]
        b(round(n_sync / span, 1), f"窗内 {n_sync} 年一起在低处，抱团或互相拖", ids)
    ts, bs = round(sum(x["points"] for x in tension), 1), round(sum(x["points"] for x in bond), 1)
    if ts >= 5 and bs >= 1:
        kind = "对子"
    elif ts >= 5:
        kind = "只撞不拴"
    elif bs >= 2:
        kind = "同盟"
    else:
        kind = "淡"
    return {"people": [A, B], "tension": ts, "bond": bs, "kind": kind,
            "sameWant": ga in SAME and gb in SAME, "tensionWhy": tension, "bondWhy": bond}


def build(charts: list[dict], window: tuple[int, int]) -> dict:
    m = _mx.build(charts)
    edges = {(e["from"], e["to"]): e for e in m["edges"]}
    names = [c["name"] for c in charts]
    ini = {c["name"]: initiative(c) for c in charts}
    pairs = []
    for i, A in enumerate(names):
        for B in names[i + 1:]:
            p = pair(edges[(A, B)], edges[(B, A)], window)
            sa, sb = ini[A]["score"], ini[B]["score"]
            p["active"] = A if sa > sb else B if sb > sa else None
            pairs.append(p)
    pairs.sort(key=lambda p: (-(p["kind"] == "对子"), -p["tension"], -p["bond"], names.index(p["people"][0])))
    return {"schema": SCHEMA, "algorithm": "bazi-writing casting v1（DESIGN-戏剧层 4）", "window": list(window), "people": names,
            "initiative": ini, "pairs": pairs,
            "note": "候选，不是结论。主线挑对子里张力最高、又合这本书的一问的那一对；只撞不拴的一对要在编配表里另给一样拴住他们的东西（同一间屋、一纸约、一笔钱），给不出就不做主线。"}


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="几张命盘 → 编配候选：每对人的张力与牵绊")
    ap.add_argument("charts", nargs="+")
    ap.add_argument("--window", type=int, nargs=2, required=True, metavar=("起", "止"))
    a = ap.parse_args(argv)
    if len(a.charts) < 2:
        ap.error("至少两张命盘")
    charts = [json.loads(Path(p).read_text(encoding="utf-8")) for p in a.charts]
    out = build(charts, (a.window[0], a.window[1]))
    sys.stdout.buffer.write((json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
