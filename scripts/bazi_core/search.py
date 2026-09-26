"""反推搜索（DESIGN 12）：约束 JSON → 穷举打分 → 去重 → 前几名，逐条命中说明。

两种历法：
- 架空（calendar.mode = "fictional"）：合法四柱全枚举，年 60 × 月 12 × 日 60 × 时 12 = 518,400 盘，
  月干按五虎遁、时干按五鼠遁；大运按 gender 与年干阴阳定顺逆，起运岁数取 calendar.start_age（默认 3）。
  calendar.year_pillars（年柱列表）、calendar.month_branches（月支列表）可收窄枚举，出生年份已定的角色用得上。
- 现实历（"real"）：birth_year_range 内逐日乘十二时辰，时辰取中点（子 0 点、丑 2 点……亥 22 点）当作当地太阳时，
  不做真太阳时修正；作者定下出生地后再用 chart --birth --lon 排正式命盘。

约束项（DESIGN 12.2）。每项 weight 默认 1；加 "hard": true 即硬约束，不满足直接淘汰（arc 的硬约束看 min_match，默认 0.8）：
- gender（必填，定大运顺逆）；story_age_window [起, 止]（arc 与 events 要用）
- day_master: {element: [五行…]} 或 {stem: [天干…]}
- day_branch: {any_of: [地支…]}
- strength: {value: 身旺|身弱|中和}；比值在中和带、要的是旺或弱时给半分
- structure: {any_of: [格名…]}：取格 name 或月令本格 base 任一相符
- ten_gods: {prominent: [{god, weight}], absent: [{god, weight}]}
  prominent：透干或月令本气 1，他支本气 0.5，只在中气余气 0.2；absent 反之
- yongshen: {element: [五行…]}：用神五行（本模块补的项）
- arc: {template: 模板名 或 vector: [四个数], turning_age}：分数取模板匹配分；给了 turning_age 则按 0.7 匹配 + 0.3 转折
- events: [{age_range: [a, b], type: 冲日支|冲提纲|天克地冲|伏吟|换运, weight}]：窗内有一年（换运看换步之年）命中即得分
- relations: [{to: 角色名（读 命盘/{to}.json）或 JSON 路径, ten_god_seen_by_them: 十神, ten_god_seen_by_me: 十神,
  day_branch: [六合|六冲|刑|害…], weight}]：几个键都给时取平均
- shensha: {require: [神煞名…]}：按命中比例得分

打分：每项 满足度 × 权重 累加。去重：只差一柱、且十神组成（四干加四支本气）差异不超过 4 的两盘算重复，留高分者。
同一约束两次运行结果相同（枚举序固定，同分按枚举序）。

命令行（在作者项目根下）：
    python -m bazi_core.search 约束.json [--top 5] [--save 命盘/约束] [--charts 命盘]
"""

from __future__ import annotations

import argparse
import heapq
import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import arc as arc_mod
from . import dayun as dayun_mod
from . import relations as R
from . import shensha as shensha_mod
from . import strength as strength_mod
from . import tiaohou as tiaohou_mod
from . import yongshen as yongshen_mod
from .chart import four_pillars
from .shishen import BRANCHES, HIDDEN_STEMS, STEMS, WUXING, determine_structure, element_of, stem_label, ten_god

SCHEMA = "bazi-search/v1"
_KEYS = ("year", "month", "day", "hour")
_CN = {"year": "年", "month": "月", "day": "日", "hour": "时"}
SHICHEN = [f"{b}时" for b in BRANCHES]
EVENT_TYPES = ("冲日支", "冲提纲", "天克地冲", "伏吟", "换运")
KEEP = 300  # 剪枝时保留的高分候选数，够去重后取前几名


# ---------------------------------------------------------------- 枚举

def _pillar(stem: int, branch: int) -> str:
    return STEMS[stem % 10] + BRANCHES[branch % 12]


