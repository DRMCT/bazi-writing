"""谎言候选：查表层（DESIGN-人物层 1、3：谎言是童年一件具体的事加忌神格局给的候选）。

表在 tables/lies.json（narrative-table/v1，两张分表）：忌神格局一行三到五条候选；童年钉法按六到十二岁年表机制给谎言的形状。
for_chart 从用神档案认格局：method 从强 / 从弱 / 调候各对一行；旺衰中和另加"中和临界"一行；其余按 side 加 bing.family，
身弱且病神兼财与官杀时另加"身弱财杀两旺"。一张盘一到两个格局。
钉法：对六到十二岁逐年跑 timeline.year_facts，机制与钉法表的机制前缀相符即命中（"天克地冲年柱"命中"天克地冲"），同一机制多年只记一条并列出年份；
关键机制以外的（合绊用神、忌神透干）只在年表候选年份里算，否则年年都钉。
编号前缀 LI：LI-{格局}-{序}（候选谎言）、LI-钉-{机制}（钉法）。模型从候选里挑一条改写成这个人的话，sources 引 LI- 加钉事件那年的 L- 编号。
"""

from __future__ import annotations

import json
from pathlib import Path

from . import timeline as _tl

_TABLE_PATH = Path(__file__).resolve().parent / "tables" / "lies.json"
_T = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
_SEC = {s["key"]: s for s in _T["sections"]}
_PATTERNS = {r["pattern"]: r for r in _SEC["patterns"]["rows"]}
_PINS = [r for r in _SEC["pins"]["rows"]]
CHILD_AGES = range(6, 13)


def table() -> dict:
    return _T


def patterns_for(ys: dict, strength: dict | None) -> list[str]:
    method = ys.get("method")
    out: list[str] = []
    if method == "从强":
        out.append("从强候选")
    elif method == "从弱":
        out.append("从弱候选")
    elif method == "调候":
        out.append("调候为用")
    if strength and strength.get("verdict") == "中和":
        out.append("中和临界")
    if method not in ("从强", "从弱"):
        bing = ys.get("bing")
        side = ys.get("side")
        if bing and side in ("身旺", "身弱"):
            fams = {bing["family"]} | {b["family"] for b in bing.get("also", [])}
            if side == "身弱" and {"财", "官杀"} <= fams:
                out.append("身弱财杀两旺")
            name = f"{side}{bing['family']}为病"
            if name in _PATTERNS and name not in out:
                out.append(name)
    return list(dict.fromkeys(out))


def for_chart(chart: dict) -> dict:
    """chart 须已带 fourPillars、gender、calendar、dayun、yongshen、strength。"""
    ys = chart["yongshen"]
    st = chart.get("strength")
    feats: list[dict] = []
    pats = []
    for name in patterns_for(ys, st):
        row = _PATTERNS[name]
        cands = []
        for i, lie in enumerate(row["lies"], 1):
            fid = f"LI-{name}-{i}"
            cands.append({"id": fid, "text": lie})
            feats.append({"id": fid, "kind": "谎言候选", "text": f"{name}：{lie}（他怕的是{row['fear']}）"})
        pats.append({"pattern": name, "how": row["how"], "fear": row["fear"], "tell": row["tell"], "anchors": row["anchors"], "candidates": cands})
    pins: dict[str, dict] = {}
    steps = chart["dayun"]["steps"]
    for age in CHILD_AGES:
        yf = _tl.year_facts(chart, age, ys, steps)
        candidate = _tl._is_candidate(yf)
        for mech in yf["mechanisms"]:
            for row in _PINS:
                if not mech.startswith(row["mechanism"]):
                    continue
                # 合绊用神、忌神透干一类年年可见，只在年表候选年份里才算钉得住
                if not row["mechanism"].startswith(_tl.KEY_MECH) and not candidate:
                    continue
                if True:
                    p = pins.setdefault(row["mechanism"], {"id": f"LI-钉-{row['mechanism']}", "mechanism": row["mechanism"],
                                                            "event": row["event"], "shape": row["shape"], "anchors": row["anchors"], "years": []})
                    p["years"].append({"age": age, "pillar": yf["pillar"], "mechanism": mech, "liunianId": f"L-{age}-{yf['pillar']}-{mech}"})
    for p in pins.values():
        ages = "、".join(f"{y['age']}岁{y['pillar']}" for y in p["years"])
        feats.append({"id": p["id"], "kind": "谎言钉法", "text": f"六到十二岁逢{p['mechanism']}（{ages}）：{p['event']}；孩子的结论：{p['shape']}"})
    return {"patterns": pats, "pins": list(pins.values()), "features": feats,
            "status": "候选与钉法自起草；格局由用神档案认出，钉法年份由年表机制给出", "source": _TABLE_PATH.name}
