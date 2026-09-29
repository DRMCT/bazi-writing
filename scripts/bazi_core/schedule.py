"""配角日程与交汇点（DESIGN-戏剧层 7.3、DESIGN-人物层 3"配角自有日程"）：几个角色在同一段故事年份里各自经历什么，哪几年交汇。

每年跑一次群像快照（ensemble.snapshot）：每人当年的岁数、流年、大运基调、关键机制、领域、是否候选年份（timeline._is_candidate），
以及被引动的边。交汇点：某一年的边有当年才有的引动原因（同年引动、五行临身、日柱引动）且两端至少一人是候选年份，
或两人同年都是候选年份；只靠同步忌运、顺逆这种十年一段的底色不算，否则忌运段里每个候选年份都成交汇，挑不出来。
给了 --main 时只看与主角相连的边。同一年同一对人只记一条，原因并列。
输出：
- people：每人逐年的日程行（配角在主线之外同期经历什么，从这里读）；
- grid：按年并排的同期表；
- intersections：交汇点，编号 J-{年}-{A}-{B}，text 里写清双方当年的机制与边的原因；check-character.js 加 --schedule 读。
日程行本身不产生编号（各自年表已有 L- 编号），只有交汇点带 J- 编号。

命令行（在作者项目根下）：
    python -m bazi_core.schedule 命盘/沈砚.json 命盘/林昭.json --window 320 345 [--main 沈砚] > 命盘/日程.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import ensemble as _en
from . import matrix as _mx
from . import timeline as _tl

SCHEMA = "bazi-schedule/v1"
SPECIFIC_KINDS = frozenset({"同年引动", "五行临身", "日柱引动"})  # 当年才有的引动原因；同步忌运、顺逆是十年一段的底色


def _row(p: dict) -> dict:
    if not p.get("born"):
        return {"name": p["name"], "age": p["age"], "born": False}
    cand = _tl._is_candidate({"mechanisms": p["mechanisms"]})
    return {"name": p["name"], "age": p["age"], "born": True, "liunian": p["liunian"],
            "dayun": p["dayun"]["pillar"] if p["dayun"] else None, "dayunTone": p["dayunTone"],
            "score": p["score"], "keyMechanisms": p["keyMechanisms"], "mechanisms": p["mechanisms"],
            "domains": [d["domain"] for d in p["domains"]], "candidate": cand, "stateId": f"Q-{p['year']}-{p['name']}" if "year" in p else None}


def build(charts: list[dict], window: tuple[int, int], main: str | None = None) -> dict:
    names = [c.get("name") for c in charts]
    if None in names or len(set(names)) != len(names):
        raise ValueError("每张命盘都要有不重复的 name")
    if main is not None and main not in names:
        raise ValueError(f"--main {main} 不在给的命盘里")
    for c in charts:
        if _mx._anchor(c) is None:
            raise ValueError(f"{c['name']} 没有纪年锚（现实历出生年或架空历 --epoch）")
    a, b = window
    people = {n: {"name": n, "birthYear": _mx._anchor(c), "rows": []} for n, c in zip(names, charts)}
    grid = []
    inters = []
    feats = []
    for year in range(a, b + 1):
        snap = _en.snapshot(charts, year)
        rows = {}
        for p in snap["people"]:
            r = _row({**p, "year": year})
            r["year"] = year
            people[p["name"]]["rows"].append(r)
            rows[p["name"]] = r
        grid.append({"year": year, "people": [rows[n] for n in names]})
        seen: set[tuple[str, str]] = set()
        for e in snap["edges"]:
            A, B = e["from"], e["to"]
            if main is not None and main not in (A, B):
                continue
            key = tuple(sorted((A, B)))
            if key in seen:
                continue
            ra, rb = rows[A], rows[B]
            # 两个方向的边原因并列
            reasons, kinds = [], set()
            for e2 in snap["edges"]:
                if {e2["from"], e2["to"]} == set(key):
                    for r in e2["reasons"]:
                        kinds.add(r["kind"])
                        t = f"{e2['from']}→{e2['to']}：{r['text']}"
                        if t not in reasons:
                            reasons.append(t)
            # 同步忌运、顺逆是十年一段的底色，单靠它们加一个人的候选年份不算交汇；要有当年才有的原因，或两人同年都是候选
            specific = bool(kinds & SPECIFIC_KINDS)
            both = bool(ra.get("candidate") and rb.get("candidate"))
            if not ((specific and (ra.get("candidate") or rb.get("candidate"))) or both):
                continue
            seen.add(key)
            fid = f"J-{year}-{key[0]}-{key[1]}"
            who = [n for n in key if rows[n].get("candidate")]
            text = (f"{year}年{key[0]}与{key[1]}交汇：" + "；".join(
                f"{n}{rows[n]['age']}岁流年{rows[n]['liunian']}{'（候选年份，' + '、'.join(rows[n]['keyMechanisms']) + '）' if rows[n].get('candidate') else ''}"
                for n in key) + "｜" + "；".join(reasons))
            inters.append({"id": fid, "year": year, "people": list(key), "eventful": who, "reasons": reasons,
                           "snapshotIds": [i for e2 in snap["edges"] if {e2["from"], e2["to"]} == set(key) for i in e2["ids"]],
                           "domains": {n: rows[n]["domains"] for n in key}})
            feats.append({"id": fid, "text": text})
    return {"schema": SCHEMA, "algorithm": "bazi-writing schedule v1（DESIGN-戏剧层 7.3）", "window": [a, b], "main": main,
            "people": [people[n] for n in names], "grid": grid, "intersections": inters, "features": feats}


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="几张命盘档案 + 故事年份段 → 配角日程与交汇点")
    ap.add_argument("charts", nargs="+")
    ap.add_argument("--window", type=int, nargs=2, required=True, metavar=("起", "止"), help="故事纪年段，含两端")
    ap.add_argument("--main", default=None, help="主角名，只看与主角相连的交汇")
    a = ap.parse_args(argv)
    if len(a.charts) < 2:
        ap.error("至少两张命盘")
    charts = [json.loads(Path(p).read_text(encoding="utf-8")) for p in a.charts]
    out = build(charts, (a.window[0], a.window[1]), a.main)
    sys.stdout.buffer.write((json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