def enumerate_fictional(year_pillars: list[str] | None = None, month_branches: list[str] | None = None):
    """年 60 × 月 12 × 日 60 × 时 12；月干五虎遁、时干五鼠遁。可按年柱、月支收窄。"""
    for yi in range(60):
        ys = yi % 10
        year = _pillar(yi % 10, yi % 12)
        if year_pillars and year not in year_pillars:
            continue
        yin_stem = ((ys % 5) * 2 + 2) % 10
        for order in range(12):
            month = _pillar(yin_stem + order, 2 + order)
            if month_branches and month[1] not in month_branches:
                continue
            for di in range(60):
                ds = di % 10
                day = _pillar(di % 10, di % 12)
                zi_stem = (ds % 5) * 2 % 10
                for hb in range(12):
                    yield {"year": year, "month": month, "day": day, "hour": _pillar(zi_stem + hb, hb)}, None


def enumerate_real(y0: int, y1: int, tz: str):
    zone = ZoneInfo(tz)
    d = date(y0, 1, 1)
    end = date(y1, 12, 31)
    while d <= end:
        for hb in range(12):
            dt = datetime(d.year, d.month, d.day, (hb * 2) % 24, 0, tzinfo=zone)
            fp = four_pillars(dt, None, apply_true_solar=False)
            yield fp["pillars"], {"local": dt.isoformat(), "date": d.isoformat(), "shichen": SHICHEN[hb], "birthJie": fp["birthJie"]}
        d += timedelta(days=1)


# ---------------------------------------------------------------- 事实

def _tg_counts(pillars: dict) -> dict[str, int]:
    ds = STEMS.index(pillars["day"][0])
    out: dict[str, int] = {}
    for k in _KEYS:
        p = pillars[k]
        if k != "day":
            g = ten_god(ds, STEMS.index(p[0]))
            out[g] = out.get(g, 0) + 1
        g = ten_god(ds, HIDDEN_STEMS[BRANCHES.index(p[1])][0])
        out[g] = out.get(g, 0) + 1
    return out


def _god_level(pillars: dict, god: str) -> tuple[float, str]:
    """某十神的显著度：透干或月令本气 1；他支本气 0.5；只在中气余气 0.2；无 0。"""
    ds = STEMS.index(pillars["day"][0])
    where = []
    for k in ("year", "month", "hour"):
        if ten_god(ds, STEMS.index(pillars[k][0])) == god:
            where.append(f"{_CN[k]}干透")
    if ten_god(ds, HIDDEN_STEMS[BRANCHES.index(pillars["month"][1])][0]) == god:
        where.append("月令本气")
    if where:
        return 1.0, "、".join(where)
    for k in ("year", "day", "hour"):
        if ten_god(ds, HIDDEN_STEMS[BRANCHES.index(pillars[k][1])][0]) == god:
            return 0.5, f"{_CN[k]}支本气"
    for k in _KEYS:
        for h in HIDDEN_STEMS[BRANCHES.index(pillars[k][1])][1:]:
            if ten_god(ds, h) == god:
                return 0.2, f"{_CN[k]}支中余气"
    return 0.0, "无"


class Ctx:
    """一张候选盘的惰性事实缓存。"""

    def __init__(self, pillars: dict, birth: dict | None, cons: dict):
        self.pillars = pillars
        self.birth = birth
        self.cons = cons
        self._c: dict = {}

    def get(self, key: str):
        if key not in self._c:
            self._c[key] = getattr(self, "_" + key)()
        return self._c[key]

    def _structure(self):
        p = self.pillars
        return determine_structure(p["year"], p["month"], p["day"], p["hour"])

    def _strength(self):
        return strength_mod.assess(self.pillars)

    def _tiaohou(self):
        p = self.pillars
        return tiaohou_mod.present_in_chart(p, p["day"][0], p["month"][1])

    def _yongshen(self):
        return yongshen_mod.determine(self.pillars, strength=self.get("strength"), tiaohou=self.get("tiaohou"))

    def _shensha(self):
        return {h["name"] for h in shensha_mod.compute(self.pillars)}

    def _dayun(self):
        cal = self.cons.get("calendar", {})
        p = self.pillars
        g = self.cons["gender"]
        if self.birth:
            dt = datetime.fromisoformat(self.birth["local"])
            from datetime import timezone
            info = dayun_mod.compute(p["year"], p["month"], g, dt.astimezone(timezone.utc), dt.year)
        else:
            info = dayun_mod.compute_from_pillars(p["year"], p["month"], g, float(cal.get("start_age", 3)))
        return [s.as_payload() for s in info.steps]


