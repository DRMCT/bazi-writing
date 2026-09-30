"""群像推演：事件卡与悬置线程（DESIGN-戏剧层 7.4）。

事件是共享的，两难是各人的。不做"谁先动、轮流回应、推几轮"的回合模型：每个热年一张事件卡，脚本把在场的人、
各人的赌注、各人的回应倾向、旧账一次算全，模型对着一张卡写这一年的事件链，几轮由叙事定，脚本不数。

规则（与 DESIGN-戏剧层 7.4 逐条对应）：
1. 热年由交汇点定（schedule.build 的收紧规则：边有当年才有的原因，且两端至少一人是候选年份）。没有交汇点的年份是过场，
   连续的过场记进 gaps，大纲里合成一句时间跳跃。
2. 事件源是交汇点里主机制烈度最高的人（dilemma.PRIORITY），同分主角先；事件直接取他那一年的两难草稿（dilemma.rewrite_year）。
3. 在场的人：与事件源同在交汇点的人，加上当年对任一在场者有五行临身的人。人数由边定，不设轮数。
4. 各人的赌注取当年领域权重（timeline.year_facts 的 domains.weight）。当年没有领域在动的人只按画像反应，不生新事件。
5. 回应倾向查 tables/response_tendency.json：他看事件源的十神边乘用忌，喜用取靠近、忌仇取躲或压、闲取看；修正项按矩阵边与快照的事实判。
6. 悬置线程读作者维护的 群像/线程.json（bazi-threads/v1 两态；v2 四态埋、压、响、余波，另有知情 knows，v1 的悬置读作压、了结读作余波）：没了结的线程，当年该对边再成交汇点、或任一方候选年份触及同一领域时重新上卡；
   任一方换运的年份标改写；了结的不再上卡。每张卡另给 openThread 建议，作者写完卡认为两难没解决就把它抄进线程文件。
7. 投影：卷按主角的大运切（volumes，长跨度的书才这样分卷；短跨度的卷照编配的段，由事件链定），配角换运年成卷内转折；
   热年成情节段（segments）；作者挑的热年给 --months 出流月，供细纲。
8. 编配（--casting，bazi-casting/v1 或 v2）：v1 是主线、副线、背景的人、领域配权；v2 另有可空的时间尺度 timescale、谁碎 breakers、
   家族 families、透给读者的默认下场 defaultFate、钟 calendar、物件账 objects，逐栏校验。背景的人不当事件源。
9. 事件源扩表（DESIGN-戏剧层 7.5）：热年只是十种来路之一。卡上 sources 给默认下场到点、过去追上来、对手出招、家人出招、
   得知与认出、局与日历的候选，过场年的放 offCard，顶层 sourceKinds 是十种的对照表；fate 是默认下场（DF-）与前史（PH-），
   同 fate.py，编配透了几条时另带书一级的保质期；给了编配，卡上另有 breakers（这一年可以碎的人）与 dilemmaTo（源为主角那一年
   两难可以给的人）。timescale 按编配或窗长推定（不过两年是短跨度）：短跨度自动带流月并出 monthGrid，回到关口年出 returns，
   单元客（--guests）出 guests，上一代（--elders）只出前史。
10. --check-chain 核事件链的溯源都在 idPool 里；加 --drama 另查骨、因、落差、明暗、升级、源与默认下场（透、应验、改）。

编号：沿用 Q-（快照）、E-（矩阵）、L-（年表）、J-（日程）、D-（大运基调）；新加 TH-{起始年}-{A}-{B}-{领域}（线程）、
DF-（默认下场）、PH-（前史）。
顶层 idPool 列出全部可引编号，check-character.js --run 读它；模型写的事件链（人物/推演.md）用 --check-chain 核对每条溯源都在池里。

命令行（在作者项目根下）：
    python -m bazi_core.ensemble_run 命盘/沈砚.json 命盘/林昭.json 命盘/裴恪.json --window 324 346 --main 林昭 \
        --casting 命盘/群像/编配.json [--threads 命盘/群像/线程.json] [--elders 命盘/甲父.json] [--guests 命盘/客一.json] \
        [--horizon 10] [--months] > 命盘/群像/推演.json
    python -m bazi_core.ensemble_run --check-chain 人物/推演.md --run 命盘/群像/推演.json --threads 命盘/群像/线程.json --drama
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import dilemma as _dl
from . import ensemble as _en
from . import fate as _fate
from . import yunqi as yunqi_mod
from . import matrix as _mx
from . import schedule as _sc
from . import timeline as _tl
from . import yongshen as yongshen_mod
from .dayun import pillar_name, sexagenary_index

SCHEMA = "bazi-ensemble-run/v1"
THREADS_SCHEMA = "bazi-threads/v1"
THREADS_SCHEMAS = ("bazi-threads/v1", "bazi-threads/v2")
# v1 两态；v2 四态（DESIGN-戏剧层 9）：埋、压、响、余波。悬置读作压，了结读作余波，两套词一个文件里可以混用
THREAD_STATUS = ("悬置", "了结", "埋", "压", "响", "余波")
THREAD_OPEN = ("悬置", "埋", "压", "响")
ESCALATE_AT = 3  # 一条线开出以后第三回上卡，该升级或清算了
CASTING_SCHEMA = "bazi-casting/v1"
CASTING_SCHEMAS = ("bazi-casting/v1", "bazi-casting/v2")  # v2 加时间尺度、谁碎、家族、默认下场、钟、物件账（DESIGN-戏剧层 4），都可空
TIMESCALES = ("短跨度", "长跨度", "回到关口年")
SHORT_SPAN = 2  # 没给时间尺度时，窗不过两年按短跨度走
BREAK_BY = ("自己", "别人当面", "物证")
OUTCOMES = ("应验", "改")
PRESS_GODS = ("正官", "七杀")
# 事件源扩表（DESIGN-戏剧层 7.5）：脚本给候选，事件链由模型挑并写明为什么
SOURCE_KINDS = (
    {"kind": "热年出事", "how": "交汇点的年份出事件卡", "where": "cards"},
    {"kind": "默认下场到点", "how": "默认下场年表的那一年到了；编配透过的带 revealed", "where": "cards[].sources、offCard"},
    {"kind": "过去追上来", "how": "冲年支、伏吟的年份，或候选年份的主领域与一条前史相同；上一代的旧账看同族晚辈", "where": "cards[].sources、offCard"},
    {"kind": "对手出招", "how": "上一张卡里躲或压的那一头、押得最重的那一头失去了什么，他下一个候选年份出下一招", "where": "cards[].sources、offCard"},
    {"kind": "家人出招", "how": "编配家族里相克的有向边（他是对方的官杀），他的候选年份触发", "where": "cards[].sources、offCard"},
    {"kind": "得知与认出", "how": "线程上卡时不在知情里的那一头；物件账写了哪一年被认出，或原主与持有人同在一张卡", "where": "cards[].sources"},
    {"kind": "主角布局", "how": "不由盘给，事件链里标出", "where": "—"},
    {"kind": "局与日历", "how": "编配的钟按月挂上，同月谁的流月被引动", "where": "cards[].sources、offCard、monthGrid"},
    {"kind": "旁人求上门、班底派活", "how": "单元客入口：他书前的热年是找上门的那件事", "where": "guests"},
    {"kind": "关系自己往前走", "how": "主线温度，不由盘给", "where": "—"},
)
LINE_BONUS = {"主线": 6, "副线": 3, "旁线": 0}
_BODY_HITS = ("天克地冲日柱", "冲日支")
_TABLE_PATH = Path(__file__).resolve().parent / "tables" / "response_tendency.json"
_T = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
ROWS = {r["tenGod"]: r for r in _T["rows"]}
MODS = {m["条件"]: m for m in _T["modifiers"]}
NEAR_ROLES = ("用", "喜")
AWAY_ROLES = ("忌", "仇")
_ID_PREFIX = re.compile(r"^(?:P|DM|T|H|G|S|U|Y|R|N|NT|C|D|L|IN|IM|LI|YQ|E|Q|J|TH|DF|PH)-\S+$")  # 命盘各节、矩阵、年表、日程、快照、线程、默认下场、前史


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


def load_casting(doc: dict | None, names: list[str], others: list[str] | tuple = ()) -> dict | None:
    """编配的机器本（DESIGN-戏剧层 4、7.4）：主线一对、副线几对（长篇三到五条线，至多六对）、背景的人、领域配权；
    v2 另有可空的几栏：timescale 时间尺度、breakers 谁碎、families 家族、defaultFate 默认下场透哪几条、calendar 钟、objects 物件账。
    others：上一代与单元客的名字（不进推演的交汇点，家族、谁碎、物件账里可以出现）。人话在 人物/编配.md。"""
    if not doc:
        return None
    if doc.get("schema") not in CASTING_SCHEMAS:
        raise ValueError(f"编配文件 schema 应为 {' 或 '.join(CASTING_SCHEMAS)}")
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
    out = {"schema": doc["schema"], "main": list(main), "sub": [list(x) for x in sub], "background": list(bg), "domainWeights": dict(w)}
    out.update(_casting_v2(doc, names, list(others)))
    return out


def _casting_v2(doc: dict, names: list[str], others: list[str]) -> dict:
    everyone = set(names) | set(others)
    out: dict = {}

    def who_ok(n, where: str, pool: set = everyone) -> None:
        if n not in pool:
            raise ValueError(f"编配{where}里的 {n} 不在给的命盘里")

    def year_ok(v, where: str) -> None:
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError(f"编配{where}的年份要是整数：{v}")

    ts = doc.get("timescale")
    if ts is not None:
        if ts not in TIMESCALES:
            raise ValueError(f"时间尺度只能是 {'、'.join(TIMESCALES)}")
        out["timescale"] = ts
    if doc.get("breakers") is not None:
        brs = []
        for x in doc["breakers"]:
            x = {"who": x} if isinstance(x, str) else dict(x)
            who_ok(x.get("who"), "谁碎")
            if x.get("by") is not None and x["by"] not in BREAK_BY:
                raise ValueError(f"谁碎 {x['who']} 的 by 只能是 {'、'.join(BREAK_BY)}")
            if x.get("year") is not None:
                year_ok(x["year"], "谁碎")
            brs.append(x)
        if len({x["who"] for x in brs}) != len(brs):
            raise ValueError("谁碎一人全书一回，同一个人只写一行")
        out["breakers"] = brs
    if doc.get("families") is not None:
        fams = []
        for f in doc["families"]:
            if not isinstance(f, list) or len(f) < 2:
                raise ValueError(f"一个家族至少两个人：{f}")
            for n in f:
                who_ok(n, "家族")
            fams.append(list(f))
        out["families"] = fams
    if doc.get("defaultFate") is not None:
        dfs = []
        for x in doc["defaultFate"]:
            who_ok(x.get("who"), "默认下场", set(names))
            year_ok(x.get("year"), "默认下场")
            if x.get("reveal") is not None and x["reveal"] not in _fate.REVEALS:
                raise ValueError(f"默认下场的透法只能是 {'、'.join(_fate.REVEALS)}")
            if x.get("outcome") is not None and x["outcome"] not in OUTCOMES:
                raise ValueError(f"默认下场的 outcome 只能是 {'、'.join(OUTCOMES)}")
            if x.get("spill") is not None:
                who_ok(x["spill"], "默认下场的余波")
            dfs.append(dict(x))
        out["defaultFate"] = dfs
    if doc.get("calendar") is not None:
        cal = []
        for x in doc["calendar"]:
            if not x.get("name"):
                raise ValueError(f"钟要有名字：{x}")
            m = x.get("month")
            if isinstance(m, bool) or not isinstance(m, int) or not 1 <= m <= 12:
                raise ValueError(f"钟 {x['name']} 的 month 是一到十二（流月的次序，寅月为一）")
            if x.get("year") is not None:
                year_ok(x["year"], "钟")
            for n in x.get("who", []):
                who_ok(n, "钟")
            cal.append(dict(x))
        out["calendar"] = cal
    if doc.get("objects") is not None:
        objs = []
        for x in doc["objects"]:
            if not x.get("name"):
                raise ValueError(f"物件要有名字：{x}")
            who_ok(x.get("holder"), "物件账")
            for ps in x.get("passes", []):
                year_ok(ps.get("year"), "物件转手")
                who_ok(ps.get("to"), "物件转手")
            rc = x.get("recognized")
            if rc is not None:
                year_ok(rc.get("year"), "物件被认出")
                who_ok(rc.get("by"), "物件被认出")
            objs.append(dict(x))
        out["objects"] = objs
    return out


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
          casting: dict | None = None, elders: list[dict] | None = None, guests: list[dict] | None = None,
          horizon: int = _fate.DEFAULT_HORIZON) -> dict:
    """elders：上一代的盘，只出前史；guests：单元客的盘，只出入口。两种都不进交汇点。"""
    names = [c.get("name") for c in charts]
    if main not in names:
        raise ValueError(f"--main {main} 不在给的命盘里")
    threads = threads or []
    elders = elders or []
    guests = guests or []
    extra = [c.get("name") for c in elders + guests]
    for n in extra:
        if n in names or extra.count(n) > 1:
            raise ValueError(f"{n} 重复了：上一代与单元客另给，不和推演的命盘重名")
    casting = load_casting(casting, names, extra)
    timescale = (casting or {}).get("timescale") or ("短跨度" if window[1] - window[0] + 1 <= SHORT_SPAN else "长跨度")
    months = months or timescale == "短跨度"  # 短跨度推演最细到流月
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
        # 事件候选（DESIGN-戏剧层 7.4）：在场各人自己的事，加当年每个交汇点边上的事；背景的人不出候选
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
    ext = _expand(charts, (a, b), main, cards, threads, casting, elders, guests, horizon, timescale, edges)
    for c in cards:
        c["sources"] = ext["byYear"][c["year"]]
        c.update(ext["cardExtra"].get(c["year"], {}))
    known = {f["id"] for f in feats}
    feats += [f for f in ext["features"] if f["id"] not in known]
    pool |= ext["ids"]
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
        # 高潮候选（DESIGN-戏剧层 7.4）：每卷按主机制烈度、主线副线的边有没有动、线上的人日柱挨没挨、哪条线该升级了，给前三
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
    return {"schema": SCHEMA, "algorithm": "bazi-writing ensemble-run v1（DESIGN-戏剧层 7.4；表 response_tendency.json）",
            "window": [a, b], "main": main, "people": names, **({"casting": casting} if casting else {}),
            "hotYears": hot, "gaps": gaps, "cards": cards,
            "outline": {"volumes": volumes, "segments": segments},
            "threads": threads, "features": feats, "idPool": sorted(pool),
            "note": "事件卡是草稿：模型对着一张卡写这一年的事件链，每步引卡上的编号；两难没解决就把 openThread 抄进线程文件标悬置，了结时改状态。",
            # 以下是 DESIGN-戏剧层 6、7.5 加的，旧的几栏不动
            "timescale": {"kind": timescale, "from": "编配" if (casting or {}).get("timescale") else "窗长推定", "years": b - a + 1,
                          "note": TIMESCALE_NOTE[timescale]},
            "fate": ext["fate"], "sourceKinds": [dict(k) for k in SOURCE_KINDS],
            # 年年都有的钟不单独把一个过场年拉进来（短跨度看 monthGrid）
            "offCard": [{"year": y, "sources": ext["byYear"][y]} for y in range(a, b + 1)
                        if y not in hot and any(not x.get("every") for x in ext["byYear"][y])],
            **({"monthGrid": ext["monthGrid"]} if timescale == "短跨度" else {}),
            **({"returns": ext["returns"]} if timescale == "回到关口年" else {}),
            **({"guests": ext["guests"]} if guests else {})}


TIMESCALE_NOTE = {
    "短跨度": "盘出人、前史与默认下场；推演最细到流月（卡上带 months，另有 monthGrid），单元由局与日历排；按大运切的卷在这里多半只有一卷",
    "长跨度": "一年约一个大段，热年给大段的主事件；单元仍由局与日历排",
    "回到关口年": "现在段短；returns 给各人窗前的关口年，单元回到谁的哪一年由事件链挑：先给成年的他，再回去，现在段晚几章让他认出来",
}


def _holder_at(obj: dict, year: int) -> str:
    h = obj["holder"]
    for ps in sorted(obj.get("passes", []), key=lambda x: x["year"]):
        if ps["year"] <= year:
            h = ps["to"]
    return h


def _expand(charts: list[dict], window: tuple[int, int], main: str, cards: list[dict], threads: list[dict], casting: dict | None,
            elders: list[dict], guests: list[dict], horizon: int, timescale: str, edges: dict) -> dict:
    """默认下场、前史与事件源扩表（DESIGN-戏剧层 6、5.2、7.2、7.5）。byYear：窗里每年的新几种源；cardExtra：卡上的谁碎与两难给谁。"""
    a, b = window
    names = [c["name"] for c in charts]
    by_name = {c["name"]: c for c in charts}
    birth = {c["name"]: _mx._anchor(c) for c in charts}
    cast = casting or {}
    background = set(cast.get("background", []))
    fd = _fate.build(charts, window, horizon, elders, cast.get("families"), skip=background)
    feats = list(fd["features"])
    cache: dict = {}

    def at(n: str, year: int) -> dict | None:
        k = (n, year)
        if k not in cache:
            age = year - birth[n]
            if age < 0:
                cache[k] = None
            else:
                y = _fate._year(by_name[n], age, year)
                cache[k] = {"y": y, "age": age, "item": _dl.rewrite_year(y, f"L-{age}-{y['pillar']}") if _tl._is_candidate(y) else None}
        return cache[k]

    by_year: dict[int, list[dict]] = {y: [] for y in range(a, b + 1)}

    def add(year: int, src: dict) -> None:
        if a <= year <= b:
            by_year[year].append(src)

    # 默认下场到点；编配透过的带 revealed
    revealed = {(x["who"], x["year"]): x for x in cast.get("defaultFate", [])}
    entries = {(e["who"], e["year"]): e for p in fd["people"] for e in p["entries"]}
    for k in revealed:
        if k not in entries:
            raise ValueError(f"编配默认下场的 {k[0]} {k[1]} 年不在默认下场年表里（只有候选年份才有，见推演的 fate）")
    for p in fd["people"]:
        for e in p["entries"]:
            rv = revealed.get((e["who"], e["year"]))
            if e["inWindow"]:
                add(e["year"], {"kind": "默认下场到点", "who": e["who"], "domain": e["domain"], "text": e["text"],
                                **({"revealed": {k: v for k, v in rv.items() if k not in ("who", "year")}} if rv else {}),
                                "ids": [e["id"]] + e["ids"]})
    book = None
    if revealed:
        covers = max(y for _, y in revealed)
        book = {"coversTo": covers,
                "handover": [{"who": p["who"], "years": ys} for p in fd["people"]
                             if (ys := [e["year"] for e in p["entries"] if covers < e["year"] <= b])],
                "note": "透给读者的原本覆盖到 coversTo 这一年；过了这一年发动机交给 handover 里的人（他们默认下场的年份还在窗里）"}
    # 过去追上来：冲年支、伏吟的年份，对上领域的前史（本人的与上一代的）
    olds: dict[tuple[str, int], list[str]] = {}
    for p in fd["people"] + fd["elders"]:
        for e in p["prehistory"]:
            for c in e["catchesUp"]:
                olds.setdefault((c["who"], c["year"]), []).append(e["id"])
    for p in fd["people"]:
        for py in p["pastYears"]:
            ph = olds.get((py["who"], py["year"]), [])
            add(py["year"], {"kind": "过去追上来", "who": py["who"], "mechanisms": py["mechanisms"], "prehistory": ph,
                             **({} if ph else {"note": "没有对得上领域的前史，哪条旧账由事件链挑"}), "ids": py["ids"] + ph})
    # 对手出招：上一张卡里躲或压的、押得最重的那一头，他下一个候选年份出下一招；同一人同一年并成一条
    moves: dict[tuple[str, int], dict] = {}
    for c in cards:
        losers = [t["who"] for t in c["tendencies"] if t["lean"] == "躲或压"]
        if c.get("openThread"):
            losers.append(c["openThread"]["people"][1])
        for o in dict.fromkeys(losers):
            if o in background:
                continue
            for year in range(c["year"] + 1, b + 1):
                f = at(o, year)
                if f and f["item"]:
                    mv = moves.get((o, year))
                    if mv is None:
                        mv = moves[(o, year)] = {"kind": "对手出招", "who": o, "after": [], "text": "", "ids": f["item"]["ids"][:1]}
                        add(year, mv)
                    mv["after"].append({"year": c["year"], "against": c["source"], "stakeThen": (c["event"].get("primary") or {}).get("stake")})
                    mv["ids"] = [f"Q-{c['year']}-{o}"] + mv["ids"]
                    mv["text"] = ("、".join(f"{x['year']}年{x['against']}的事" for x in mv["after"])
                                  + f"上{o}躲或压、押得重；{year}年{o}自己有事，下一招从{o}这里出")
                    break
    # 家人出招：同一家族里他是对方的官杀（对方看他为正官、七杀），他的候选年份压到对方头上
    for fam in cast.get("families", []):
        members = [n for n in fam if n in by_name]
        for x in members:
            for t in members:
                if x == t or edges[(t, x)]["tenGod"] not in PRESS_GODS:
                    continue
                tg = edges[(t, x)]["tenGod"]
                for year in range(max(a, birth[x]), b + 1):
                    f = at(x, year)
                    if f and f["item"]:
                        add(year, {"kind": "家人出招", "who": x, "target": t, "text": f"{t}看{x}为{tg}，{x}这一年有事，压到{t}头上",
                                   "ids": [f"E-{t}-{x}-十神-{tg}"] + f["item"]["ids"][:1]})
    # 得知与认出：线程上卡时不在知情里的那一头；物件账
    th_by = {t["id"]: t for t in threads}
    for c in cards:
        for t in c["threads"]:
            th = th_by[t["id"]]
            if "knows" not in th:
                continue  # v1 线程没有知情一栏，不猜
            knows = {k["who"] for k in th["knows"] if k["since"] <= c["year"]}
            for n in th["people"]:
                if n not in knows:
                    add(c["year"], {"kind": "得知与认出", "who": n, "how": "线程", "thread": th["id"],
                                    "text": f"{n}还不知道这笔账，这回上卡可以让{n}知道", "ids": [th["id"]]})
    for o in cast.get("objects", []):
        rc = o.get("recognized")
        if rc:
            add(rc["year"], {"kind": "得知与认出", "who": rc["by"], "how": "物件", "object": o["name"], "holder": _holder_at(o, rc["year"]),
                             "planned": True, "text": f"物件账定在这一年：{rc['by']}认出{o['name']}", "ids": []})
        for c in cards:
            h = _holder_at(o, c["year"])
            if h != o["holder"] and {h, o["holder"]} <= set(c["present"]) and not (rc and c["year"] >= rc["year"]):
                add(c["year"], {"kind": "得知与认出", "who": o["holder"], "how": "物件", "object": o["name"], "holder": h, "planned": False,
                                "text": f"{o['name']}已到{h}手里，原主{o['holder']}这一年同在场", "ids": []})
    # 局与日历：钟按月挂上，同月谁的流月被引动
    grid = []
    for year in range(a, b + 1):
        c0 = charts[0]
        yp = pillar_name(sexagenary_index(c0["fourPillars"]["year"]) + year - birth[c0["name"]])
        mps = _en.month_pillars(yp)
        for m in range(1, 13):
            hits = []
            for n in names:
                if year < birth[n]:
                    continue
                mech = _en._month_mechs(by_name[n]["fourPillars"], mps[m - 1])
                if mech:
                    ids = [f"Q-{year}-{n}-{m}月-{x}" for x in mech]
                    hits.append({"who": n, "mechanisms": mech, "ids": ids})
                    feats += [{"id": i, "text": f"{year}年第{m}月（{mps[m - 1]}）{n}{x}"} for i, x in zip(ids, mech)]
            bells = [x for x in cast.get("calendar", []) if x["month"] == m and x.get("year") in (None, year)]
            for x in bells:
                add(year, {"kind": "局与日历", "name": x["name"], "month": m, "every": x.get("year") is None, "who": x.get("who", []), "hits": hits,
                           "ids": [i for h in hits for i in h["ids"]]})
            if hits or bells:
                grid.append({"year": year, "month": m, "pillar": mps[m - 1], "bells": [x["name"] for x in bells], "hits": hits})
    if timescale != "短跨度":  # 流月编号只在短跨度或钟用到时进池
        used = {i for s in by_year.values() for x in s if x["kind"] == "局与日历" for i in x["ids"]}
        feats = [f for f in feats if "月-" not in f["id"] or f["id"] in used]
    # 卡上的谁碎与两难给谁
    extra: dict[int, dict] = {}
    brs = {x["who"]: x for x in cast.get("breakers", [])}
    for c in cards:
        e: dict = {}
        if brs:
            bl = []
            for n in c["present"]:
                x = brs.get(n)
                if not x:
                    continue
                f = at(n, c["year"])
                planned = x.get("year") == c["year"]
                if planned or (f and f["item"]):
                    bl.append({"who": n, **({"by": x["by"]} if x.get("by") else {}), "planned": planned,
                               "why": "编配定在这一年" if planned else f"谁碎名单里的人，这一年是{n}的候选年份"})
            e["breakers"] = bl
        if casting and c["source"] == main:
            who = [n for n in c["present"] if n != main and n not in background and (at(n, c["year"]) or {}).get("item")]
            who.sort(key=lambda n: (n not in brs, c["present"].index(n)))
            e["dilemmaTo"] = {"who": who, "note": _dl._T["use"]}
        if e:
            extra[c["year"]] = e
    # 单元客：书前最近的热年是找上门的那件事；速生三问的底
    gl = []
    for g in guests:
        co = _fate.course(g, window, horizon)
        ph = _fate.prehistory(g, window)
        gl.append({"who": g["name"], "entry": ph[-1] if ph else None, "course": [x for x in co["entries"] if x["inWindow"]],
                   "nails": next((x for x in ph if x["nails"]), None), "breaker": brs.get(g["name"]),
                   "asks": ["照常会怎样：course", "他信的假话与钉下它的那一年：nails", "谁来说破：编配谁碎一节"]})
        for x in co["entries"]:
            feats.append({"id": x["id"], "text": f"单元客 {g['name']} 默认下场：{x['text']}"})
        for x in ph:
            feats.append({"id": x["id"], "text": f"单元客 {g['name']} 前史：{x['text']}"})
    # 回到关口年：各人窗前最烈的三个热年，六岁起（谎言钉法的年龄，回去得有一场他自己的戏）
    returns = []
    for p in fd["people"]:
        top = sorted([x for x in p["prehistory"] if x["age"] >= min(_fate._lies.CHILD_AGES)], key=lambda x: (_dl.PRIORITY.index(_dl.normalize(x["mechanism"])), -x["year"]))[:3]
        returns += [{"who": p["who"], "year": x["year"], "age": x["age"], "text": x["text"], "ids": [x["id"]]}
                    for x in sorted(top, key=lambda x: x["year"])]
    ids = {f["id"] for f in feats}
    for p in fd["people"] + fd["elders"]:
        for x in p.get("entries", []) + p["prehistory"]:
            ids |= set(x["ids"])
        ids |= set(p.get("shelfLife", {}).get("ids", []))
        for x in p.get("pastYears", []):
            ids |= set(x["ids"])
    for s in by_year.values():
        for x in s:
            ids |= set(x["ids"])
    return {"byYear": by_year, "cardExtra": extra, "features": feats, "ids": ids, "monthGrid": grid, "returns": returns, "guests": gl,
            "fate": {"people": fd["people"], "elders": fd["elders"], "reveals": fd["reveals"], **({"book": book} if book else {}),
                     "note": fd["note"]}}


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
YEAR_FIELDS = ("牌面", "因", "源", "事件", "选择", "知情", "线程", "主线温度", "读者")
KIND_NAMES = tuple(k["kind"] for k in SOURCE_KINDS)
KIND_ALIAS = {"旁人求上门": "旁人求上门、班底派活", "班底派活": "旁人求上门、班底派活", "单元客入口": "旁人求上门、班底派活"}
CARD_KINDS = ("默认下场到点", "过去追上来", "对手出招", "家人出招", "得知与认出", "局与日历")  # 卡上 sources 给的几种
FATE_STATES = ("透", "应验", "改")
_DF_REF = re.compile(r"(DF-[^\s\-，、；。,;（(]+-\d+)\s*(透|应验|改)?")  # DF-名-年，后面紧跟状态也认
_GAP = re.compile(r"^过场\s*(\d{1,4})")


def parse_kinds(value: str) -> tuple[list[str], list[str], str]:
    """源一栏："对手出招、得知与认出；为什么挑它"。返回 (认得的种类, 认不得的词, 为什么)。"""
    head, _, why = value.partition("；")
    head = head.split("，")[0]
    toks = [t.strip() for t in head.split("、") if t.strip()]
    kinds, bad = [], []
    i = 0
    while i < len(toks):
        pair = f"{toks[i]}、{toks[i + 1]}" if i + 1 < len(toks) else None
        if pair in KIND_NAMES:
            kinds.append(pair)
            i += 2
            continue
        k = KIND_ALIAS.get(toks[i], toks[i])
        if k in KIND_NAMES:
            kinds.append(k)
        else:
            bad.append(toks[i])
        i += 1
    return list(dict.fromkeys(kinds)), bad, why.strip()
TEMPERATURES = ("靠", "离", "撞", "退")
_FIELD = re.compile(r"^- ([^：:]{1,12})[：:]\s*(.*)$")
_STEP = re.compile(r"^\s+(?:\d+[.、]|[-*])\s*(.+)$")


def check_chain_drama(md: str, run: dict, threads: list[dict] | None = None) -> dict:
    """事件链新写法（模板 references/戏剧层/模板/推演.md）。返回 {"problems": [...], "warnings": [...], "stats": {...}}。
    卷：二级标题，里面要有三级标题"骨"，九个字段齐。热年：三级标题以年份起头，九个字段齐，步子至少两步，
    每步写以为与实际、标（明）或（暗）。卡上第三回上卡的线，这一年要么在线程一栏标响，要么至少一步是明的。
    线程文件里状态是埋或压的线要有 plan。溯源照旧由 check_chain 核。
    源（DESIGN-戏剧层 7.5）：十种之一起头，几种用顿号分开，分号后写为什么；卡上 sources 没给的那几种报 warn；
    连着三个热年只有热年出事报 warn。默认下场一栏可空（过场行里也认）："DF-… 透／应验／改"；编配透的那几条要写哪一年透，
    窗里到点的要写应验还是改；应验不在到点那一年、改在到点之后、没透先兑现、与编配的 outcome 不一样、编配没写透的，报 warn。"""
    problems: list[dict] = []
    warnings: list[dict] = []
    fate_marks: list[dict] = []
    fate_ids = {e["id"]: e for p in (run.get("fate") or {}).get("people", []) for e in p["entries"]}

    def marks(text: str, year: int | None, ln: int) -> None:
        if text.strip() in ("", "无"):
            return
        for m in _DF_REF.finditer(text):
            fid, state = m.group(1), m.group(2)
            if fid not in fate_ids:
                problems.append({"line": ln, "id": fid, "problem": "这一条不在推演的默认下场里"})
            elif state is None:
                problems.append({"line": ln, "id": fid, "problem": "默认下场的编号后面跟 透、应验、改 之一"})
            else:
                fate_marks.append({"id": fid, "state": state, "year": year, "line": ln})
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
        g = _GAP.match(line)
        if g:
            marks(line, int(g.group(1)), ln)
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
    kind_count: dict[str, int] = {}
    plain_run = 0
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
            src = y["fields"].get("源", "")
            if src:
                kinds, bad, why = parse_kinds(src)
                for b in bad:
                    problems.append({"line": y["line"], "problem": f"{y['year']}年源里的 {b} 不是十种源之一（{'、'.join(KIND_NAMES)}）"})
                if kinds and not why:
                    problems.append({"line": y["line"], "problem": f"{y['year']}年源要在分号后写为什么挑它"})
                card_kinds = {x["kind"] for x in (cards.get(y["year"]) or {}).get("sources", [])}
                for k in kinds:
                    kind_count[k] = kind_count.get(k, 0) + 1
                    if k in CARD_KINDS and y["year"] in cards and k not in card_kinds:
                        warnings.append({"line": y["line"], "problem": f"{y['year']}年的卡上没有{k}这一种源：编配里没写的钟、物件账、家族，或线程的知情，先补进去再跑推演"})
                plain_run = plain_run + 1 if kinds == ["热年出事"] else 0
                if plain_run == 3:
                    warnings.append({"line": y["line"], "problem": "连着三个热年只有热年出事：回去看漏了哪一种源（对手出招、得知、钟、默认下场到点……）"})
            marks(y["fields"].get("默认下场", ""), y["year"], y["line"])
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
    # 默认下场：透了没有、兑现了没有
    by_id: dict[str, list[dict]] = {}
    for mk in fate_marks:
        by_id.setdefault(mk["id"], []).append(mk)
    planned = {f"DF-{x['who']}-{x['year']}": x for x in (run.get("casting") or {}).get("defaultFate", [])}
    end = (run.get("window") or [0, 10 ** 6])[1]
    for fid, ms in by_id.items():
        due = fate_ids[fid]["year"]
        shown = [m["year"] for m in ms if m["state"] == "透"]
        for m in ms:
            if m["state"] == "透":
                continue
            if m["state"] == "应验" and m["year"] != due:
                warnings.append({"line": m["line"], "id": fid, "problem": f"应验写在{m['year']}年，这条默认下场到点是{due}年"})
            if m["state"] == "改" and m["year"] is not None and m["year"] > due:
                warnings.append({"line": m["line"], "id": fid, "problem": f"改写在{m['year']}年，到点的{due}年已经过了"})
            if not any(x is not None and m["year"] is not None and x <= m["year"] for x in shown):
                warnings.append({"line": m["line"], "id": fid, "problem": "没透就兑现：读者不知道原本，应验或改都落空"})
            want = (planned.get(fid) or {}).get("outcome")
            if want and want != m["state"]:
                warnings.append({"line": m["line"], "id": fid, "problem": f"编配定的是{want}，事件链写了{m['state']}；改了就回去改编配"})
        if shown and planned and fid not in planned:
            warnings.append({"line": ms[0]["line"], "id": fid, "problem": "编配的默认下场一节没写透这一条，补进编配"})
    for fid, x in planned.items():
        ms = by_id.get(fid, [])
        if not any(m["state"] == "透" for m in ms):
            problems.append({"line": 0, "id": fid, "problem": "编配透给读者的这一条，事件链没写哪一年透"})
        if x["year"] <= end and not any(m["state"] in ("应验", "改") for m in ms):
            problems.append({"line": 0, "id": fid, "problem": "编配透给读者的这一条到点了，事件链没写应验还是改"})
    return {"problems": problems, "warnings": warnings,
            "stats": {"volumes": len(vols), "years": len(seen_years), "openSteps": open_steps, "rung": rung,
                      "temperature": "".join(temps), "sources": kind_count,
                      "defaultFate": {x: sum(1 for m in fate_marks if m["state"] == x) for x in FATE_STATES},
                      "threadsOpen": sum(1 for t in threads or [] if t["status"] in THREAD_OPEN),
                      "threadsClosed": sum(1 for t in threads or [] if t["status"] not in THREAD_OPEN)}}


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="群像推演：事件卡与悬置线程")
    ap.add_argument("charts", nargs="*", help="命盘档案 JSON")
    ap.add_argument("--window", nargs=2, type=int, metavar=("起", "止"), help="故事纪年段")
    ap.add_argument("--main", help="主角名：同分时他先当事件源；卷按他的大运切（长跨度的书才这样分卷）")
    ap.add_argument("--threads", help="线程文件 群像/线程.json")
    ap.add_argument("--casting", help="编配的机器本 群像/编配.json（主线、副线、背景的人、领域配权；v2 另有时间尺度、谁碎、家族、默认下场、钟、物件账）")
    ap.add_argument("--months", action="store_true", help="热年在场的人带十二流月（短跨度自动带）")
    ap.add_argument("--elders", nargs="*", default=[], help="上一代的命盘：只出前史，不进交汇点")
    ap.add_argument("--guests", nargs="*", default=[], help="单元客的命盘：只出入口（书前的热年）与默认下场，不进交汇点")
    ap.add_argument("--horizon", type=int, default=_fate.DEFAULT_HORIZON, help="默认下场延到窗后几年，默认 10")
    ap.add_argument("--check-chain", metavar="MD", help="核对人物/推演.md 的溯源都在推演 idPool 里")
    ap.add_argument("--run", metavar="JSON", help="--check-chain 用：推演.json")
    ap.add_argument("--drama", action="store_true", help="--check-chain 用：按事件链新写法再查骨、因、落差、明暗、升级、源与默认下场（DESIGN-戏剧层 8）")
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
            warnings = d["warnings"]
            stats = d["stats"]
        else:
            warnings = []
        for p in problems:
            print(json.dumps({"file": ns.check_chain, **p}, ensure_ascii=False))
        for p in warnings:
            print(json.dumps({"file": ns.check_chain, "level": "warn", **p}, ensure_ascii=False))
        print(json.dumps({"summary": True, "file": ns.check_chain, "problems": len(problems), "warnings": len(warnings), **stats},
                         ensure_ascii=False))
        return 1 if problems else 0
    if not ns.charts or not ns.window or not ns.main:
        ap.error("要给命盘、--window 与 --main")
    charts = [json.loads(Path(p).read_text(encoding="utf-8")) for p in ns.charts]
    threads = load_threads(json.loads(Path(ns.threads).read_text(encoding="utf-8"))) if ns.threads else []
    casting = json.loads(Path(ns.casting).read_text(encoding="utf-8")) if ns.casting else None
    elders = [json.loads(Path(p).read_text(encoding="utf-8")) for p in ns.elders]
    guests = [json.loads(Path(p).read_text(encoding="utf-8")) for p in ns.guests]
    out = build(charts, (ns.window[0], ns.window[1]), ns.main, threads, ns.months, casting, elders, guests, ns.horizon)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
