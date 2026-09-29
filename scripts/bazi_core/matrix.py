"""多人矩阵（DESIGN-命盘层 6）：几张命盘档案 → 有向邻接表，每条边带溯源编号。

每条有向边 A→B：
- 十神：A 的日主看 B 的日主是什么十神（"他眼里的我"反过来就是 B→A 那条边）；
- 日柱：两人日柱之间的天干关系（合、克……）、地支关系（六合、六冲、刑、害）、伏吟与天克地冲（对称，两条边都记）；
- 用忌：B 的日主五行在 A 的五神里是什么（用、喜、闲、忌、仇），A 的用神是 B 的日主五行即"B 是 A 的用神之人"；
- 岁运同步：两人都有纪年锚（现实历出生年，或架空历 storyEpochBirthYear）时，逐年看两人所处大运的顺逆分，
  两人同在忌运（分数 < 0）的连续年份记"同步忌运"，A 顺 B 逆记"A 顺 B 逆"。起运前记 0，不算忌。

矩阵是作者本，放 命盘/ 下；映射到某套装的关系类型是导出器的事。编号前缀 E：
E-{A}-{B}-十神-{X}、E-{A}-{B}-日柱-{关系}、E-{A}-{B}-用忌-{角色}、E-{A}-{B}-同步忌运-{起}-{止}、E-{A}-{B}-顺逆-{起}-{止}。
人物档案里"他人眼中的他"一类特质可引这些编号，check-character.js 加 --matrix 读。

命令行（在作者项目根下）：
    python -m bazi_core.matrix 命盘/沈砚.json 命盘/林昭.json [--span 80] > 命盘/矩阵.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import arc as arc_mod
from . import relations as R
from . import yongshen as yongshen_mod
from .shishen import STEMS, WUXING, element_of, ten_god

_RT = json.loads((Path(__file__).resolve().parent / "tables" / "response_tendency.json").read_text(encoding="utf-8"))
_ROWS = {r["tenGod"]: r for r in _RT["rows"]}


def draft(A: str, B: str, g: str, role: str, pp: dict, da: str, db: str, sync: list[dict], split: list[dict]) -> tuple[str, list[str]]:
    """边的注释草稿（DESIGN-命盘层 6，2026-09-24-11）：A 眼里的 B。回应倾向表给这条边上 B 对 A 是什么、A 需要还是受不了、偏向哪边；
    日柱与岁运同步照事实写。模型改写进人物档案"他人眼中的他"，引 draftIds。"""
    row = _ROWS[g]
    ids = [f"E-{A}-{B}-十神-{g}", f"E-{A}-{B}-用忌-{role[0]}"]
    parts = [f"{A}看{B}为{g}：{row['carries'].replace('源', B)}"]
    if role in ("用", "喜"):
        parts.append(f"{B}是{A}需要的（{role}神），回应偏靠近：{row['near'].replace('源', B)}")
    elif role in ("忌", "仇"):
        parts.append(f"{B}是{A}受不了的（{role}神），回应偏躲或压：{row['away'].replace('源', B)}")
    else:
        parts.append(f"{B}在{A}是闲神，看着不动，回应在{row['between']}之间取中")
    if pp["stem"] in ("克", "被克", "合"):
        parts.append({"克": f"日干{da[0]}克{db[0]}，{A}对{B}带指挥味", "被克": f"日干{da[0]}受{db[0]}之克，{A}对{B}带受制味",
                      "合": f"日干{da[0]}与{db[0]}相合，两人黏得住"}[pp["stem"]])
        ids.append(f"E-{A}-{B}-日柱-天干{pp['stem']}")
    for rel in pp["branches"] + pp["tags"]:
        parts.append(f"日柱{da}与{db}{rel}" + ("，回应烈一档，当场发作" if rel == "六冲" else "，回应软一档，事后才动" if rel == "六合" else ""))
        ids.append(f"E-{A}-{B}-日柱-{rel}")
    if sync:
        parts.append("；".join(f"{s['from']}–{s['to']}年两人同在忌运，抱团或互相拖累" for s in sync))
        ids += [f"E-{A}-{B}-同步忌运-{s['from']}-{s['to']}" for s in sync]
    if split:
        parts.append("；".join(f"{s['from']}–{s['to']}年{A}顺{B}逆，{A}有余力，写成施与或俯视" for s in split))
        ids += [f"E-{A}-{B}-顺逆-{s['from']}-{s['to']}" for s in split]
    return "。".join(parts).replace("。。", "。") + "。", ids

SCHEMA = "bazi-matrix/v1"


def _anchor(chart: dict) -> int | None:
    cal = chart.get("calendar") or {}
    if cal.get("mode") == "real" and cal.get("birthLocal"):
        return datetime.fromisoformat(cal["birthLocal"]).year
    if cal.get("mode") == "fictional":
        return cal.get("storyEpochBirthYear")
    return None


def _node(chart: dict) -> dict:
    p = chart["fourPillars"]
    ys = chart.get("yongshen") or yongshen_mod.determine(p)
    scores = chart.get("dayunScores") or [
        {"sequence": s["sequence"], "pillar": s["pillar"], "score": s["score"]}
        for s in arc_mod.dayun_scores(p, chart["dayun"]["steps"], ys)]
    by_seq = {s["sequence"]: s["score"] for s in scores}
    steps = [{"pillar": s["pillar"], "startAge": s["startAge"], "endAge": s["endAge"], "score": by_seq[s["sequence"]]}
             for s in chart["dayun"]["steps"]]
    return {"name": chart.get("name"), "pillars": p, "dayMaster": p["day"][0],
            "dayElement": WUXING[element_of(STEMS.index(p["day"][0]))],
            "yong": ys["yong"], "roles": ys["roles"], "birthYear": _anchor(chart), "steps": steps}


def _score_at(node: dict, year: int) -> float:
    age = year - node["birthYear"]
    for s in node["steps"]:
        if s["startAge"] <= age < s["endAge"]:
            return s["score"]
    return 0.0


def _runs(years: list[int]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for y in years:
        if out and y == out[-1][1] + 1:
            out[-1] = (out[-1][0], y)
        else:
            out.append((y, y))
    return out


def edge(a: dict, b: dict, span: int = 80) -> dict:
    A, B = a["name"], b["name"]
    feats: list[dict] = []

    def add(fid: str, text: str) -> None:
        feats.append({"id": f"E-{A}-{B}-{fid}", "text": text})

    g = ten_god(STEMS.index(a["dayMaster"]), STEMS.index(b["dayMaster"]))
    add(f"十神-{g}", f"{A}看{B}为{g}")
    pp = R.pillar_pair(a["pillars"]["day"], b["pillars"]["day"])
    da, db = a["pillars"]["day"], b["pillars"]["day"]
    stem_text = {"合": f"{A}日干{da[0]}与{B}日干{db[0]}相合", "克": f"{A}日干{da[0]}克{B}日干{db[0]}",
                 "被克": f"{A}日干{da[0]}受{B}日干{db[0]}之克"}
    if pp["stem"] in stem_text:
        add(f"日柱-天干{pp['stem']}", stem_text[pp["stem"]])
    for rel in pp["branches"] + pp["tags"]:
        add(f"日柱-{rel}", f"{A}日柱{da}与{B}日柱{db}{rel}")
    role = a["roles"][b["dayElement"]]
    add(f"用忌-{role[0]}", f"{B}的日主{b['dayElement']}是{A}的{role}神" if len(role) == 1 else f"{B}的日主{b['dayElement']}在{A}是闲神（{role[2:4]}）")
    sync, split = [], []
    if a["birthYear"] is not None and b["birthYear"] is not None:
        y0 = max(a["birthYear"], b["birthYear"])
        y1 = min(a["birthYear"], b["birthYear"]) + span
        both, a_up = [], []
        for y in range(y0, y1 + 1):
            sa, sb = _score_at(a, y), _score_at(b, y)
            if sa < 0 and sb < 0:
                both.append(y)
            if sa > 0 and sb < 0:
                a_up.append(y)
        for s, e in _runs(both):
            sync.append({"from": s, "to": e})
            add(f"同步忌运-{s}-{e}", f"{s}–{e}年{A}与{B}同在忌运")
        for s, e in _runs(a_up):
            split.append({"from": s, "to": e})
            add(f"顺逆-{s}-{e}", f"{s}–{e}年{A}行顺运而{B}行忌运")
    text, dids = draft(A, B, g, role, pp, da, db, sync, split)
    return {
        "from": A, "to": B,
        "tenGod": g,
        "draft": text, "draftIds": dids,
        "dayPillar": {"stem": pp["stem"], "branches": pp["branches"], "tags": pp["tags"]},
        "yongji": {"role": role, "isYong": role == "用", "isJi": role in ("忌", "仇")},
        "syncJi": sync, "aUpBDown": split,
        "features": feats,
    }


def build(charts: list[dict], span: int = 80) -> dict:
    nodes = [_node(c) for c in charts]
    names = [n["name"] for n in nodes]
    if None in names or len(set(names)) != len(names):
        raise ValueError("每张命盘都要有不重复的 name（chart --name）")
    edges = [edge(a, b, span) for a in nodes for b in nodes if a is not b]
    feats = [f for e in edges for f in e["features"]]
    ids = [f["id"] for f in feats]
    if len(ids) != len(set(ids)):
        raise ValueError("矩阵编号重复")
    return {"schema": SCHEMA, "algorithm": "bazi-writing matrix v1（DESIGN-命盘层 6）",
            "nodes": [{k: v for k, v in n.items() if k != "steps"} for n in nodes],
            "edges": edges, "features": feats}


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="几张命盘档案 → 多人矩阵")
    ap.add_argument("charts", nargs="+", help="命盘档案 JSON，至少两张")
    ap.add_argument("--span", type=int, default=80, help="岁运同步看到年长者出生后多少年")
    a = ap.parse_args(argv)
    if len(a.charts) < 2:
        ap.error("至少两张命盘")
    charts = [json.loads(Path(p).read_text(encoding="utf-8")) for p in a.charts]
    out = build(charts, a.span)
    sys.stdout.buffer.write((json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