# ---------------------------------------------------------------- 约束求值：返回 (满足度, 说明)

def _c_day_master(ctx: Ctx, c: dict):
    s = ctx.pillars["day"][0]
    el = WUXING[element_of(STEMS.index(s))]
    if c.get("stem"):
        return (1.0 if s in c["stem"] else 0.0), f"日主{s}{el}"
    return (1.0 if el in c.get("element", []) else 0.0), f"日主{s}{el}"


def _c_day_branch(ctx: Ctx, c: dict):
    b = ctx.pillars["day"][1]
    return (1.0 if b in c.get("any_of", []) else 0.0), f"日支{b}"


def _c_structure(ctx: Ctx, c: dict):
    s = ctx.get("structure")
    want = c.get("any_of", [])
    if s.name in want:
        return 1.0, f"取格{s.name}"
    if s.base in want:
        return 1.0, f"月令本格{s.base}（变格{s.name}）"
    return 0.0, f"取格{s.name}" + (f"（本格{s.base}）" if s.base != s.name else "")


def _c_strength(ctx: Ctx, c: dict):
    st = ctx.get("strength")
    v = st["verdict"]
    want = c.get("value")
    if v == want:
        sat = 1.0
    elif v == "中和" or want == "中和":
        sat = 0.5
    else:
        sat = 0.0
    return sat, f"{v}（比值 {st['ratio']}）"


def _c_yongshen(ctx: Ctx, c: dict):
    y = ctx.get("yongshen")["yong"]
    return (1.0 if y["element"] in c.get("element", []) else 0.0), f"用神{y['element']}（{y['family']}）"


def _c_shensha(ctx: Ctx, c: dict):
    req = c.get("require", [])
    have = ctx.get("shensha")
    hit = [n for n in req if n in have]
    return (len(hit) / len(req) if req else 1.0), ("见" + "、".join(hit) if hit else "未见") + (f"；缺{'、'.join(n for n in req if n not in have)}" if len(hit) < len(req) else "")


def _c_god(ctx: Ctx, c: dict, absent: bool):
    lv, where = _god_level(ctx.pillars, c["god"])
    if absent:
        sat = {1.0: 0.0, 0.5: 0.3, 0.2: 0.7, 0.0: 1.0}[lv]
    else:
        sat = lv
    return sat, f"{c['god']}：{where}"


def _flow_flags(ctx: Ctx, age: int) -> tuple[str, list[str]]:
    base = dayun_mod.sexagenary_index(ctx.pillars["year"])
    ln = dayun_mod.pillar_name(base + age)
    tr = R.transit_relations(ctx.pillars, ln)
    flags = list(tr["flags"])
    if any(f.startswith("天克地冲") for f in flags):
        flags.append("天克地冲")
    if any(f.startswith("伏吟") for f in flags):
        flags.append("伏吟")
    return ln, flags


def _c_event(ctx: Ctx, c: dict):
    a, b = c["age_range"]
    t = c["type"]
    if t == "换运":
        hits = [s for s in ctx.get("dayun") if a <= s["startAge"] <= b and s["sequence"] > 1]
        if hits:
            return 1.0, f"{hits[0]['startAge']}岁换运入{hits[0]['pillar']}"
        return 0.0, f"{a}–{b}岁无换运"
    for age in range(int(a), int(b) + 1):
        ln, flags = _flow_flags(ctx, age)
        if t in flags:
            detail = next((f for f in flags if f.startswith(t) and f != t), t)
            return 1.0, f"{age}岁流年{ln}{detail}"
    return 0.0, f"{a}–{b}岁流年无{t}"


