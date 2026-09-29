"""群像推演：事件卡与悬置线程（DESIGN 17 已定项 2026-09-24-11，第 10 节第 7 条）。

事件是共享的，两难是各人的。不做"谁先动、轮流回应、推几轮"的回合模型：每个热年一张事件卡，脚本把在场的人、
各人的赌注、各人的回应倾向、旧账一次算全，模型对着一张卡写这一年的事件链，几轮由叙事定，脚本不数。

规则（与 DESIGN 17 逐条对应）：
1. 热年由交汇点定（schedule.build 的收紧规则：边有当年才有的原因，且两端至少一人是候选年份）。没有交汇点的年份是过场，
   连续的过场记进 gaps，大纲里合成一句时间跳跃。
2. 事件源是交汇点里主机制烈度最高的人（dilemma.PRIORITY），同分主角先；事件直接取他那一年的两难草稿（dilemma.rewrite_year）。
3. 在场的人：与事件源同在交汇点的人，加上当年对任一在场者有五行临身的人。人数由边定，不设轮数。
4. 各人的赌注取当年领域权重（timeline.year_facts 的 domains.weight）。当年没有领域在动的人只按画像反应，不生新事件。
5. 回应倾向查 tables/response_tendency.json：他看事件源的十神边乘用忌，喜用取靠近、忌仇取躲或压、闲取看；修正项按矩阵边与快照的事实判。
6. 悬置线程读作者维护的 群像/线程.json（bazi-threads/v1）：状态悬置的线程，当年该对边再成交汇点、或任一方候选年份触及同一领域时重新上卡；
   任一方换运的年份标改写；了结的不再上卡。每张卡另给 openThread 建议，作者写完卡认为两难没解决就把它抄进线程文件。
7. 投影：卷按主角的大运切（volumes），配角换运年成卷内转折；热年成情节段（segments）；作者挑的热年给 --months 出流月，供细纲。

编号：沿用 Q-（快照）、E-（矩阵）、L-（年表）、J-（日程）、D-（大运基调）；新加 TH-{起始年}-{A}-{B}-{领域}（线程）。
顶层 idPool 列出全部可引编号，check-character.js --run 读它；模型写的事件链（人物/推演.md）用 --check-chain 核对每条溯源都在池里。

命令行（在作者项目根下）：
    python -m bazi_core.ensemble_run 命盘/沈砚.json 命盘/林昭.json 命盘/裴恪.json --window 324 346 --main 林昭 \
        [--threads 命盘/群像/线程.json] [--months] > 命盘/群像/推演.json
    python -m bazi_core.ensemble_run --check-chain 人物/推演.md --run 命盘/群像/推演.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import dilemma as _dl
from . import ensemble as _en
from . import yunqi as yunqi_mod
from . import matrix as _mx
from . import schedule as _sc
from . import timeline as _tl
from . import yongshen as yongshen_mod

SCHEMA = "bazi-ensemble-run/v1"
THREADS_SCHEMA = "bazi-threads/v1"
THREADS_SCHEMAS = ("bazi-threads/v1", "bazi-threads/v2")
# v1 两态；v2 四态（DESIGN-戏剧层 4.4）：埋、压、响、余波。悬置读作压，了结读作余波，两套词一个文件里可以混用
THREAD_STATUS = ("悬置", "了结", "埋", "压", "响", "余波")
THREAD_OPEN = ("悬置", "埋", "压", "响")
ESCALATE_AT = 3  # 一条线开出以后第三回上卡，该升级或清算了
CASTING_SCHEMA = "bazi-casting/v1"
LINE_BONUS = {"主线": 6, "副线": 3, "旁线": 0}
_BODY_HITS = ("天克地冲日柱", "冲日支")
_TABLE_PATH = Path(__file__).resolve().parent / "tables" / "response_tendency.json"
_T = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
ROWS = {r["tenGod"]: r for r in _T["rows"]}
MODS = {m["条件"]: m for m in _T["modifiers"]}
NEAR_ROLES = ("用", "喜")
AWAY_ROLES = ("忌", "仇")
_ID_PREFIX = re.compile(r"^(?:P|DM|T|H|G|S|U|Y|R|N|NT|C|D|L|IN|IM|LI|YQ|E|Q|J|TH)-\S+$")  # 命盘各节、矩阵、年表、日程、快照、线程


def _rank(mechs: list[str]) -> int:
    pm = _dl.primary_mechanism(mechs)
    return len(_dl.PRIORITY) if pm is None else _dl.PRIORITY.index(pm[0])


def _covers(spans: list[dict], year: int) -> dict | None:
    return next((s for s in spans if s["from"] <= year <= s["to"]), None)


def load_threads(doc: dict | None) -> list[dict]:
    if not doc:
        return []
    if doc.get("schema") not in THREADS_SCHEMAS:
        raise ValueError(f"线程文件 schema 应为 {' 或 '.join(THREADS_SCHEMAS)}")
    out = []
    for t in doc.get("threads", []):
        for k in ("id", "people", "domain", "since", "status"):
            if k not in t:
                raise ValueError(f"线程缺字段 {k}：{t}")
        if t["status"] not in THREAD_STATUS:
            raise ValueError(f"线程 {t['id']} 状态只能是 {'、'.join(THREAD_STATUS)}")
        if len(t["people"]) != 2:
            raise ValueError(f"线程 {t['id']} 的 people 要两个人")
        plan = t.get("plan")
        if plan is not None and not (isinstance(plan, dict) and (isinstance(plan.get("year"), int) or plan.get("mute"))):
            raise ValueError(f"线程 {t['id']} 的 plan 写哪一年响（year），或写留哑的理由（mute）")
        if t.get("open") not in (None, "明", "暗"):
            raise ValueError(f"线程 {t['id']} 的 open 只能是 明 或 暗")
        for k in t.get("knows", []):
            if not (isinstance(k, dict) and k.get("who") and isinstance(k.get("since"), int)):
                raise ValueError(f"线程 {t['id']} 的 knows 每条要 who 与 since（哪一年知道的）")
        out.append(t)
    return out


def load_casting(doc: dict | None, names: list[str]) -> dict | None:
    """编配的机器本（DESIGN-戏剧层 4.1、5.2、5.3）：主线一对、副线几对（长篇三到五条线，至多六对）、背景的人、领域配权。人话在 人物/编配.md。"""
    if not doc:
        return None
    if doc.get("schema") != CASTING_SCHEMA:
        raise ValueError(f"编配文件 schema 应为 {CASTING_SCHEMA}")
    main = doc.get("main") or []
    sub = doc.get("sub") or []
    bg = doc.get("background") or []
    w = doc.get("domainWeights") or {}
    if len(main) != 2:
        raise ValueError("编配的 main 是主线那一对，要两个人")
    if len(sub) > 6:
        raise ValueError("副线至多六条：线多了先问哪几条碰不到主角、答不到命题")
    seen_pairs = [set(main)]
    for pair in sub:
        if set(pair) in seen_pairs:
            raise ValueError(f"这一对已经在线上了：{pair}")
        seen_pairs.append(set(pair))
    for pair in [main] + sub:
        if len(pair) != 2 or pair[0] == pair[1]:
            raise ValueError(f"一条线是一对人：{pair}")
        for n in pair:
            if n not in names:
                raise ValueError(f"编配里的 {n} 不在给的命盘里")
            if n in bg:
                raise ValueError(f"{n} 在线上，不能又是背景")
    for n in bg:
        if n not in names:
            raise ValueError(f"编配里的 {n} 不在给的命盘里")
    for d, v in w.items():
        if d not in _tl.DOMAINS:
            raise ValueError(f"领域配权里没有 {d} 这个领域")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
            raise ValueError(f"领域配权 {d} 要是正数")
    return {"schema": CASTING_SCHEMA, "main": list(main), "sub": [list(x) for x in sub], "background": list(bg), "domainWeights": dict(w)}


def _line_of(pair: set, casting: dict | None) -> str:
    if casting:
        if pair == set(casting["main"]):
            return "主线"
        if any(pair == set(x) for x in casting["sub"]):
            return "副线"
    return "旁线"


def tendency(edge: dict, year: int, snap_edge: dict | None, has_stakes: bool, reverse_edge: dict | None, escalate: bool = False) -> dict:
    """他（edge.from）对事件源（edge.to）的回应倾向：表的行加修正项。textOpen 是同一个倾向摆到明处的样子；
    escalate：两人之间有一条线第三回上卡，挂上修正项，取明处那一档。"""
    row = ROWS[edge["tenGod"]]
    role = edge["yongji"]["role"]
    if role in NEAR_ROLES:
        lean, text, text_open = "靠近", row["near"], row.get("nearOpen")
    elif role in AWAY_ROLES:
        lean, text, text_open = "躲或压", row["away"], row.get("awayOpen")
    else:
        lean, text, text_open = "看", MODS["闲神"]["改写"], None
    mods = []
    kinds = {r["kind"] for r in (snap_edge or {}).get("reasons", [])}
    if "六冲" in edge["dayPillar"]["branches"] or "日柱引动" in kinds:
        mods.append("日柱相冲")
    if "六合" in edge["dayPillar"]["branches"]:
        mods.append("日柱相合")
    if edge["dayPillar"]["stem"] in ("克", "被克"):
        mods.append("日干克或被克")
    if _covers(edge["syncJi"], year):
        mods.append("同步忌运的年份")
    up = _covers(edge["aUpBDown"], year)
    down = _covers(reverse_edge["aUpBDown"], year) if reverse_edge else None
    if up or down:
        mods.append("一顺一逆的年份")
    if "五行临身" in kinds:
        mods.append("五行临身的年份")
    if not has_stakes:
        mods.append("他当年没有领域在动")
    if escalate and "这条线第三回上卡" in MODS:
        mods.append("这条线第三回上卡")
    ids = [f"E-{edge['from']}-{edge['to']}-十神-{edge['tenGod']}", f"E-{edge['from']}-{edge['to']}-用忌-{role}"]
    for s in edge["syncJi"]:
        if s["from"] <= year <= s["to"]:
            ids.append(f"E-{edge['from']}-{edge['to']}-同步忌运-{s['from']}-{s['to']}")
    if up:
        ids.append(f"E-{edge['from']}-{edge['to']}-顺逆-{up['from']}-{up['to']}")
    if down:
        ids.append(f"E-{edge['to']}-{edge['from']}-顺逆-{down['from']}-{down['to']}")
    if snap_edge:
        ids += snap_edge["ids"]
    return {"who": edge["from"], "seesSourceAs": edge["tenGod"], "sourceIs": role, "between": row["between"],
            "carries": row["carries"], "lean": lean, "text": text, "textOpen": text_open,
            "upDown": "他顺源逆" if up else "源顺他逆" if down else None,
            "modifiers": [{"条件": m, "改写": MODS[m]["改写"]} for m in mods], "ids": ids}


def _event(chart: dict, age: int, year: int, weights: dict | None = None, avoid: str | None = None) -> tuple[dict, dict]:
    ys = chart.get("yongshen") or yongshen_mod.determine(chart["fourPillars"])
    steps = chart["dayun"]["steps"]
    y = _tl.year_facts(chart, age, ys, steps)
    y["year"] = year
    head = f"L-{age}-{y['pillar']}"
    item = _dl.rewrite_year(y, head, weights, avoid)
    if item is None:
        pm = _dl.primary_mechanism(y["mechanisms"])
        item = {"age": age, "year": year, "pillar": y["pillar"], "dayun": y.get("dayun"),
                "mechanism": pm[0] if pm else None, "mechanismRaw": pm[1] if pm else None,
                "form": _dl.MECH[pm[0]]["form"] if pm else None, "primary": None, "secondary": None,
                "dilemma": None, "template": "无领域，只有机制", "ids": [f"{head}-{pm[1]}"] if pm else [head]}
    if y.get("dayun"):
        st = next((s for s in steps if s["pillar"] == y["dayun"]["pillar"] and s["startAge"] == y["dayun"]["startAge"]), None)
        if st:
            item["ids"].append(f"D-{st['sequence']}-{st['pillar']}-基调")
    return item, y


def build(charts: list[dict], window: tuple[int, int], main: str, threads: list[dict] | None = None, months: bool = False,
          casting: dict | None = None) -> dict:
    names = [c.get("name") for c in charts]
    if main not in names:
        raise ValueError(f"--main {main} 不在给的命盘里")
    threads = threads or []
    casting = load_casting(casting, names)
    background = set(casting["background"]) if casting else set()
    weights = casting["domainWeights"] if casting else None
    pressure: dict[str, int] = {}
    recent: list[str | None] = []
    for t in threads:
        for n in t["people"]:
            if n not in names:
                raise ValueError(f"线程 {t['id']} 的 {n} 不在给的命盘里")
    sched = _sc.build(charts, window)
    m = _mx.build(charts)
    edges = {(e["from"], e["to"]): e for e in m["edges"]}
    nodes = {c["name"]: _mx._node(c) for c in charts}
    by_name = {c["name"]: c for c in charts}
    birth = {n: _mx._anchor(c) for n, c in zip(names, charts)}
    inters_by_year: dict[int, list[dict]] = {}
    for it in sched["intersections"]:
        inters_by_year.setdefault(it["year"], []).append(it)
    a, b = window
    cards, feats, pool = [], [], set()
    for f in sched["features"]:
        pool.add(f["id"])
    grid_mech = {(row["year"], r["name"]): r.get("mechanisms", []) for row in sched["grid"] for r in row["people"]}
    for t in threads:
        # 任一方换运的年份线程标改写（第 6 条），过场年也算，写在线程本身；热年的卡另列 rewrite
        t["rewriteYears"] = sorted({y for y in range(max(a, t["since"] + 1), b + 1) for n in t["people"] if "换运" in grid_mech.get((y, n), [])})
        pool.add(t["id"])
        feats.append({"id": t["id"], "text": f"线程 {t['id']}：{t['people'][0]}与{t['people'][1]}在{t['domain']}上的账，{t['since']}年起，{t['status']}"
                                              + (f"，{t['note']}" if t.get("note") else "")})
    for year in range(a, b + 1):
        inters = inters_by_year.get(year)
        if not inters:
            continue
        snap = _en.snapshot(charts, year, months=months)
        for f in snap["features"]:
            pool.add(f["id"])
        feats += [f for f in snap["features"] if not f["id"].count("月-")]  # 流月编号只进池，不重复列
        if months:
            feats += [f for f in snap["features"] if f["id"].count("月-")]
        state = {p["name"]: p for p in snap["people"] if p.get("born")}
        snap_edges = {(e["from"], e["to"]): e for e in snap["edges"]}
        # 2. 事件源。背景的人不当源（编配表），除非这一年只有背景的人有事
        eventful = sorted({n for it in inters for n in it["eventful"]}, key=lambda n: (_rank(state[n]["mechanisms"]), n != main, names.index(n)))
        front = [n for n in eventful if n not in background]
        source = (front or eventful)[0]
        # 3. 在场的人
        present = [source]
        for it in inters:
            if source in it["people"]:
                for n in it["people"]:
                    if n not in present:
                        present.append(n)
        for (x, y_), e in snap_edges.items():
            if any(r["kind"] == "五行临身" for r in e["reasons"]) and (x in present or y_ in present):
                for n in (x, y_):
                    if n not in present:
                        present.append(n)
        present = [n for n in names if n in present]
        # 这一年只有背景的人有事：事落到在场的、押得最重的那个线上的人头上，他当源；背景的人记作 driver，可以施压，不当源
        driver = None
        if source in background:
            nb = [n for n in present if n not in background]
            if nb:
                driver = source
                source = max(nb, key=lambda n: (sum(d["weight"] for d in state[n]["domains"]), -names.index(n)))
        elsewhere = [it["id"] for it in inters if not (set(it["people"]) & set(present))]
        # 事件。同一个主领域连着做了两个热年，这一年让它退后（只在给了编配时）
        # 书自己多挑的领域（配权大于一）不让：感情线的书连着几年都是感情，正是它要的
        avoid = recent[-1] if casting and len(recent) >= 2 and recent[-1] and recent[-1] == recent[-2] and weights.get(recent[-1], 1) <= 1 else None
        event, yfacts = _event(by_name[source], state[source]["age"], year, weights, avoid)
        recent.append((event.get("primary") or {}).get("domain"))
        # 4. 赌注
        stakes = []
        for n in present:
            p = state[n]
            doms = p["domains"]
            cand = _tl._is_candidate({"mechanisms": p["mechanisms"]})
            head = f"L-{p['age']}-{p['liunian']}"
            stakes.append({"who": n, "age": p["age"], "liunian": p["liunian"], "candidate": cand, "keyMechanisms": p["keyMechanisms"],
                           "domains": [{"domain": d["domain"], "weight": d["weight"], "via": d["via"]} for d in doms],
                           "total": sum(d["weight"] for d in doms), "byPortraitOnly": not doms,
                           "ids": [f"Q-{year}-{n}"] + [f"{head}-域-{d['domain']}" for d in doms]})
        heaviest = max((s for s in stakes if s["who"] != source), key=lambda s: (s["total"], -present.index(s["who"])), default=None)
        # 6. 线程（先算，回应倾向要看哪条线第三回上卡）
        on_card = []
        for t in threads:
            if t["status"] not in THREAD_OPEN or year <= t["since"]:  # 起始那年是它开出来的卡，之后的年份才谈重上
                continue
            A, B = t["people"]
            why = []
            if any(set(it["people"]) == {A, B} for it in inters):
                why.append(f"{A}与{B}今年再成交汇点")
            for n in (A, B):
                p = state.get(n)
                if p and _tl._is_candidate({"mechanisms": p["mechanisms"]}) and any(d["domain"] == t["domain"] for d in p["domains"]):
                    why.append(f"{n}今年是候选年份且动{t['domain']}")
            rewrite = [n for n in (A, B) if state.get(n) and "换运" in state[n]["mechanisms"]]
            if why or rewrite:
                pressure[t["id"]] = pressure.get(t["id"], 0) + 1
                on_card.append({"id": t["id"], "people": t["people"], "domain": t["domain"], "since": t["since"],
                                "why": why, "rewrite": rewrite, "note": t.get("note", ""),
                                "status": t["status"], "pressure": pressure[t["id"]], "escalate": pressure[t["id"]] >= ESCALATE_AT,
                                **({"plan": t["plan"]} if t.get("plan") else {}), **({"open": t["open"]} if t.get("open") else {})})
        hot_pairs = [set(t["people"]) for t in on_card if t["escalate"]]
        # 5. 回应倾向
        tends = []
        for n in present:
            if n == source:
                continue
            e = edges[(n, source)]
            tends.append(tendency(e, year, snap_edges.get((n, source)), bool(state[n]["domains"]), edges.get((source, n)),
                                  escalate={n, source} in hot_pairs))
            tends[-1]["sourceSeesHimAs"] = edges[(source, n)]["tenGod"]
        # 事件候选（DESIGN-戏剧层 5.2）：在场各人自己的事，加当年每个交汇点边上的事；背景的人不出候选
        cands = []
        for n in present:
            if n in background or not _tl._is_candidate({"mechanisms": state[n]["mechanisms"]}):
                continue
            ev = event if n == source else _event(by_name[n], state[n]["age"], year, weights)[0]
            cands.append({"kind": "个人", "who": n, "line": "旁线", "mechanism": ev.get("mechanismRaw"),
                          "domain": (ev.get("primary") or {}).get("domain"), "dilemma": ev.get("dilemma"),
                          "score": len(_dl.PRIORITY) - _rank(state[n]["mechanisms"]), "ids": ev["ids"]})
        order = {d: i for i, d in enumerate(_tl.DOMAINS)}
        for it in inters:
            A, B = it["people"]
            if not {A, B} <= set(present) or {A, B} <= background:
                continue
            line = _line_of({A, B}, casting)
            tally: dict[str, float] = {}
            for n in (A, B):
                for d in state[n]["domains"]:
                    tally[d["domain"]] = tally.get(d["domain"], 0) + d["weight"] * (weights or {}).get(d["domain"], 1)
            dom = min(tally, key=lambda d: (-tally[d], order[d])) if tally else None
            sides = []
            for x, y_ in ((A, B), (B, A)):
                td = tendency(edges[(x, y_)], year, snap_edges.get((x, y_)), bool(state[x]["domains"]), edges.get((y_, x)),
                              escalate={x, y_} in hot_pairs)
                sides.append({"who": x, "sees": y_, "as": td["seesSourceAs"], "lean": td["lean"], "text": td["text"],
                              "textOpen": td["textOpen"], "modifiers": [m["条件"] for m in td["modifiers"]]})
            dom_ids = [f"L-{state[n]['age']}-{state[n]['liunian']}-域-{dom}" for n in (A, B)
                       if dom and any(d["domain"] == dom for d in state[n]["domains"])]
            cands.append({"kind": "边", "people": [A, B], "line": line, "domain": dom,
                          "stake": _dl.DOMAIN[dom]["stake"] if dom else None, "reasons": it["reasons"], "sides": sides,
                          "threads": [t["id"] for t in on_card if set(t["people"]) == {A, B}],
                          "score": len(_dl.PRIORITY) - min(_rank(state[A]["mechanisms"]), _rank(state[B]["mechanisms"])) + LINE_BONUS[line],
                          "ids": sorted({it["id"], *it["snapshotIds"], *dom_ids, f"Q-{year}-{A}", f"Q-{year}-{B}"})})
        cands.sort(key=lambda c: (-c["score"], c["kind"] != "边", names.index(c.get("who") or c["people"][0])))
        open_thread = None
        if event.get("primary") and heaviest is not None:
            other = heaviest["who"]
            dom = event["primary"]["domain"]
            open_thread = {"id": f"TH-{year}-{source}-{other}-{dom}", "people": [source, other], "domain": dom,
                           "stake": event["primary"]["stake"], "since": year, "status": "埋" if casting else "悬置", "note": ""}
        ids = sorted({i for it in inters for i in [it["id"]] + it["snapshotIds"]} | {f"Q-{year}-{n}" for n in present}
                     | set(event["ids"]) | {i for s in stakes for i in s["ids"]} | {i for t in tends for i in t["ids"]} | {t["id"] for t in on_card}
                     | {i for c in cands for i in c["ids"]})
        pool |= set(ids)
        yq = yunqi_mod.year_qi(state[source]["pillar"]) if state[source].get("pillar") else {}
        card = {"year": year, "source": source, **({"driver": driver} if driver else {}), "sourceAge": state[source]["age"], "sourceKeyMechanisms": state[source]["keyMechanisms"],
                "intersections": [it["id"] for it in inters if set(it["people"]) & set(present)], "elsewhere": elsewhere,
                "event": event, "candidates": cands, "present": present, "stakes": stakes, "tendencies": tends, "threads": on_card,
                **({"yearScene": {"label": yq["scene"]["label"], "text": yq["scene"]["text"], "epidemic": yq["scene"]["epidemic"]}} if yq.get("scene") else {}),
                "openThread": open_thread, "ids": ids}
        if months:
            card["months"] = {n: state[n].get("months", []) for n in present}
        cards.append(card)
    hot = [c["year"] for c in cards]
    gaps, run = [], []
    for year in range(a, b + 1):
        if year in hot:
            if run:
                gaps.append({"from": run[0], "to": run[-1], "years": len(run)})
                run = []
        else:
            run.append(year)
    if run:
        gaps.append({"from": run[0], "to": run[-1], "years": len(run)})
    # 7. 投影
    volumes = []
    mc = by_name[main]
    mb = birth[main]
    for s in mc["dayun"]["steps"]:
        y0, y1 = mb + s["startAge"], mb + s["endAge"] - 1
        if y1 < a or y0 > b:
            continue
        sc = next((x["score"] for x in nodes[main]["steps"] if x["pillar"] == s["pillar"] and x["startAge"] == s["startAge"]), 0)
        turning = []
        for n in names:
            if n == main:
                continue
            for st in by_name[n]["dayun"]["steps"]:
                yy = birth[n] + st["startAge"]
                if max(y0, a) <= yy <= min(y1, b):
                    turning.append({"year": yy, "who": n, "what": f"换运入{st['pillar']}", "ids": [f"Q-{yy}-{n}"] if yy in hot else []})
        # 高潮候选（DESIGN-戏剧层 5.4）：每卷按主机制烈度、主线副线的边有没有动、线上的人日柱挨没挨、哪条线该升级了，给前三
        lined = {n for pair in [casting["main"]] + casting["sub"] for n in pair} if casting else {main}
        climax = []
        for c in cards:
            if not (y0 <= c["year"] <= y1):
                continue
            why = [f"主机制 {c['event'].get('mechanismRaw')}"]
            pts = float(len(_dl.PRIORITY) - _dl.PRIORITY.index(c["event"]["mechanism"])) if c["event"].get("mechanism") else 0.0
            for x in c["candidates"]:
                if x["kind"] == "边" and x["line"] != "旁线":
                    pts += LINE_BONUS[x["line"]] / 2
                    why.append(f"{x['line']} {x['people'][0]}与{x['people'][1]}被引动")
            for st in c["stakes"]:
                if st["who"] in lined and any(k.startswith(_BODY_HITS) for k in st["keyMechanisms"]):
                    pts += 1
                    why.append(f"{st['who']}日柱挨了一记")
            for t in c["threads"]:
                if t["escalate"]:
                    pts += 1
                    why.append(f"{t['id']} 第{t['pressure']}回上卡")
            climax.append({"year": c["year"], "score": pts, "why": why})
        climax = sorted(climax, key=lambda x: (-x["score"], x["year"]))[:3]
        volumes.append({"stage": f"D-{s['sequence']}-{s['pillar']}", "ages": [s["startAge"], s["endAge"]], "years": [max(y0, a), min(y1, b)],
                        "tone": "顺" if sc > 0 else "逆" if sc < 0 else "平", "hotYears": [y for y in hot if y0 <= y <= y1],
                        "climaxCandidates": climax,
                        "turningPoints": sorted(turning, key=lambda t: (t["year"], t["who"])),
                        "threadsOpened": [t["id"] for t in threads if y0 <= t["since"] <= y1]})
    for v in volumes:
        pool.add(f"{v['stage']}-基调")  # 卷按主角大运切，大纲引它的基调编号
    segments = [{"year": c["year"], "source": c["source"], "mechanism": c["event"].get("mechanismRaw"),
                 "domain": (c["event"].get("primary") or {}).get("domain"), "dilemma": c["event"].get("dilemma"),
                 "present": c["present"], "threads": [t["id"] for t in c["threads"]]} for c in cards]
    return {"schema": SCHEMA, "algorithm": "bazi-writing ensemble-run v1（DESIGN 17 已定项 2026-09-24-11；表 response_tendency.json）",
            "window": [a, b], "main": main, "people": names, **({"casting": casting} if casting else {}),
            "hotYears": hot, "gaps": gaps, "cards": cards,
            "outline": {"volumes": volumes, "segments": segments},
            "threads": threads, "features": feats, "idPool": sorted(pool),
            "note": "事件卡是草稿：模型对着一张卡写这一年的事件链，每步引卡上的编号；两难没解决就把 openThread 抄进线程文件标悬置，了结时改状态。"}


def check_chain(md: str, run: dict) -> list[dict]:
    """人物/推演.md 里每条"｜溯源 …"的编号都要在 idPool 里；返回问题列表。
    只把"溯源"后面全是编号（或为空）的行当溯源行，正文里提到"溯源"两个字的句子不算。"""
    pool = set(run.get("idPool", []))
    problems = []
    sourced = 0
    for ln, line in enumerate(md.splitlines(), 1):
        m = re.search(r"[｜|]溯源\s*(.*)$", line)
        if not m:
            continue
        toks = [i.strip() for i in re.split(r"[，、,;；\s]+", m.group(1)) if i.strip()]
        looks = [_ID_PREFIX.match(t) is not None for t in toks]
        if toks and not any(looks):
            continue  # 正文里的"溯源"字样
        sourced += 1
        if not toks:
            problems.append({"line": ln, "problem": "溯源为空"})
        for t, ok in zip(toks, looks):
            if not ok:
                problems.append({"line": ln, "id": t, "problem": "不是编号"})
            elif t not in pool:
                problems.append({"line": ln, "id": t, "problem": "编号不在推演 idPool 里"})
    if sourced == 0:
        problems.append({"line": 0, "problem": "整份事件链没有一条溯源"})
    return problems


BONE_FIELDS = ("为哪一人一事", "起", "承", "转", "合", "高潮年", "响", "清算", "卷末的问题")
YEAR_FIELDS = ("牌面", "因", "事件", "选择", "知情", "线程", "主线温度", "读者")
TEMPERATURES = ("靠", "离", "撞", "退")
_FIELD = re.compile(r"^- ([^：:]{1,12})[：:]\s*(.*)$")
_STEP = re.compile(r"^\s+(?:\d+[.、]|[-*])\s*(.+)$")


def check_chain_drama(md: str, run: dict, threads: list[dict] | None = None) -> dict:
    """事件链新写法（模板 references/戏剧层/模板/推演.md）。返回 {"problems": [...], "stats": {...}}。
    卷：二级标题，里面要有三级标题"骨"，九个字段齐。热年：三级标题以年份起头，八个字段齐，步子至少两步，
    每步写以为与实际、标（明）或（暗）。卡上第三回上卡的线，这一年要么在线程一栏标响，要么至少一步是明的。
    线程文件里状态是埋或压的线要有 plan。溯源照旧由 check_chain 核。"""
    problems: list[dict] = []
    cards = {c["year"]: c for c in run.get("cards", [])}
    sections: list[dict] = []
    cur = None
    volume = None
    for ln, line in enumerate(md.splitlines(), 1):
        if line.startswith("## "):
            volume = {"title": line[3:].strip(), "line": ln, "bone": None, "years": []}
            sections.append(volume)
            cur = None
            continue
        if line.startswith("### "):
            title = line[4:].strip()
            m = re.match(r"(\d{1,4})\s*年", title)
            cur = {"title": title, "line": ln, "fields": {}, "steps": [], "year": int(m.group(1)) if m else None}
            if volume is not None:
                if title.startswith("骨"):
                    volume["bone"] = cur
                elif m:
                    volume["years"].append(cur)
            continue
        if cur is None:
            continue
        f = _FIELD.match(line)
        if f:
            cur["fields"][f.group(1).strip()] = re.split(r"\s*[｜|]溯源", f.group(2))[0].strip()
            continue
        st = _STEP.match(line)
        if st:
            cur["steps"].append({"line": ln, "text": st.group(1)})
    vols = [v for v in sections if v["years"] or v["bone"]]
    seen_years = set()
    open_steps = rung = 0
    temps: list[str] = []
    for v in vols:
        if v["bone"] is None:
            problems.append({"line": v["line"], "problem": f"{v['title']}没有骨：先立这一卷的骨再填步骤"})
        else:
            for k in BONE_FIELDS:
                if not v["bone"]["fields"].get(k):
                    problems.append({"line": v["bone"]["line"], "problem": f"{v['title']}的骨缺{k}"})
        for y in v["years"]:
            seen_years.add(y["year"])
            for k in YEAR_FIELDS:
                if not y["fields"].get(k):
                    problems.append({"line": y["line"], "problem": f"{y['year']}年缺{k}"})
            t = y["fields"].get("主线温度", "")
            if t:
                if t[0] not in TEMPERATURES:
                    problems.append({"line": y["line"], "problem": f"{y['year']}年主线温度要以 靠、离、撞、退 之一起头"})
                else:
                    temps.append(t[0])
            if len(y["steps"]) < 2:
                problems.append({"line": y["line"], "problem": f"{y['year']}年步子少于两步"})
            year_open = 0
            for stp in y["steps"]:
                tx = stp["text"]
                if "以为" not in tx or "实际" not in tx:
                    problems.append({"line": stp["line"], "problem": "这一步没写他以为会怎样、实际怎样"})
                if "（明）" in tx:
                    year_open += 1
                elif "（暗）" not in tx:
                    problems.append({"line": stp["line"], "problem": "这一步没标（明）或（暗）"})
            open_steps += year_open
            line_th = y["fields"].get("线程", "")
            rung_here = set(re.findall(r"(TH-\S+?)\s*响", line_th))
            rung += len(rung_here)
            card = cards.get(y["year"])
            for th in (card or {}).get("threads", []):
                if th.get("escalate") and th["id"] not in rung_here and not year_open:
                    problems.append({"line": y["line"], "id": th["id"],
                                     "problem": f"{th['id']} 第{th['pressure']}回上卡，这一年没有响，也没有一步是明的：该升级或清算了"})
    for yr in run.get("hotYears", []):
        if yr not in seen_years:
            problems.append({"line": 0, "problem": f"热年 {yr} 没有一节"})
    for th in threads or []:
        if th["status"] in ("埋", "压") and not th.get("plan"):
            problems.append({"line": 0, "id": th["id"], "problem": "这条线埋着，没写哪一年响；留哑也要写理由（plan.mute）"})
    flat = all(a == b for a, b in zip(temps, temps[1:])) if len(temps) >= 3 else False
    if flat:
        problems.append({"line": 0, "problem": f"主线温度从头到尾都是{temps[0]}，一直帐，没有擒放"})
    return {"problems": problems,
            "stats": {"volumes": len(vols), "years": len(seen_years), "openSteps": open_steps, "rung": rung,
                      "temperature": "".join(temps),
                      "threadsOpen": sum(1 for t in threads or [] if t["status"] in THREAD_OPEN),
                      "threadsClosed": sum(1 for t in threads or [] if t["status"] not in THREAD_OPEN)}}


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="群像推演：事件卡与悬置线程")
    ap.add_argument("charts", nargs="*", help="命盘档案 JSON")
    ap.add_argument("--window", nargs=2, type=int, metavar=("起", "止"), help="故事纪年段")
    ap.add_argument("--main", help="主角名，卷按他的大运切")
    ap.add_argument("--threads", help="线程文件 群像/线程.json")
    ap.add_argument("--casting", help="编配的机器本 群像/编配.json（主线、副线、背景的人、领域配权）")
    ap.add_argument("--months", action="store_true", help="热年在场的人带十二流月")
    ap.add_argument("--check-chain", metavar="MD", help="核对人物/推演.md 的溯源都在推演 idPool 里")
    ap.add_argument("--run", metavar="JSON", help="--check-chain 用：推演.json")
    ap.add_argument("--drama", action="store_true", help="--check-chain 用：按事件链新写法再查骨、因、落差、明暗、升级（DESIGN-戏剧层 4.3）")
    ns = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if ns.check_chain:
        if not ns.run:
            ap.error("--check-chain 要配 --run")
        run = json.loads(Path(ns.run).read_text(encoding="utf-8"))
        md = Path(ns.check_chain).read_text(encoding="utf-8")
        problems = check_chain(md, run)
        stats = {}
        if ns.drama:
            th = load_threads(json.loads(Path(ns.threads).read_text(encoding="utf-8"))) if ns.threads else run.get("threads", [])
            d = check_chain_drama(md, run, th)
            problems += d["problems"]
            stats = d["stats"]
        for p in problems:
            print(json.dumps({"file": ns.check_chain, **p}, ensure_ascii=False))
        print(json.dumps({"summary": True, "file": ns.check_chain, "problems": len(problems), **stats}, ensure_ascii=False))
        return 1 if problems else 0
    if not ns.charts or not ns.window or not ns.main:
        ap.error("要给命盘、--window 与 --main")
    charts = [json.loads(Path(p).read_text(encoding="utf-8")) for p in ns.charts]
    threads = load_threads(json.loads(Path(ns.threads).read_text(encoding="utf-8"))) if ns.threads else []
    casting = json.loads(Path(ns.casting).read_text(encoding="utf-8")) if ns.casting else None
    out = build(charts, (ns.window[0], ns.window[1]), ns.main, threads, ns.months, casting)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
