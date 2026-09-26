"""群像快照：某一年（可细到流月）所有人的状态与被引动的关系边。

DESIGN 10 第 6 条年度状态卡的事实部分，第 7 条群像推演里"脚本算谁在这个时间点被引动、哪些边被激活"的那一半。
人物怎么互相反应、推几轮、何时收束（回合规则）仍是待定项，由模型按快照写，这里不做。

每人：当年周岁、所处大运与基调、流年干支、机制与领域（timeline.year_facts）、是否换运；给 --months 时另列十二流月
（五虎遁起月，寅月为正月）对命局的冲合刑害，供细纲的场景节拍用。
被引动的边 A→B（原因可多条）：
- 同年引动：两人当年都有关键机制（冲提纲、冲日支、天克地冲、伏吟、岁运并临、岁运相冲、换运）；
- 五行临身：流年天干五行正是 B 的日主五行，而它在 A 是用神或忌神（这一年 B 在 A 眼里分量变重）；
- 岁运同步：矩阵的同步忌运或顺逆段覆盖当年；
- 日柱引动：两人日支本有冲合刑害，流年地支正是其中一方的日支。
编号前缀 Q：Q-{年}-{A}（人的状态）、Q-{年}-{A}-{B}-{原因}（边）、Q-{年}-{A}-{月序}月-{机制}（流月）。

命令行（在作者项目根下）：
    python -m bazi_core.ensemble 命盘/沈砚.json 命盘/林昭.json --year 330 [--months] > 命盘/群像/330.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import matrix as matrix_mod
from . import relations as R
from . import timeline as timeline_mod
from . import yongshen as yongshen_mod
from .shishen import BRANCHES, STEMS, WUXING, element_of

SCHEMA = "bazi-ensemble/v1"
_KEYS = ("year", "month", "day", "hour")
_CN = {"year": "年", "month": "月", "day": "日", "hour": "时"}


def month_pillars(year_pillar: str) -> list[str]:
    """流年十二流月：五虎遁，寅月起。"""
    ys = STEMS.index(year_pillar[0])
    first = ((ys % 5) * 2 + 2) % 10
    return [STEMS[(first + i) % 10] + BRANCHES[(2 + i) % 12] for i in range(12)]


def _month_mechs(pillars: dict, mp: str) -> list[str]:
    tr = R.transit_relations(pillars, mp)
    out = list(tr["flags"])
    for k in _KEYS:
        h = tr["byPillar"].get(k)
        if not h:
            continue
        for rel in h["branches"]:
            if rel == "六合":
                out.append(f"合{_CN[k]}支")
            elif rel in ("刑", "害") and k == "day":
                out.append(f"{rel}日支")
    return list(dict.fromkeys(out))


def snapshot(charts: list[dict], year: int, months: bool = False) -> dict:
    m = matrix_mod.build(charts)
    nodes = {c["name"]: matrix_mod._node(c) for c in charts}
    people = []
    state: dict[str, dict] = {}
    feats: list[dict] = []
    for c in charts:
        name = c["name"]
        by = matrix_mod._anchor(c)
        if by is None:
            raise ValueError(f"{name} 没有纪年锚（现实历出生年或架空历 --epoch），不能按年对齐")
        age = year - by
        if age < 0:
            people.append({"name": name, "age": age, "born": False})
            continue
        ys = c.get("yongshen") or yongshen_mod.determine(c["fourPillars"])
        yf = timeline_mod.year_facts(c, age, ys, c["dayun"]["steps"])
        key = [x for x in yf["mechanisms"] if x.startswith(timeline_mod.KEY_MECH)]
        tone = None
        if yf["dayun"]:
            sc = next((s["score"] for s in nodes[name]["steps"] if s["pillar"] == yf["dayun"]["pillar"] and s["startAge"] == yf["dayun"]["startAge"]), 0)
            tone = "顺" if sc > 0 else "逆" if sc < 0 else "平"
        item = {"name": name, "age": age, "born": True, "liunian": yf["pillar"], "dayun": yf["dayun"], "dayunTone": tone,
                "score": yf["score"], "mechanisms": yf["mechanisms"], "keyMechanisms": key, "domains": yf["domains"],
                "shensha": yf["shensha"], "yong": ys["yong"]}
        if months:
            item["months"] = [{"order": i + 1, "pillar": mp, "mechanisms": _month_mechs(c["fourPillars"], mp)}
                              for i, mp in enumerate(month_pillars(yf["pillar"]))]
            for mo in item["months"]:
                for mech in mo["mechanisms"]:
                    feats.append({"id": f"Q-{year}-{name}-{mo['order']}月-{mech}", "text": f"{year}年第{mo['order']}月（{mo['pillar']}）{name}{mech}"})
        people.append(item)
        state[name] = {**item, "roles": ys["roles"], "pillars": c["fourPillars"]}
        dom = "、".join(d["domain"] for d in yf["domains"]) or "无"
        feats.append({"id": f"Q-{year}-{name}", "text": f"{year}年{name}{age}岁，流年{yf['pillar']}，大运{yf['dayun']['pillar'] if yf['dayun'] else '未起运'}（{tone or '—'}），"
                                                     f"机制{'、'.join(yf['mechanisms']) or '无'}，动{dom}"})

    edges = []
    for e in m["edges"]:
        a, b = e["from"], e["to"]
        if a not in state or b not in state:
            continue
        A, B = state[a], state[b]
        reasons = []
        if A["keyMechanisms"] and B["keyMechanisms"]:
            reasons.append(("同年引动", f"{a}{'、'.join(A['keyMechanisms'])}；{b}{'、'.join(B['keyMechanisms'])}"))
        ln_el = WUXING[element_of(STEMS.index(A["liunian"][0]))]
        b_el = nodes[b]["dayElement"]
        role = A["roles"][b_el]
        if ln_el == b_el and role in ("用", "忌"):
            reasons.append(("五行临身", f"流年{A['liunian'][0]}{ln_el}正是{b}的日主五行，在{a}为{role}神"))
        for s in e["syncJi"]:
            if s["from"] <= year <= s["to"]:
                reasons.append(("同步忌运", f"{s['from']}–{s['to']}年两人同在忌运"))
        for s in e["aUpBDown"]:
            if s["from"] <= year <= s["to"]:
                reasons.append(("顺逆", f"{s['from']}–{s['to']}年{a}顺而{b}逆"))
        da, db = A["pillars"]["day"][1], B["pillars"]["day"][1]
        rel = R.branch_pair(da, db)
        if rel and A["liunian"][1] in (da, db):
            reasons.append(("日柱引动", f"两人日支{da}{db}{'、'.join(rel)}，流年支{A['liunian'][1]}引动"))
        if not reasons:
            continue
        ids = []
        for kind, text in reasons:
            fid = f"Q-{year}-{a}-{b}-{kind}"
            ids.append(fid)
            feats.append({"id": fid, "text": f"{year}年{a}→{b}：{text}"})
        edges.append({"from": a, "to": b, "tenGod": e["tenGod"], "reasons": [{"kind": k, "text": t} for k, t in reasons],
                      "ids": ids, "matrixIds": [f["id"] for f in e["features"]]})
    return {"schema": SCHEMA, "algorithm": "bazi-writing ensemble v1（DESIGN 10 第 6–7 条的事实部分）", "year": year,
            "people": people, "edges": edges, "features": feats}


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="几张命盘档案 + 纪年 → 群像快照（每人状态、被引动的边、可选流月）")
    ap.add_argument("charts", nargs="+")
    ap.add_argument("--year", type=int, required=True, help="故事纪年（现实历为公历年）")
    ap.add_argument("--months", action="store_true", help="另列十二流月的冲合")
    a = ap.parse_args(argv)
    charts = [json.loads(Path(p).read_text(encoding="utf-8")) for p in a.charts]
    out = snapshot(charts, a.year, a.months)
    sys.stdout.buffer.write((json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