def _c_relation(ctx: Ctx, c: dict):
    other = c["_chart"]["fourPillars"]
    mine = ctx.pillars
    parts, notes = [], []
    if c.get("ten_god_seen_by_them"):
        g = ten_god(STEMS.index(other["day"][0]), STEMS.index(mine["day"][0]))
        parts.append(1.0 if g == c["ten_god_seen_by_them"] else 0.0)
        notes.append(f"{c['to']}看我为{g}")
    if c.get("ten_god_seen_by_me"):
        g = ten_god(STEMS.index(mine["day"][0]), STEMS.index(other["day"][0]))
        parts.append(1.0 if g == c["ten_god_seen_by_me"] else 0.0)
        notes.append(f"我看{c['to']}为{g}")
    if c.get("day_branch"):
        rel = R.branch_pair(mine["day"][1], other["day"][1])
        parts.append(1.0 if set(rel) & set(c["day_branch"]) else 0.0)
        notes.append(f"日支{mine['day'][1]}与{other['day'][1]}" + ("、".join(rel) if rel else "无关系"))
    return (sum(parts) / len(parts) if parts else 1.0), "；".join(notes)


def _c_arc(ctx: Ctx, c: dict):
    window = tuple(ctx.cons["story_age_window"])
    res = arc_mod.analyze(ctx.pillars, ctx.get("dayun"), window, ctx.get("yongshen"), ctx.get("tiaohou"), c.get("turning_age"))
    vec = list(res["vector"].values())
    target = c.get("vector") or c.get("template")
    m = arc_mod.match(vec, target)
    sat = m
    note = f"四段 {vec}，{'自定义向量' if c.get('vector') else c['template']}匹配 {m}，最近模板{res['best']}"
    if c.get("turning_age") is not None:
        t = res["turning"]
        sat = round(0.7 * m + 0.3 * t["score"], 3)
        note += f"；转折 {t['score']}" + (f"（{t['nearest']['text']}）" if t.get("nearest") else "")
    ctx._c["arc"] = res
    return sat, note


# (名称, 成本档, 求值) ；成本档 0 为第一遍全算，1 为剪枝后才算
def build_items(cons: dict, charts_dir: Path) -> list[dict]:
    items: list[dict] = []

    def add(name: str, c: dict, fn, cost: int, want: str):
        items.append({"name": name, "c": c, "fn": fn, "cost": cost, "weight": float(c.get("weight", 1)),
                      "hard": bool(c.get("hard")), "want": want})

    if "day_master" in cons:
        c = cons["day_master"]
        add("day_master", c, _c_day_master, 0, "日主" + "、".join(c.get("stem") or c.get("element", [])))
    if "day_branch" in cons:
        add("day_branch", cons["day_branch"], _c_day_branch, 0, "日支" + "、".join(cons["day_branch"]["any_of"]))
    if "structure" in cons:
        add("structure", cons["structure"], _c_structure, 0, "、".join(cons["structure"]["any_of"]))
    tg = cons.get("ten_gods", {})
    for g in tg.get("prominent", []):
        add("ten_gods.prominent", g, lambda ctx, c: _c_god(ctx, c, False), 0, f"{g['god']}显")
    for g in tg.get("absent", []):
        add("ten_gods.absent", g, lambda ctx, c: _c_god(ctx, c, True), 0, f"无{g['god']}")
    for r in cons.get("relations", []):
        to = r["to"]
        path = Path(to) if to.endswith(".json") else charts_dir / f"{to}.json"
        r = dict(r, _chart=json.loads(path.read_text(encoding="utf-8")))
        want = "；".join(x for x in (r.get("ten_god_seen_by_them") and f"{to}看我为{r['ten_god_seen_by_them']}",
                                      r.get("ten_god_seen_by_me") and f"我看{to}为{r['ten_god_seen_by_me']}",
                                      r.get("day_branch") and f"日支{'或'.join(r['day_branch'])}") if x)
        add("relations", r, _c_relation, 0, want)
    for e in cons.get("events", []):
        if e["type"] not in EVENT_TYPES:
            raise ValueError(f"events.type 只认 {EVENT_TYPES}，收到 {e['type']}")
        add("events", e, _c_event, 0 if e["type"] != "换运" else 1, f"{e['age_range'][0]}–{e['age_range'][1]}岁{e['type']}")
    if "shensha" in cons:
        add("shensha", cons["shensha"], _c_shensha, 1, "、".join(cons["shensha"]["require"]))
    if "strength" in cons:
        add("strength", cons["strength"], _c_strength, 1, cons["strength"]["value"])
    if "yongshen" in cons:
        add("yongshen", cons["yongshen"], _c_yongshen, 1, "用神" + "、".join(cons["yongshen"]["element"]))
    if "arc" in cons:
        if "story_age_window" not in cons:
            raise ValueError("arc 约束须给 story_age_window")
        a = cons["arc"]
        if not a.get("template") and not a.get("vector"):
            raise ValueError("arc 须给 template 或 vector")
        if a.get("template") and a["template"] not in arc_mod.TEMPLATES:
            raise ValueError(f"arc.template 只认 {list(arc_mod.TEMPLATES)}")
        add("arc", a, _c_arc, 2, (a.get("template") or f"向量{a['vector']}") + (f"，{a['turning_age']}岁转折" if a.get("turning_age") is not None else ""))
    return items


