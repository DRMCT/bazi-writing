"""年表展开（DESIGN 10 第 1–2 条）：大运定阶段基调，逐年流年对命局与大运做刑冲合害，标出机制与领域，作候选大事件。

脚本只算事实：机制说怎么发生，领域说赌注是什么（第 10 节九领域表，由被引动的宫位与十神推出）。
事件类型的叙事映射（岁运事件类型表）与两难改写是解读层的事，这里不写。

机制：冲提纲、冲日支、冲年支、冲时支、天克地冲某柱、伏吟某柱、刑、害、合日支、岁运并临（流年与大运同柱）、
岁运相冲（流年支冲大运支）、换运、合绊用神、合化为用（取自 arc.transit_score 的逐项来由）、忌神透干、用神到位。
领域：
- 感情：日支（配偶宫）受冲刑害合；流年见亲密关系星（命盘顶层 loverStar，默认男取财、女取官杀，DESIGN 7.3）；流年逢桃花、红艳。
- 六亲：年柱（祖上）、月柱（父母）、时柱（子女）受冲刑或天克地冲；流年十神为财（父）、印（母）、比劫（手足）时并记。
- 财富：流年见财；流年比劫而命局财透（比劫夺财）；流年冲开命局财库。
- 事业与权力：流年见官杀；冲提纲；流年逢将星。
- 身心：天克地冲日柱（身）；流年逢华盖、流年支落日柱旬空（心）。
- 名誉与是非：伤官见官（流年伤官而命局正官透，或反之）；流年冲命局官杀本气之支；流年七杀而命局无食神制。
- 学识与真相：流年见印；流年逢文昌；流年财而命局印透（财坏印）。
- 迁徙与归属：流年逢驿马；冲年支；冲月支。
- 创造与传承：流年见食伤；时柱受冲合。
领域信号分强弱：宫位受冲刑害合、天克地冲、伏吟、冲开财库、伤官见官、冲官杀之支、流年神煞、旬空为强信号；
"流年见某十神"一类（见财、见官杀、见印、见食伤、见亲密关系星、比劫夺财、财坏印、七杀无制）为弱信号，一年里两个以上弱信号才记该领域，
否则每年都动四五个领域，挑不出年份。候选年份只看机制：两个以上关键机制，或冲提纲、冲日支、天克地冲、岁运并临之一；
不看顺逆分，因为流年干支落在忌神上的年份太多（普通盘六成年份分数到 0.7），"这一年不顺"不等于"这一年出事"。

命令行：
    python -m bazi_core.timeline 命盘/沈砚.json --window 0 60 > 命盘/沈砚.年表.json
--window 是故事窗；逐年表自动延到与窗相交的最后一步大运的末尾（coverage 字段记实际覆盖），阶段事实按整十年算，
顶层 candidates 只算窗内。
编号：L-{岁}-{流年}（与命盘 liunian 同号）、L-{岁}-{流年}-{机制}、L-{岁}-{流年}-域-{领域}；check-character.js 加 --timeline 读。
阶段事实（2026-09-24，阶段状态卡的事实层，见 stage_facts）：stages 每步另带干支十神、用喜忌、顺逆档位、与命局的冲合、日主在运支的
十二长生、运柱神煞、十神与命局的叠合（叠、近、新）、这十年最常动的领域、窗内候选年份，编号 D-{步}-{干支}-{干|支|档|长生|煞|叠|近|新|域|机制}-…，
与 D-{步}-{干支}-基调 同放 features；stagecard.py 据此出草稿。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from . import arc as arc_mod
from . import changsheng as changsheng_mod
from . import intimacy as intimacy_mod
from . import relations as R
from . import shensha as shensha_mod
from . import yongshen as yongshen_mod
from . import yunqi as yunqi_mod
from .dayun import pillar_name, sexagenary_index
from .shishen import BRANCHES, HIDDEN_STEMS, STEMS, WUXING, element_of, ten_god

SCHEMA = "bazi-timeline/v1"
DOMAINS = ("感情", "六亲", "财富", "事业与权力", "身心", "名誉与是非", "学识与真相", "迁徙与归属", "创造与传承")
KEY_MECH = ("冲提纲", "冲日支", "天克地冲", "伏吟", "岁运并临", "岁运相冲", "换运")
STRONG_MECH = ("冲提纲", "冲日支", "天克地冲", "岁运并临")  # 单独一条就进候选的机制
_KEYS = ("year", "month", "day", "hour")
_CN = {"year": "年", "month": "月", "day": "日", "hour": "时"}
_PALACE = {"year": "祖上", "month": "父母", "hour": "子女"}
_FAM = {"比肩": "比劫", "劫财": "比劫", "食神": "食伤", "伤官": "食伤", "正财": "财", "偏财": "财",
        "正官": "官杀", "七杀": "官杀", "正印": "印", "偏印": "印"}
_TRANSIT_SHENSHA = ("桃花", "红艳", "驿马", "将星", "文昌", "华盖", "天乙贵人", "羊刃")


def _birth_year(chart: dict) -> int | None:
    cal = chart.get("calendar") or {}
    if cal.get("mode") == "real" and cal.get("birthLocal"):
        return datetime.fromisoformat(cal["birthLocal"]).year
    return cal.get("storyEpochBirthYear")


def _step_at(steps: list[dict], age: int) -> dict | None:
    for s in steps:
        if s["startAge"] <= age < s["endAge"]:
            return s
    return None


def _transit_shensha(pillars: dict, ln: str) -> list[str]:
    probe = {**pillars, "hour": ln}
    return sorted({h["name"] for h in shensha_mod.compute(probe) if "hour" in h["positions"] and h["name"] in _TRANSIT_SHENSHA})


def year_facts(chart: dict, age: int, ys: dict, steps: list[dict]) -> dict:
    p = chart["fourPillars"]
    ds = STEMS.index(p["day"][0])
    base = sexagenary_index(p["year"])
    ln = pillar_name(base + age)
    stem_god = ten_god(ds, STEMS.index(ln[0]))
    branch_god = ten_god(ds, HIDDEN_STEMS[BRANCHES.index(ln[1])][0])
    gods = {stem_god, branch_god}
    fams = {_FAM[g] for g in gods}
    step = _step_at(steps, age)
    ts = arc_mod.transit_score(p, ln, ys)
    tr = R.transit_relations(p, ln)
    mech: list[str] = []
    dom: dict[str, list[tuple[str, bool]]] = {}

    def d(domain: str, why: str, weak: bool = False) -> None:
        dom.setdefault(domain, [])
        if why not in [x for x, _ in dom[domain]]:
            dom[domain].append((why, weak))

    for k in _KEYS:
        if not p.get(k):
            continue
        h = tr["byPillar"][k]
        for rel in h["branches"]:
            if rel == "六冲":
                name = {"month": "冲提纲", "day": "冲日支"}.get(k, f"冲{_CN[k]}支")
                mech.append(name)
            elif rel in ("刑", "自刑"):
                mech.append(f"{R.xing_direction(ln[1], p[k][1]) or '刑'}（{_CN[k]}支）")
            elif rel == "害":
                mech.append(f"害{_CN[k]}支")
            elif rel == "六合":
                mech.append(f"合{_CN[k]}支")
        for tag in h["tags"]:
            mech.append(f"{tag}{_CN[k]}柱")
        hit = [r for r in h["branches"] if r in ("六冲", "刑", "自刑", "害", "六合")] + h["tags"]
        if not hit:
            continue
        what = "、".join(hit)
        if k == "day":
            d("感情", f"日支（配偶宫）{p[k][1]}受{what}")
        if k in _PALACE and any(x in hit for x in ("六冲", "刑", "自刑", "天克地冲")):
            d("六亲", f"{_CN[k]}柱（{_PALACE[k]}）受{what}")
        if k == "hour":
            d("创造与传承", f"时柱受{what}")
        if k in ("year", "month") and "六冲" in hit:
            d("迁徙与归属", f"冲{_CN[k]}支{p[k][1]}")
        if k == "month" and "六冲" in hit:
            d("事业与权力", f"冲提纲{p[k][1]}")
        if k == "day" and "天克地冲" in hit:
            d("身心", f"天克地冲日柱{p['day']}（身）")
    if step:
        sp = R.pillar_pair(ln, step["pillar"])
        if ln == step["pillar"]:
            mech.append("岁运并临")
        if "六冲" in sp["branches"]:
            mech.append("岁运相冲")
        if step["startAge"] == age and step["sequence"] > 1:
            mech.append("换运")
    for t in ts["terms"]:
        if "合绊" in t["term"]:
            mech.append("合绊用神")
        elif "为用" in t["term"] and "合" in t["term"]:
            mech.append("合化为用")
    s_el = WUXING[element_of(STEMS.index(ln[0]))]
    b_el = WUXING[element_of(HIDDEN_STEMS[BRANCHES.index(ln[1])][0])]
    if ys["roles"][s_el] == "忌":
        mech.append("忌神透干")
    if "用" in (ys["roles"][s_el], ys["roles"][b_el]):
        mech.append("用神到位")

    # 十神与神煞推领域
    lover = intimacy_mod.lover_gods(chart)
    for g in gods:
        if g in lover:
            d("感情", f"流年见亲密关系星{g}", weak=True)
    six = {"财": "父", "印": "母", "比劫": "手足"}
    if "六亲" in dom:
        for f in six:  # 固定顺序：集合迭代顺序随进程的哈希种子变，via 的次序会漂（2026-09-24-11 推演样例重生成时发现）
            if f in fams:
                d("六亲", f"流年{f}星（{six[f]}）", weak=True)
    natal_exposed = {ten_god(ds, STEMS.index(p[k][0])) for k in ("year", "month", "hour") if p.get(k)}
    natal_main = {ten_god(ds, HIDDEN_STEMS[BRANCHES.index(p[k][1])][0]) for k in _KEYS if p.get(k)}
    if "财" in fams:
        d("财富", "流年见财", weak=True)
        if natal_exposed & {"正印", "偏印"}:
            d("学识与真相", "流年财坏命局透印", weak=True)
    if "比劫" in fams and natal_exposed & {"正财", "偏财"}:
        d("财富", "流年比劫夺命局透财", weak=True)
    cai_yang = STEMS[((element_of(ds) + 2) % 5) * 2]  # 财之五行的阳干；墓库按十二长生表（火土同宫）
    ku = next(b for b in BRANCHES if changsheng_mod.stage(cai_yang, b) == "墓")
    if any(p[k][1] == ku for k in _KEYS if p.get(k)) and R.LIU_CHONG.get(ln[1]) == ku:
        d("财富", f"冲开财库{ku}")
    if "官杀" in fams:
        d("事业与权力", "流年见官杀", weak=True)
    if "印" in fams:
        d("学识与真相", "流年见印", weak=True)
    if "食伤" in fams:
        d("创造与传承", "流年见食伤", weak=True)
    if ("伤官" in gods and "正官" in natal_exposed) or ("正官" in gods and "伤官" in natal_exposed):
        d("名誉与是非", "伤官见官")
    if "七杀" in gods and "食神" not in natal_exposed | natal_main:
        d("名誉与是非", "七杀无制", weak=True)
    for k in _KEYS:
        if p.get(k) and R.LIU_CHONG.get(ln[1]) == p[k][1] and _FAM[ten_god(ds, HIDDEN_STEMS[BRANCHES.index(p[k][1])][0])] == "官杀":
            d("名誉与是非", f"冲{_CN[k]}支官杀")
    ss = _transit_shensha(p, ln)
    for n in ss:
        if n in ("桃花", "红艳"):
            d("感情", f"流年逢{n}")
        elif n == "驿马":
            d("迁徙与归属", "流年逢驿马")
        elif n == "将星":
            d("事业与权力", "流年逢将星")
        elif n == "文昌":
            d("学识与真相", "流年逢文昌")
        elif n == "华盖":
            d("身心", "流年逢华盖（心）")
    if ln[1] in shensha_mod.xun_kong(p["day"]):
        d("身心", "流年支落日柱旬空（心）")

    by = _birth_year(chart)
    return {
        "age": age, "year": None if by is None else by + age, "pillar": ln,
        "tenGods": {"stem": stem_god, "branch": branch_god},
        "dayun": None if step is None else {"pillar": step["pillar"], "startAge": step["startAge"], "endAge": step["endAge"]},
        "score": ts["score"], "terms": ts["terms"],
        "mechanisms": list(dict.fromkeys(mech)),
        # strong：有强信号；weight：强信号计 2、弱信号计 1，两难改写按它挑主领域（dilemma.py）
        "domains": [{"domain": k, "via": [why for why, _ in dom[k]], "strong": any(not weak for _, weak in dom[k]),
                     "weight": sum(1 if weak else 2 for _, weak in dom[k])} for k in DOMAINS
                    if k in dom and (any(not weak for _, weak in dom[k]) or len(dom[k]) >= 2)],
        "shensha": ss,
        # 年景标签（全书共享，tables/yunqi_year.json）只在表起草后才带；整句在年度状态卡与群像事件卡里
        **({"yearScene": _scene["label"]} if (_scene := yunqi_mod.year_qi(ln).get("scene")) else {}),
    }


def _pillar_mechs(p: dict, transit: str) -> list[str]:
    """一步大运（或流年）对命局四柱的冲刑害合与天克地冲、伏吟，命名与 year_facts 的机制一致。"""
    tr = R.transit_relations(p, transit)
    mech: list[str] = []
    for k in _KEYS:
        if not p.get(k):
            continue
        h = tr["byPillar"][k]
        for rel in h["branches"]:
            if rel == "六冲":
                mech.append({"month": "冲提纲", "day": "冲日支"}.get(k, f"冲{_CN[k]}支"))
            elif rel in ("刑", "自刑"):
                mech.append(f"{R.xing_direction(transit[1], p[k][1]) or '刑'}（{_CN[k]}支）")
            elif rel == "害":
                mech.append(f"害{_CN[k]}支")
            elif rel == "六合":
                mech.append(f"合{_CN[k]}支")
        for tag in h["tags"]:
            mech.append(f"{tag}{_CN[k]}柱")
    return list(dict.fromkeys(mech))


def stage_facts(chart: dict, step: dict, sc: dict, years: list[dict], ys: dict) -> dict:
    """一步大运的阶段事实（DESIGN 10 第 6 条前半，阶段状态卡的事实层）：干支十神与用喜忌、顺逆档位、与命局的冲合、
    日主在运支的十二长生、运柱神煞、十神与命局的叠合（命局已有为叠、没有为新）、这十年最常动的领域、窗内的候选年份。
    编号 D-{步}-{干支}-…，与年表 features 同放；解读按阶段状态表（tables/stage_overlay.json，stagecard.py 出草稿）。"""
    p = chart["fourPillars"]
    ds = STEMS.index(p["day"][0])
    gz = step["pillar"]
    stem_god = ten_god(ds, STEMS.index(gz[0]))
    branch_god = ten_god(ds, HIDDEN_STEMS[BRANCHES.index(gz[1])][0])
    s_el = WUXING[element_of(STEMS.index(gz[0]))]
    b_el = WUXING[element_of(HIDDEN_STEMS[BRANCHES.index(gz[1])][0])]
    roles = {"stem": ys["roles"][s_el], "branch": ys["roles"][b_el]}  # 闲神带偏喜偏忌，编号只取首字
    band = arc_mod.tone_band(sc["score"])
    mech = _pillar_mechs(p, gz)
    for t in sc["terms"]:
        if "合绊" in t["term"]:
            mech.append("合绊用神")
        elif "为用" in t["term"] and "合" in t["term"]:
            mech.append("合化为用")
        elif t["term"].startswith("补调候"):
            mech.append("补调候")
    mech = list(dict.fromkeys(mech))
    cs = changsheng_mod.stage(p["day"][0], gz[1])
    ss = _transit_shensha(p, gz)
    natal_exposed = {ten_god(ds, STEMS.index(p[k][0])) for k in ("year", "month", "hour") if p.get(k)}
    natal_main = {ten_god(ds, HIDDEN_STEMS[BRANCHES.index(p[k][1])][0]) for k in _KEYS if p.get(k)}
    natal_fams = {_FAM[g] for g in natal_exposed | natal_main}
    overlay = {g: ("叠" if g in natal_exposed | natal_main else "近" if _FAM[g] in natal_fams else "新")
               for g in dict.fromkeys((stem_god, branch_god))}  # 叠：命局透干或本气已有；近：同家族的另一个；新：全无
    tally: dict[str, int] = {}
    for y in years:
        for dmn in y["domains"]:
            tally[dmn["domain"]] = tally.get(dmn["domain"], 0) + dmn["weight"]
    order = {d: i for i, d in enumerate(DOMAINS)}
    top = sorted(tally, key=lambda d: (-tally[d], order[d]))[:2]
    head = f"D-{step['sequence']}-{gz}"
    span = f"第{step['sequence']}步大运{gz}（{step['startAge']}至{step['endAge']}岁）"
    feats = [
        {"id": f"{head}-干-{stem_god}", "text": f"{span}天干{gz[0]}为{stem_god}，示人的偏移"},
        {"id": f"{head}-支-{branch_god}", "text": f"{span}地支{gz[1]}本气为{branch_god}，底色"},
        {"id": f"{head}-干-{roles['stem'][0]}", "text": f"{span}天干{gz[0]}{s_el}为{roles['stem']}"},
        {"id": f"{head}-支-{roles['branch'][0]}", "text": f"{span}地支{gz[1]}{b_el}为{roles['branch']}"},
        {"id": f"{head}-档-{band}", "text": f"{span}顺逆分 {sc['score']}，档位{band}"},
        {"id": f"{head}-长生-{cs}", "text": f"{span}日主{p['day'][0]}在运支{gz[1]}为{cs}"},
    ]
    feats += [{"id": f"{head}-{m}", "text": f"{span}{m}"} for m in mech]
    feats += [{"id": f"{head}-煞-{n}", "text": f"{span}运柱逢{n}"} for n in ss]
    _ov = {"叠": "命局已有，放大", "近": "命局有同家族的另一个，换了方向", "新": "命局所无，新来"}
    feats += [{"id": f"{head}-{kind}-{g}", "text": f"{span}{g}{_ov[kind]}"} for g, kind in overlay.items()]
    feats += [{"id": f"{head}-域-{d}", "text": f"{span}最常动的领域{d}（信号权重 {tally[d]}）"} for d in top]
    ids = [f["id"] for f in feats]
    assert len(ids) == len(set(ids)), ids
    return {"tenGods": {"stem": stem_god, "branch": branch_god}, "elements": {"stem": s_el, "branch": b_el}, "roles": roles,
            "band": band, "mechanisms": mech, "changsheng": cs, "shensha": ss, "overlay": overlay,
            "domains": [{"domain": d, "weight": tally[d]} for d in top],
            "candidates": [y["age"] for y in years if _is_candidate(y)], "features": feats}


def _is_candidate(y: dict) -> bool:
    """候选年份：两个以上关键机制，或冲提纲、冲日支、天克地冲、岁运并临之一。只有换运、伏吟、岁运相冲之一的年份不进候选。
    不看顺逆分：15 张盘试过，带分数门槛的规则候选数随盘在 14 到 40 之间漂，只看机制稳定在 12 到 16。"""
    key = [m for m in y["mechanisms"] if m.startswith(KEY_MECH)]
    return len(key) >= 2 or any(m.startswith(STRONG_MECH) for m in key)


_QI_EL = {"厥阴风木": "木", "少阴君火": "火", "少阳相火": "火", "太阴湿土": "土", "阳明燥金": "金", "太阳寒水": "水"}
_OVERCOMES = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


def illness_candidate(chart: dict, y: dict) -> dict | None:
    """身心域被引动的年份的病候（DESIGN 7.4 病秧子问题）：三层交汇写在一条里，生年运气给档、薄弱处、病候与情志方向（命盘 yunqi.events），
    故事年运气给那年的岁气与疫季（yunqi.year_qi 按流年干支），年表给这一年身心域为何被引动。流年司天或在泉克薄弱脏标加重（五行通则，推演）。
    候选，默认不写进人物档案；作者挑，一步大运最多一次。旧命盘没有 events 时返回 None。"""
    ev = (chart.get("yunqi") or {}).get("events")
    dom = next((d for d in y["domains"] if d["domain"] == "身心"), None)
    if not ev or not dom:
        return None
    yq = yunqi_mod.year_qi(y["pillar"])
    organ_el = ev.get("organElement") or ""
    pressing = [q for q in (yq["siTian"], yq["zaiQuan"]) if organ_el and _OVERCOMES.get(_QI_EL[q]) == organ_el]
    grade = ev["grade"]
    severe = grade != "和" or bool(pressing) or dom["strong"]
    return {
        "domainVia": dom["via"], "strong": dom["strong"],
        "yearQi": yq["summary"], "epidemicSteps": yq["epidemicSteps"], "pressing": pressing,
        "grade": grade, "gradeWhy": ev["gradeWhy"], "tempo": ev["tempo"],
        "organ": ev["organ"], "illness": ev["illness"]["severe" if severe else "mild"],
        "fatal": ev["illness"]["fatal"] if grade == "危" else "",
        "zhi": ev["zhi"], "mood": ev["mood"]["severe" if severe else "mild"],
        "level": "重相" if severe else "轻相",
        "ids": ev.get("ids", []),
    }


def build(chart: dict, window: tuple[int, int]) -> dict:
    p = chart["fourPillars"]
    ys = chart.get("yongshen") or yongshen_mod.determine(p)
    steps = chart["dayun"]["steps"]
    a, b = window
    scored = {s["sequence"]: s for s in arc_mod.dayun_scores(p, steps, ys)}
    stages = []
    for s in steps:
        if s["endAge"] > a and s["startAge"] <= b:
            sc = scored[s["sequence"]]
            tone = "顺" if sc["score"] > 0 else "逆" if sc["score"] < 0 else "平"
            stages.append({"sequence": s["sequence"], "pillar": s["pillar"], "ages": [s["startAge"], s["endAge"]],
                           "score": sc["score"], "tone": tone, "terms": sc["terms"], "flags": sc["flags"]})
    # 逐年表延到与窗相交的最后一步大运的末尾：末卡的阶段事实（候选、领域、挂钩年份）才有整十年可落，
    # 不然阶段卡"需要的得失"落不到年份（2026-09-24 子代理改样例时发现）。窗内外以 window 与 coverage 区分，候选年份只算窗内。
    b_ext = max([b] + [s["endAge"] - 1 for s in steps if s["endAge"] > a and s["startAge"] <= b])
    years = [year_facts(chart, age, ys, steps) for age in range(a, b_ext + 1)]
    feats: list[dict] = []
    for y in years:
        head = f"L-{y['age']}-{y['pillar']}"
        feats.append({"id": head, "text": f"{y['age']}岁流年{y['pillar']}，顺逆分 {y['score']}"})
        for m in y["mechanisms"]:
            feats.append({"id": f"{head}-{m}", "text": f"{y['age']}岁流年{y['pillar']}{m}"})
        for dmn in y["domains"]:
            feats.append({"id": f"{head}-域-{dmn['domain']}", "text": f"{y['age']}岁流年{y['pillar']}动{dmn['domain']}：{'；'.join(dmn['via'])}"})
        ic = illness_candidate(chart, y)
        if ic:
            y["illnessCandidate"] = ic
            feats.append({"id": f"{head}-病候", "text": (
                f"{y['age']}岁流年{y['pillar']}身心域被引动（{'；'.join(ic['domainVia'])}），病候候选（默认不写，作者挑，一步大运最多一次）："
                f"{ic['yearQi']}" + (f"，{'、'.join(ic['pressing'])}克此人薄弱的{ic['organ']}，加重" if ic["pressing"] else "")
                + f"；此人{ic['grade']}档（{ic['gradeWhy']}；{ic['tempo']}），薄弱处{ic['organ']}，取{ic['level']}：病 {ic['illness']}"
                + (f"；危及性命之候 {ic['fatal']}" if ic["fatal"] else "")
                + f"；情志往{ic['zhi']}的方向垮：{ic['mood']}")})
    for st in stages:
        feats.append({"id": f"D-{st['sequence']}-{st['pillar']}-基调", "text": f"第{st['sequence']}步大运{st['pillar']}（{st['ages'][0]}至{st['ages'][1]}岁）基调{st['tone']}，顺逆分 {st['score']}"})
        step = next(s for s in steps if s["sequence"] == st["sequence"])
        in_stage = [y for y in years if st["ages"][0] <= y["age"] < st["ages"][1]]
        sf = stage_facts(chart, step, scored[st["sequence"]], in_stage, ys)
        feats += sf.pop("features")
        st.update(sf)
    cands = [y["age"] for y in years if _is_candidate(y) and y["age"] <= b]
    return {"schema": SCHEMA, "algorithm": "bazi-writing timeline v1（DESIGN 10 第 1–2 条）", "name": chart.get("name"),
            "window": [a, b], "coverage": [a, b_ext], "yong": ys["yong"], "stages": stages, "years": years, "candidates": cands, "features": feats}


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="命盘档案 → 年表（大运基调、逐年机制与领域、候选大事件）")
    ap.add_argument("chart")
    ap.add_argument("--window", type=int, nargs=2, default=[0, 60], metavar=("起", "止"), help="展开的周岁段，含两端")
    a = ap.parse_args(argv)
    with open(a.chart, encoding="utf-8") as f:
        chart = json.load(f)
    out = build(chart, (a.window[0], a.window[1]))
    sys.stdout.buffer.write((json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
