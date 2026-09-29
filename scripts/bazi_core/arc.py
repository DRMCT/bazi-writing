"""弧光走势（DESIGN-命盘层 7）：岁运顺逆分、故事时间窗重采样为起承转合四段、六个模板匹配、转折点约束。

v1 启发式，确定性、可解释：每步大运给出分数和逐项来由。权重取 DESIGN-命盘层 7.2 表的初值，用喜闲忌按
yongshen 的 preference 连续化：天干 0.4×p、地支本气 0.6×p（p：用 1、喜 0.5、闲 ±0.25、仇 -0.5、忌 -1），
表里"用 +0.4、喜 +0.2、闲 0、忌 -0.4"是 p 取 1、0.5、0、-1 的特例；仇神与偏喜偏忌的闲神是本模块补的两档。

流年按同一张表打分（transit_score），只供事件候选，不参与弧光匹配。

reading 一节按 tables/arc_match.json（弧光匹配表，自起草的叙事映射）填：最佳模板的内在弧光与四段该发生什么、
窗内每步大运的顺逆档位、转折信号的含义、匹配不上时对作者说的话。不产生编号。

命令行：
    python -m bazi_core.arc 命盘/沈砚.json --window 24 46 [--turning 30] [--template 正弧]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import relations as R
from . import strength as strength_mod
from . import tiaohou as tiaohou_mod
from . import yongshen as yongshen_mod
from .dayun import pillar_name, sexagenary_index
from .shishen import BRANCHES, HIDDEN_STEMS, STEMS, WUXING, element_of

TEMPLATES: dict[str, list[float]] = {
    "正弧": [0.2, -0.3, -0.8, 0.5],
    "负弧": [0.2, 0.7, -0.3, -0.8],
    "触底反弹": [-0.8, -0.4, 0.2, 0.7],
    "高开低走": [0.8, 0.3, -0.2, -0.6],
    "平弧": [0.1, 0.1, -0.5, 0.1],
    "震荡": [0.6, -0.6, 0.6, -0.6],
}
SEGMENTS = ("起", "承", "转", "合")

STEM_W, BRANCH_W = 0.4, 0.6
CHONG_TIGANG = -0.3
CHONG_RIZHI = -0.3
HE_BAN_YONG = -0.2
HE_HUA_YONG = 0.2
BU_TIAOHOU = 0.2
FUYIN_YONG, FUYIN_JI = 0.1, -0.2
NOISE = 0.15
TURN_STEP, TURN_MAX = 0.1, 3

_KEYS = ("year", "month", "day", "hour")
_CN = {"year": "年", "month": "月", "day": "日", "hour": "时"}


def _el(stem_idx: int) -> int:
    return element_of(stem_idx)


def _branch_main_el(branch: str) -> int:
    return _el(HIDDEN_STEMS[BRANCHES.index(branch)][0])


def _hua_ok(element: str, month_branch: str) -> bool:
    rule = strength_mod.STEM_HUA_RULES.get(element)
    return bool(rule) and (month_branch in rule["months"] or month_branch == rule["next"])


def transit_score(pillars: dict, transit: str, ys: dict, th: dict | None = None) -> dict:
    """一步大运（或一个流年）对命局的顺逆分。返回 {score, raw, terms: [{term, value}]}。"""
    th = th or tiaohou_mod.lookup(pillars["day"][0], pillars["month"][1])
    pref = ys["preference"]
    roles = ys["roles"]
    yong = WUXING.index(ys["yong"]["element"])
    s_el = _el(STEMS.index(transit[0]))
    b_el = _branch_main_el(transit[1])
    terms: list[dict] = []

    def add(term: str, value: float) -> None:
        if value:
            terms.append({"term": term, "value": round(value, 3)})

    add(f"天干{transit[0]}{WUXING[s_el]}为{roles[WUXING[s_el]]}", STEM_W * pref[WUXING[s_el]])
    add(f"地支{transit[1]}本气{WUXING[b_el]}为{roles[WUXING[b_el]]}", BRANCH_W * pref[WUXING[b_el]])

    tr = R.transit_relations(pillars, transit)
    if "冲提纲" in tr["flags"]:
        add(f"{transit[1]}冲提纲{pillars['month'][1]}", CHONG_TIGANG)
    if "冲日支" in tr["flags"]:
        add(f"{transit[1]}冲日支{pillars['day'][1]}", CHONG_RIZHI)

    month_b = pillars["month"][1]
    hua, ban = None, None
    for k in ("year", "month", "hour"):
        p = pillars.get(k)
        if not p or R.STEM_HE.get(transit[0]) != p[0]:
            continue
        he_el = R.STEM_HE_ELEMENT.get(transit[0] + p[0])
        if he_el and WUXING.index(he_el) == yong and _hua_ok(he_el, month_b):
            hua = hua or f"{transit[0]}合{_CN[k]}干{p[0]}化{he_el}为用"
        elif _el(STEMS.index(p[0])) == yong:
            ban = ban or f"{transit[0]}合绊{_CN[k]}干{p[0]}（用神）"
    for k in _KEYS:
        p = pillars.get(k)
        if not p or R.LIU_HE.get(transit[1]) != p[1]:
            continue
        he_el = R.LIU_HE_ELEMENT.get(transit[1] + p[1])
        if he_el and WUXING.index(he_el) == yong and _branch_main_el(month_b) == yong:
            hua = hua or f"{transit[1]}合{_CN[k]}支{p[1]}化{he_el}为用"
        elif _branch_main_el(p[1]) == yong:
            ban = ban or f"{transit[1]}合绊{_CN[k]}支{p[1]}（用神）"
    natal_b = {pillars[k][1] for k in _KEYS if pillars.get(k)}
    for table, kind in ((R.SAN_HE, "三合"), (R.SAN_HUI, "三会")):
        for ju, el in table.items():
            if transit[1] in ju and not all(z in natal_b for z in ju) and all(z in natal_b or z == transit[1] for z in ju):
                if WUXING.index(el) == yong:
                    hua = hua or f"{transit[1]}引{ju}{kind}{el}局为用"
    if hua:
        add(hua, HE_HUA_YONG)
    if ban:
        add(ban, HE_BAN_YONG)

    th_stems = [s for s in th.get("stems", []) if s in STEMS]
    if th_stems:
        th_el = _el(STEMS.index(th_stems[0]))
        if not yongshen_mod.element_in_chart(pillars, th_el) and th_el in (s_el, b_el):
            add(f"补调候{WUXING[th_el]}（命局所缺）", BU_TIAOHOU)

    for k in _KEYS:
        if pillars.get(k) == transit:
            v = pref[WUXING[s_el]]
            if v > 0:
                add(f"伏吟{_CN[k]}柱（用喜）", FUYIN_YONG)
            elif v < 0:
                add(f"伏吟{_CN[k]}柱（忌）", FUYIN_JI)
            break

    raw = sum(t["value"] for t in terms)
    score = max(-1.0, min(1.0, raw))
    if abs(score) < NOISE:
        score = 0.0
    return {"transit": transit, "score": round(score, 3), "raw": round(raw, 3), "terms": terms, "flags": tr["flags"]}


def dayun_scores(pillars: dict, steps: list[dict], ys: dict, th: dict | None = None) -> list[dict]:
    th = th or tiaohou_mod.lookup(pillars["day"][0], pillars["month"][1])
    out = []
    for s in steps:
        r = transit_score(pillars, s["pillar"], ys, th)
        out.append({"sequence": s["sequence"], "pillar": s["pillar"], "startAge": s["startAge"], "endAge": s["endAge"], **r})
    return out


def resample(scored: list[dict], window: tuple[float, float]) -> list[float]:
    """把大运分数（按岁数区间的阶梯函数）在故事时间窗内等分四段取平均。起运前（童限）记 0。"""
    a, b = window
    if b <= a:
        raise ValueError("时间窗须 a < b")
    seg = (b - a) / 4
    out = []
    for i in range(4):
        x0, x1 = a + i * seg, a + (i + 1) * seg
        acc = 0.0
        for s in scored:
            lo, hi = max(x0, s["startAge"]), min(x1, s["endAge"])
            if hi > lo:
                acc += (hi - lo) * s["score"]
        out.append(round(acc / seg, 3))
    return out


def match(vector: list[float], template: str | list[float]) -> float:
    t = TEMPLATES[template] if isinstance(template, str) else template
    return round(1 - sum(abs(x - y) for x, y in zip(vector, t)) / 8, 3)


def ranking(vector: list[float]) -> list[dict]:
    rows = [{"template": k, "vector": v, "match": match(vector, v)} for k, v in TEMPLATES.items()]
    return sorted(rows, key=lambda r: -r["match"])


def turning_candidates(pillars: dict, steps: list[dict], window: tuple[float, float]) -> list[dict]:
    """窗内的转折信号：大运换步之年，流年天克地冲日柱或冲日支之年。岁数取周岁，流年干支按年柱顺推。"""
    a, b = window
    out = []
    for s in steps:
        if a <= s["startAge"] <= b and s["sequence"] > 1:
            out.append({"age": s["startAge"], "kind": "换运", "text": f"{s['startAge']}岁换运入{s['pillar']}"})
    base = sexagenary_index(pillars["year"])
    for age in range(int(a), int(b) + 1):
        ln = pillar_name(base + age)
        pp = R.pillar_pair(ln, pillars["day"])
        if "天克地冲" in pp["tags"]:
            out.append({"age": age, "kind": "流年天克地冲日柱", "text": f"{age}岁流年{ln}天克地冲日柱{pillars['day']}"})
        elif "六冲" in pp["branches"]:
            out.append({"age": age, "kind": "流年冲日支", "text": f"{age}岁流年{ln}冲日支{pillars['day'][1]}"})
    return sorted(out, key=lambda x: x["age"])


def turning_score(cands: list[dict], turning_age: float) -> dict:
    if not cands:
        return {"score": 0.0, "nearest": None, "distance": None}
    best = min(cands, key=lambda c: (abs(c["age"] - turning_age), c["age"]))
    d = abs(best["age"] - turning_age)
    score = 0.0 if d >= TURN_MAX else round(1 - TURN_STEP * d, 3)
    return {"score": score, "nearest": best, "distance": d}


_MATCH_TABLE = Path(__file__).resolve().parent / "tables" / "arc_match.json"
_MT = json.loads(_MATCH_TABLE.read_text(encoding="utf-8"))
_MSEC = {s["key"]: s for s in _MT["sections"]}
_TEMPLATE_ROWS = {r["template"]: r for r in _MSEC["templates"]["rows"]}
_TONE_ROWS = _MSEC["tones"]["rows"]
_TURNING_ROWS = {r["kind"]: r for r in _MSEC["turnings"]["rows"]}
_ADVICE_ROWS = _MSEC["mismatch"]["rows"]


def tone_band(score: float) -> str:
    """顺逆分的档位名（弧光匹配表 tones 分表）：强顺、弱顺、平、弱逆、强逆。"""
    for r in _TONE_ROWS:
        lo, hi = r["range"]
        if lo <= score <= hi and not (r["band"] == "平" and abs(score) >= 0.15 and score != 0):
            return r["band"]
    return "平"


def reading(best: str, best_match: float, steps: list[dict], turning: dict | None,
            wanted: str | None = None, rank: list[dict] | None = None) -> dict:
    """按弧光匹配表把数字翻成叙事。给了作者要的模板（wanted）时，叙事与建议按它写：匹配分取它的分，
    它不是最佳模板时另记一句"数字更像哪个"，因为 L1 匹配分偏宽，几个模板常同在 0.8 上下。"""
    template = wanted or best
    match_used = best_match
    if wanted and rank:
        match_used = next(r["match"] for r in rank if r["template"] == wanted)
    row = _TEMPLATE_ROWS[template]
    tones = []
    for s in steps:
        band = tone_band(s["score"])
        t = next(r for r in _TONE_ROWS if r["band"] == band)
        tones.append({"sequence": s["sequence"], "pillar": s["pillar"], "score": s["score"], "band": band,
                      "meaning": t["meaning"], "pitfall": t["pitfall"]})
    if match_used >= 0.75:
        advice = _ADVICE_ROWS[0]
    elif match_used >= 0.6:
        advice = _ADVICE_ROWS[1]
    else:
        advice = _ADVICE_ROWS[2]
    out = {"template": template, "match": match_used, "inner": row["inner"], "segments": row["segments"], "turningHint": row["turning"],
           "anchors": row["anchors"], "tones": tones, "advice": {"when": advice["when"], "text": advice["advice"]},
           "status": "叙事映射自起草（tables/arc_match.json）"}
    if wanted and wanted != best:
        out["closer"] = {"template": best, "match": best_match,
                         "text": f"作者要的是{wanted}（{match_used}），数字更像{best}（{best_match}）；差距小于 0.05 时两说都成立，看哪一段反了再定"}
    if rank and len(rank) > 1:
        out["margin"] = round(rank[0]["match"] - rank[1]["match"], 3)
    if turning is not None:
        kinds = sorted({c["kind"] for c in turning.get("candidates", [])})
        out["turnings"] = [{"kind": k, "meaning": _TURNING_ROWS[k]["meaning"], "fit": _TURNING_ROWS[k]["fit"]} for k in kinds if k in _TURNING_ROWS]
        if turning.get("distance") is None or turning["distance"] >= TURN_MAX:
            out["turningAdvice"] = _ADVICE_ROWS[3]["advice"]
    return out


def analyze(pillars: dict, steps: list[dict], window: tuple[float, float], ys: dict | None = None,
            th: dict | None = None, turning_age: float | None = None, wanted: str | None = None) -> dict:
    ys = ys or yongshen_mod.determine(pillars)
    th = th or tiaohou_mod.lookup(pillars["day"][0], pillars["month"][1])
    scored = dayun_scores(pillars, steps, ys, th)
    vec = resample(scored, window)
    rank = ranking(vec)
    out = {
        "algorithm": "bazi-writing arc v1（DESIGN-命盘层 7，权重初值）",
        "window": list(window),
        "yong": ys["yong"],
        "steps": [s for s in scored if s["endAge"] > window[0] and s["startAge"] < window[1]],
        "vector": dict(zip(SEGMENTS, vec)),
        "templates": rank,
        "best": rank[0]["template"],
    }
    if turning_age is not None:
        cands = turning_candidates(pillars, steps, window)
        out["turning"] = {"age": turning_age, **turning_score(cands, turning_age), "candidates": cands}
    out["reading"] = reading(out["best"], rank[0]["match"], out["steps"], out.get("turning"), wanted, rank)
    return out


def for_chart(chart: dict, window: tuple[float, float], turning_age: float | None = None, wanted: str | None = None) -> dict:
    pillars = chart["fourPillars"]
    ys = chart.get("yongshen") or yongshen_mod.determine(pillars)
    return analyze(pillars, chart["dayun"]["steps"], window, ys, None, turning_age, wanted)


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="命盘档案 → 弧光走势（大运顺逆分、四段向量、模板匹配）")
    ap.add_argument("chart", help="命盘档案 JSON（bazi_core.chart 的输出）")
    ap.add_argument("--window", type=float, nargs=2, required=True, metavar=("起", "止"), help="故事覆盖的年龄段")
    ap.add_argument("--turning", type=float, default=None, help="作者要的转折年龄")
    ap.add_argument("--template", choices=sorted(TEMPLATES), default=None, help="作者要的弧光：reading 按它写，另给它的匹配分")
    a = ap.parse_args(argv)
    with open(a.chart, encoding="utf-8") as f:
        chart = json.load(f)
    out = for_chart(chart, (a.window[0], a.window[1]), a.turning, a.template)
    if a.template:
        out["templateMatch"] = {"template": a.template, "match": match(list(out["vector"].values()), a.template)}
    sys.stdout.buffer.write((json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