def _passes_hard(item: dict, sat: float) -> bool:
    if not item["hard"]:
        return True
    if item["name"] == "arc":
        return sat >= float(item["c"].get("min_match", 0.8))
    return sat >= 0.999


# ---------------------------------------------------------------- 主流程

def _evaluate(ctx: Ctx, items: list[dict], costs: tuple[int, ...]) -> tuple[float, list[dict]] | None:
    total, hits = 0.0, []
    for it in items:
        if it["cost"] not in costs:
            continue
        sat, note = it["fn"](ctx, it["c"])
        if not _passes_hard(it, sat):
            return None
        pts = round(sat * it["weight"], 3)
        total += pts
        hits.append({"constraint": it["name"], "want": it["want"], "got": note, "sat": round(sat, 3),
                     "weight": it["weight"], "points": pts, "hard": it["hard"]})
    return total, hits


def _dup(a: dict, b: dict) -> bool:
    diff = sum(a["pillars"][k] != b["pillars"][k] for k in _KEYS)
    if diff > 1:
        return False
    ca, cb = a["_tg"], b["_tg"]
    l1 = sum(abs(ca.get(g, 0) - cb.get(g, 0)) for g in set(ca) | set(cb))
    return l1 <= 4


RANDOM_POOL_RATIO = 0.8  # 随机补位：只从分数不低于最高分八成的候选里抽


def search(cons: dict, top: int = 5, charts_dir: Path | None = None, progress=None, seed: int | None = None) -> dict:
    """seed 给了就是随机补位（DESIGN 4.1）：缺的 gender 随机、架空历缺的 start_age 随机零到九岁，
    候选盘从过硬约束且分数不低于最高分八成的池子里按种子抽 top 个，不按分数排；同种子同结果，种子写进返回的 constraints.random。"""
    if seed is None and isinstance(cons.get("random"), dict) and cons["random"].get("seed") is not None:
        seed = int(cons["random"]["seed"])
    filled: list[str] = []
    if seed is not None:
        rnd = random.Random(seed)
        cons = dict(cons)
        if cons.get("gender") not in ("male", "female"):
            cons["gender"] = rnd.choice(["male", "female"])
            filled.append("gender")
        cal0 = dict(cons.get("calendar", {"mode": "fictional"}))
        if cal0.get("mode", "fictional") == "fictional" and "start_age" not in cal0:
            cal0["start_age"] = rnd.randint(0, 9)
            cons["calendar"] = cal0
            filled.append("start_age")
        cons["random"] = {**(cons.get("random") or {}), "seed": seed, "filled": filled}
    if cons.get("gender") not in ("male", "female"):
        raise ValueError("gender 必填：male 或 female（定大运顺逆）；或给 --seed 随机补")
    charts_dir = charts_dir or Path("命盘")
    items = build_items(cons, charts_dir)
    cal = cons.get("calendar", {"mode": "fictional"})
    if cal.get("mode", "fictional") == "real":
        y0, y1 = cal["birth_year_range"]
        gen = enumerate_real(int(y0), int(y1), cal.get("tz", "Asia/Shanghai"))
    else:
        gen = enumerate_fictional(cal.get("year_pillars"), cal.get("month_branches"))
    max_total = sum(it["weight"] for it in items)
    late_max = sum(it["weight"] for it in items if it["cost"] > 0)

    # 第一遍：便宜的约束全算，硬约束淘汰。只存分数与四柱，缓存丢掉省内存；
    # 后算的约束里没有硬约束时，分数上界够不着当前第 KEEP 名第一遍分数的盘直接丢（总分不低于第一遍分数，丢得安全）。
    late_hard = any(it["hard"] for it in items if it["cost"] > 0)
    first: list[tuple[float, int, tuple, dict | None]] = []
    floor: list[float] = []
    n = 0
    for i, (pillars, birth) in enumerate(gen):
        n += 1
        if progress and n % 100000 == 0:
            progress(f"第一遍 {n} 盘")
        ctx = Ctx(pillars, birth, cons)
        r = _evaluate(ctx, items, (0,))
        if r is None:
            continue
        partial = r[0]
        if not late_hard:
            if len(floor) >= KEEP and partial + late_max < floor[0]:
                continue
            if len(floor) < KEEP:
                heapq.heappush(floor, partial)
            elif partial > floor[0]:
                heapq.heapreplace(floor, partial)
        first.append((partial, i, tuple(pillars[k] for k in _KEYS), birth))
    first.sort(key=lambda x: (-x[0], x[1]))

    # 第二遍：按第一遍分数从高到低补算其余约束，上界不及第 KEEP 名总分即停
    heap: list[tuple[float, int, dict]] = []
    evaluated = 0
    for partial, idx, pt, birth in first:
        if len(heap) >= KEEP and partial + late_max < heap[0][0]:
            break
        ctx = Ctx(dict(zip(_KEYS, pt)), birth, cons)
        r0 = _evaluate(ctx, items, (0,))
        r = _evaluate(ctx, items, (1, 2))
        evaluated += 1
        if r is None or r0 is None:
            continue
        total = round(partial + r[0], 3)
        rec = {"_idx": idx, "_ctx": ctx, "_hits": r0[1] + r[1], "total": total}
        if len(heap) < KEEP:
            heapq.heappush(heap, (total, -idx, rec))
        elif total > heap[0][0]:
            heapq.heapreplace(heap, (total, -idx, rec))
    ranked = [x[2] for x in sorted(heap, key=lambda x: (-x[0], -x[1]))]

    results: list[dict] = []
    random_info = None
    if seed is not None:
        # 随机补位：池子是第一遍过硬约束、分数不低于最高分八成的盘（约束少时几乎全池），按种子洗牌后补算其余约束，取前 top 个不按分排
        best = first[0][0] if first else 0.0
        thr = round(best * RANDOM_POOL_RATIO, 3) if best > 0 else 0.0
        pool = [x for x in first if x[0] >= thr]
        rnd = random.Random(seed)
        rnd.shuffle(pool)
        for partial, idx, pt, birth in pool:
            ctx = Ctx(dict(zip(_KEYS, pt)), birth, cons)
            r0 = _evaluate(ctx, items, (0,))
            r = _evaluate(ctx, items, (1, 2))
            evaluated += 1
            if r is None or r0 is None:
                continue
            cand = {"pillars": ctx.pillars, "_tg": _tg_counts(ctx.pillars)}
            if any(_dup(cand, x) for x in results):
                continue
            results.append({**cand, "_rec": {"_idx": idx, "_ctx": ctx, "_hits": r0[1] + r[1], "total": round(partial + r[0], 3)}})
            if len(results) >= top:
                break
        random_info = {"seed": seed, "pool": len(pool), "threshold": thr, "filled": filled}
    else:
        for rec in ranked:
            ctx: Ctx = rec["_ctx"]
            cand = {"pillars": ctx.pillars, "_tg": _tg_counts(ctx.pillars)}
            if any(_dup(cand, r) for r in results):
                continue
            results.append({**cand, "_rec": rec})
            if len(results) >= top:
                break
    out = []
    order = {it["name"]: i for i, it in enumerate(items)}
    for rank, r in enumerate(results, 1):
        rec, ctx = r["_rec"], r["_rec"]["_ctx"]
        p = ctx.pillars
        st, ys, s = ctx.get("strength"), ctx.get("yongshen"), ctx.get("structure")
        arc_res = ctx._c.get("arc")
        if arc_res is None and "story_age_window" in cons:
            arc_res = arc_mod.analyze(p, ctx.get("dayun"), tuple(cons["story_age_window"]), ys, ctx.get("tiaohou"))
        cmd = (f"--birth {ctx.birth['local'][:16]} --no-true-solar" if ctx.birth
               else f"--pillars {p['year']} {p['month']} {p['day']} {p['hour']} --start-age {cons.get('calendar', {}).get('start_age', 3)}")
        out.append({
            "rank": rank,
            "score": rec["total"],
            "max": max_total,
            "pillars": p,
            "birth": ctx.birth,
            "dayMaster": stem_label(STEMS.index(p["day"][0])),
            "structure": s.name + (f"（本格{s.base}）" if s.base != s.name else ""),
            "strength": f"{st['verdict']}（比值 {st['ratio']}）",
            "yongshen": f"{ys['yong']['element']}（{ys['yong']['family']}）：{ys['reason']}",
            "arc": None if arc_res is None else {"vector": arc_res["vector"], "best": arc_res["best"],
                                                  "steps": [{"pillar": x["pillar"], "ages": [x["startAge"], x["endAge"]], "score": x["score"]} for x in arc_res["steps"]]},
            "hits": sorted(rec["_hits"], key=lambda h: order.get(h["constraint"], 99)),
            "chartArgs": cmd + f" --gender {cons['gender']}",
        })
    return {"schema": SCHEMA, "algorithm": "bazi-writing search v1（DESIGN 12）", "constraints": cons,
            "searched": n, "kept": len(first), "fullyEvaluated": evaluated, "random": random_info, "results": out}


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="反推搜索：约束 JSON → 前几名候选盘")
    ap.add_argument("constraints", help="约束 JSON 文件")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--seed", type=int, default=None, help="随机补位：缺的性别与起运岁数随机补，候选从高分池里按种子抽而不按分排")
    ap.add_argument("--charts", default="命盘", help="relations 里按角色名找命盘档案的目录")
    ap.add_argument("--save", default=None, help="把约束与结果写进这个目录（如 命盘/约束），文件名取约束的 name 或约束文件名")
    a = ap.parse_args(argv)
    sys.stderr.reconfigure(encoding="utf-8")
    path = Path(a.constraints)
    cons = json.loads(path.read_text(encoding="utf-8"))
    res = search(cons, a.top, Path(a.charts), progress=lambda m: print(m, file=sys.stderr), seed=a.seed)
    text = json.dumps(res, ensure_ascii=False, indent=2) + "\n"
    if a.save:
        d = Path(a.save)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{cons.get('name') or path.stem}.json").write_text(text, encoding="utf-8")
    sys.stdout.buffer.write(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
